"""
Adversarial validation (framework Step 3: red/blue-team the thesis).

Serenity's process: before publicising or sizing up, feed the draft thesis to
multiple LLMs acting as the harshest Devil's Advocate, hunting for technical
holes, alternative-path risk, valuation bias and geopolitical risk. Only theses
that survive multiple rounds get conviction.

This module reproduces that quantitatively and (optionally) with real LLMs:

1. ``redteam_node`` — a battery of deterministic *attack vectors*, each scoring
   a severity 0..1 with a concrete objection and the blue-team rebuttal. They
   roll up into a ``resilience`` (1 - weighted severity) and an
   ``adversarial_ev`` (the model's expected value haircut by resilience). A
   thesis "survives" only if it stays resilient AND no single attack is
   critical (severity >= 0.8).

2. ``monte_carlo`` — perturbs the payoff inputs (win prob, upside, downside) to
   report the probability the bet still has positive expected value once you
   admit you don't know the inputs precisely. This is the adversarial test on
   the *assumptions*, not just the point estimate.

3. ``llm_redteam`` — OPTIONAL. Routes the thesis to one or more real LLMs (via
   the repo's ``call_llm``) as independent devil's advocates and aggregates
   their objections. Degrades gracefully to an empty result if no API keys.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from serenity_chokepoint.chokepoint_data import Node
from serenity_chokepoint.scoring import ChokepointScore, _payoff, score_node


# --------------------------------------------------------------------------- #
# Deterministic attack vectors
# --------------------------------------------------------------------------- #
@dataclass
class Attack:
    name: str
    severity: float          # 0..1 (1 = thesis-breaking)
    weight: float            # importance of this vector
    objection: str           # the red-team's strongest point
    rebuttal: str            # the structural blue-team counter


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# China-exposed material/substrate layers carry export-control / weaponisation risk.
_GEO_TICKERS = {"AXTI", "IQE", "VNP", "MP", "INPACT", "SOI"}


def _attacks(n: Node) -> list[Attack]:
    a: list[Attack] = []

    # 1. Valuation already prices the ramp in (the framework's own admitted weakness).
    live_ev_rev = n.fwd_ev_sales * n.ramp_rev_mult  # implied trailing EV/Sales
    sev = _clip((live_ev_rev - 15) / 60)             # 15x ~ fine, 75x ~ extreme
    a.append(Attack(
        "valuation_priced_in", sev, 1.2,
        f"Implied EV/Sales ~{live_ev_rev:.0f}x; much of the {n.ramp_rev_mult:.1f}x ramp may already be discounted.",
        "Venture-style: capacity-locked chokepoints re-rate on ASP + volume; multiple compresses as revenue lands.",
    ))

    # 2. Supply can respond / a second source qualifies — the choke erodes.
    sev = _clip((1 - n.irreplaceability) * 0.8 + max(0.0, n.capacity_cagr - 0.20) * 2)
    a.append(Attack(
        "supply_elasticity", sev, 1.1,
        f"Irreplaceability only {n.irreplaceability:.2f} and capacity grows {n.capacity_cagr*100:.0f}%/yr — a 2nd source could relieve the choke.",
        f"Qualification cycle is {n.qual_cycle_months}mo; material-science + customer lock-in keep entrants years behind.",
    ))

    # 3. Tech-path risk: CPO loses to pluggables / copper / a rival architecture.
    sev = _clip(n.tech_path_risk * 1.1)
    a.append(Attack(
        "tech_path_risk", sev, 1.0,
        "The CPO/silicon-photonics path could slip or lose to pluggables/co-packaged copper, stranding the node.",
        "NVDA/AVGO/MRVL capex + physics of power-per-bit make the optical transition structural, not optional.",
    ))

    # 4. Crowding: already discovered, asymmetry gone.
    inst = n.inst_ownership
    cover = n.analyst_coverage
    sev = _clip((inst - 0.45) / 0.45 * 0.7 + min(cover, 25) / 25 * 0.4)
    a.append(Attack(
        "already_discovered", sev, 1.0,
        f"Institutions hold {inst*100:.0f}% with {cover} analysts covering — the information-asymmetry edge is largely gone.",
        "Even discovered chokepoints re-rate on capacity-allocation pricing power once volume ramps.",
    ))

    # 5. Financing / dilution risk eats the equity holder.
    sev = _clip(n.dilution_risk * 1.05)
    a.append(Attack(
        "dilution_financing", sev, 0.9,
        "Cash burn ahead of ramp invites ATM/equity raises that dilute the upside (cf. avoided $IREN).",
        "M&A optionality + pre-paid capacity deals can fund the ramp without a punitive raise.",
    ))

    # 6. Liquidity / microcap fragility.
    if n.market_cap_b > 0:
        sev = _clip((1.0 - n.market_cap_b / 3.0) * 0.7) if n.market_cap_b < 3.0 else 0.1
    else:
        sev = 1.0
    a.append(Attack(
        "liquidity_microcap", sev, 0.7,
        f"~${n.market_cap_b:.2f}B cap: 15-25% daily swings, hard to exit size, vulnerable to a single bad print.",
        "Position-size with deep-fractional Kelly and hold through volume-ramp validation, not on noise.",
    ))

    # 7. Customer / qualification concentration reversal.
    sev = _clip(0.55 if n.qualified else 0.25) * _clip(n.top3_share + 0.1)
    a.append(Attack(
        "customer_concentration", sev * 0.6, 0.8,
        "Demand concentrates in 1-2 hyperscalers; a design-loss or push-out at one customer guts the ramp.",
        "Long qualification cycles cut both ways — incumbency makes a designed-in supplier very sticky.",
    ))

    # 8. Geopolitical / export-control risk on the materials layers.
    if n.ticker in _GEO_TICKERS or n.layer in (4, 5):
        sev = 0.55 if n.ticker in _GEO_TICKERS else 0.35
        a.append(Attack(
            "geopolitical", sev, 0.8,
            "China gallium/indium/rare-earth export controls (or Taiwan risk) can whipsaw both supply and the multiple.",
            "Western-sourced feedstock is precisely why this node is strategic — controls tighten the choke in its favour.",
        ))

    return a


@dataclass
class AdversarialResult:
    ticker: str
    resilience: float                 # 0..1 (1 = bulletproof)
    adversarial_ev: float             # expected value haircut by resilience
    survives: bool
    top_objection: str
    critical_flags: list[str]
    attacks: list[Attack] = field(default_factory=list)
    mc_prob_positive_ev: float | None = None


def redteam_node(node: Node, cp: ChokepointScore | None = None) -> AdversarialResult:
    cp = cp or score_node(node)
    attacks = _attacks(node)

    wsum = sum(at.weight for at in attacks) or 1.0
    weighted_sev = sum(at.severity * at.weight for at in attacks) / wsum
    resilience = round(1.0 - weighted_sev, 3)

    critical = [at.name for at in attacks if at.severity >= 0.8]
    # Survives multi-round red-team: resilient overall AND no single critical hole
    # AND the base case is still positive-EV.
    survives = resilience >= 0.45 and not critical and cp.expected_value > 0

    adversarial_ev = round(cp.expected_value * resilience, 3)
    top = max(attacks, key=lambda at: at.severity * at.weight)

    return AdversarialResult(
        ticker=node.ticker,
        resilience=resilience,
        adversarial_ev=adversarial_ev,
        survives=survives,
        top_objection=f"[{top.name}] {top.objection}",
        critical_flags=critical,
        attacks=sorted(attacks, key=lambda at: at.severity * at.weight, reverse=True),
    )


# --------------------------------------------------------------------------- #
# Monte-Carlo robustness on the payoff assumptions
# --------------------------------------------------------------------------- #
def monte_carlo(node: Node, n: int = 4000, seed: int = 7) -> dict:
    """Perturb win prob / upside / downside and report P(EV > 0) and percentiles."""
    rng = random.Random(seed)
    cp = score_node(node)
    base = _payoff(node, cp.chokepoint_score)

    evs: list[float] = []
    for _ in range(n):
        # multiplicative/additive noise reflecting genuine input uncertainty
        wp = _clip(base["win_prob"] + rng.gauss(0, 0.10), 0.05, 0.95)
        up = max(1.05, base["upside_mult"] * (1 + rng.gauss(0, 0.25)))
        dn = _clip(base["downside_loss"] * (1 + rng.gauss(0, 0.20)), 0.05, 0.98)
        evs.append(wp * (up - 1.0) - (1 - wp) * dn)

    evs.sort()
    pos = sum(1 for e in evs if e > 0) / len(evs)

    def pct(p: float) -> float:
        return round(evs[min(len(evs) - 1, int(p * len(evs)))], 3)

    return {
        "ticker": node.ticker,
        "prob_positive_ev": round(pos, 3),
        "ev_p10": pct(0.10),
        "ev_p50": pct(0.50),
        "ev_p90": pct(0.90),
    }


def redteam_node_full(node: Node) -> AdversarialResult:
    """Red-team + attach Monte-Carlo P(EV>0)."""
    res = redteam_node(node)
    res.mc_prob_positive_ev = monte_carlo(node)["prob_positive_ev"]
    # Tighten the survival gate with the simulation: a fragile distribution fails
    # even if the point estimate survives.
    if res.mc_prob_positive_ev is not None and res.mc_prob_positive_ev < 0.55:
        res.survives = False
    return res


# --------------------------------------------------------------------------- #
# Optional: real multi-LLM devil's advocate
# --------------------------------------------------------------------------- #
def llm_redteam(node: Node, models: list[tuple[str, str]] | None = None) -> dict:
    """Route the thesis to one or more real LLMs as independent devil's advocates.

    ``models`` is a list of (model_name, model_provider) tuples. Returns a dict
    of provider -> objection text. Degrades to {} (with a 'note') if no keys /
    infra. This is opt-in (CLI --llm) and is the faithful Step-3 reproduction:
    multiple independent models, harshest critique, only repo if it survives.
    """
    try:
        from pydantic import BaseModel
        from langchain_core.prompts import ChatPromptTemplate
        from serenity_chokepoint._optional_llm import call_llm  # optional; absent by default -> graceful degrade
    except Exception as e:  # infra not installed (e.g. running the engine standalone)
        return {"note": f"LLM infra unavailable ({e}); deterministic red-team only.", "objections": {}}

    class Critique(BaseModel):
        fatal_flaws: list[str]
        verdict: str  # "survives" | "fails"
        confidence: float

    models = models or [("gpt-4o", "OpenAI"), ("claude-sonnet-4-6", "Anthropic"), ("gemini-2.0-flash", "Gemini")]
    cp = score_node(node)
    det = redteam_node_full(node)

    template = ChatPromptTemplate.from_messages([
        ("system",
         "You are the harshest possible Devil's Advocate red-teaming an AI supply-chain 'chokepoint' long thesis. "
         "Find the technical holes, alternative-path risks, valuation bias and geopolitical risks. Be specific and brutal. "
         "Only conclude 'survives' if the thesis genuinely withstands your strongest attacks."),
        ("human",
         "Ticker {t} ({name}), layer {layer}.\nThesis: {thesis}\n"
         "Structural scores: chokepoint={cp}, odds={odds}, EV={ev}, win_prob={wp}.\n"
         "Deterministic red-team already found: {auto}\n\n"
         "Return JSON: {{\"fatal_flaws\": [..], \"verdict\": \"survives|fails\", \"confidence\": float}}"),
    ])
    prompt = template.invoke({
        "t": node.ticker, "name": node.name, "layer": node.layer, "thesis": node.thesis,
        "cp": cp.chokepoint_score, "odds": cp.odds_ratio, "ev": cp.expected_value, "wp": cp.win_prob,
        "auto": det.top_objection,
    })

    objections: dict[str, dict] = {}
    for model_name, provider in models:
        try:
            out = call_llm(
                prompt=prompt, model_name=model_name, model_provider=provider,
                pydantic_model=Critique, agent_name="serenity_adversarial",
                default_factory=lambda: Critique(fatal_flaws=["(no response)"], verdict="fails", confidence=0.0),
            )
            objections[provider] = {"verdict": out.verdict, "confidence": out.confidence, "fatal_flaws": out.fatal_flaws}
        except Exception as e:
            objections[provider] = {"error": str(e)[:160]}

    survived = sum(1 for v in objections.values() if v.get("verdict") == "survives")
    return {
        "objections": objections,
        "models_polled": len(models),
        "consensus_survives": survived >= max(1, len(models) // 2 + 1),
        "note": None if any("error" not in v for v in objections.values()) else "all models errored (likely missing API keys)",
    }
