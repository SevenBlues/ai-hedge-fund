"""
Chokepoint scoring + asymmetric-odds engine.

Two distinct things are computed per node, mirroring Serenity's process:

1. Chokepoint Score (0..100) — *is this a real bottleneck?*  A weighted blend of
   the six criteria from the framework (Step 2): supply concentration, physical
   irreplaceability, demand/supply imbalance, qualification barrier, information
   asymmetry, and catalyst/optionality bonus.

2. Asymmetric payoff (Step 4/5) — *is it a high-odds bet?*  We translate the
   structural moat into a win-probability, model the upside multiple (TAM/ramp)
   vs a downside-loss fraction (dilution + valuation stretch + tech-path +
   liquidity risk), then compute an odds ratio, expected value and a
   volatility-/Kelly-adjusted suggested position weight (Step 5).

The output is intentionally transparent: every sub-score and its contribution
is returned so a human can audit (and override) the model — the framework
insists the model only *assists* domain judgement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from serenity_chokepoint.chokepoint_data import Node, get_universe


# Weights for the six Chokepoint-Score pillars. Sum = 100.
WEIGHTS = {
    "supply_concentration": 22,
    "irreplaceability": 22,
    "demand_supply_gap": 16,
    "qualification_barrier": 16,
    "information_asymmetry": 14,
    "catalyst_optionality": 10,
}


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# --------------------------------------------------------------------------- #
# Pillar sub-scores (each returns 0..1)
# --------------------------------------------------------------------------- #
def _supply_concentration(n: Node) -> float:
    """Top-1-3 share, rewarded non-linearly above the 70% chokepoint line.

    Also folds in an HHI-style penalty for fragmentation: a 70%+ top-3 share is
    the framework's hard gate, so we curve sharply once it is cleared.
    """
    s = n.top3_share
    # Below 0.5 -> weak; 0.7 is the gate; >0.7 curves toward 1.0.
    if s <= 0.5:
        return _clip(s * 0.6)            # max 0.30 if fragmented
    if s <= 0.7:
        return _clip(0.30 + (s - 0.5) * 1.5)  # 0.30 -> 0.60 across 0.5..0.7
    return _clip(0.60 + (s - 0.7) * 1.33)     # 0.60 -> ~0.99 across 0.7..1.0


def _irreplaceability(n: Node) -> float:
    """Physical / material-science substitution difficulty, lengthened by a
    long qualification cycle (you can't just spin up a second source)."""
    qual = _clip(n.qual_cycle_months / 24.0)
    return _clip(0.7 * n.irreplaceability + 0.3 * qual)


def _demand_supply_gap(n: Node) -> float:
    """Demand elasticity >> supply elasticity. The wider AI end-market CAGR runs
    ahead of the node's realistic capacity CAGR, the tighter the choke."""
    gap = n.demand_cagr - n.capacity_cagr
    # 0 gap -> 0 ; a 40pt gap -> ~1.0
    return _clip(gap / 0.40)


def _qualification_barrier(n: Node) -> float:
    """Already designed-in + long cert cycle => competitors are years behind."""
    base = 0.55 if n.qualified else 0.0
    return _clip(base + 0.45 * _clip(n.qual_cycle_months / 24.0))


def _information_asymmetry(n: Node) -> float:
    """Undiscovered = small cap + low institutional ownership + thin coverage.
    This is where the alpha lives in the framework."""
    if n.market_cap_b <= 0:
        return 0.0  # non-investable structural node
    # Smaller cap = more asymmetry. <$0.5B ~ 1.0, $5B ~ 0.3, >$20B ~ 0.
    cap_score = _clip(1.0 - math.log10(max(n.market_cap_b, 0.05) / 0.3) / 2.2)
    inst_score = _clip(1.0 - n.inst_ownership / 0.6)        # <30% inst is ideal
    cover_score = _clip(1.0 - n.analyst_coverage / 15.0)    # thin coverage
    return _clip(0.5 * cap_score + 0.3 * inst_score + 0.2 * cover_score)


def _catalyst_optionality(n: Node) -> float:
    """Bonus: insider buying, squeeze fuel, M&A premium optionality, vertical
    integration / pricing-power expansion."""
    score = 0.0
    score += 0.30 if n.insider_buying else 0.0
    score += 0.20 * _clip(n.short_interest / 0.25)
    score += 0.30 * n.ma_potential
    score += 0.20 * n.vertical_integ
    return _clip(score)


PILLAR_FUNCS = {
    "supply_concentration": _supply_concentration,
    "irreplaceability": _irreplaceability,
    "demand_supply_gap": _demand_supply_gap,
    "qualification_barrier": _qualification_barrier,
    "information_asymmetry": _information_asymmetry,
    "catalyst_optionality": _catalyst_optionality,
}


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #
@dataclass
class ChokepointScore:
    ticker: str
    name: str
    layer: int
    chokepoint_score: float                 # 0..100
    pillars: dict[str, float]               # raw 0..1 sub-scores
    contributions: dict[str, float]         # weighted points contributed
    # Asymmetric payoff
    win_prob: float                         # 0..1 structural win probability
    upside_mult: float                      # x return if thesis plays out
    downside_loss: float                    # fractional loss if it breaks (0..1)
    odds_ratio: float                       # 赔率: upside_mult / downside_loss
    expected_value: float                   # E[return] per $1, ev-weighted
    kelly_weight: float                     # suggested portfolio weight (capped)
    investable: bool
    thesis: str = ""
    flags: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Asymmetric payoff model
# --------------------------------------------------------------------------- #
def _payoff(n: Node, chokepoint_score: float) -> dict:
    """Map structure -> probability and model the asymmetric return.

    Win probability is anchored by the structural moat (chokepoint score) and
    nudged by qualification status; it is intentionally bounded well under 1 to
    respect the framework's "not 100% win rate / DYOR" humility.
    """
    cp = chokepoint_score / 100.0
    win_prob = _clip(0.30 + 0.45 * cp + (0.05 if n.qualified else -0.05), 0.10, 0.85)

    # Upside: the ramp multiple, gently discounted by how much is already priced
    # in (forward EV/Sales) — venture-style, not TTM P/S (Step 4).
    valuation_drag = _clip(n.fwd_ev_sales / 12.0)            # 12x fwd EV/S ~ fully priced
    upside_mult = max(1.1, n.ramp_rev_mult * (1.0 - 0.5 * valuation_drag))

    # Downside: blended structural-break loss.
    liquidity_risk = _clip(1.0 - math.log10(max(n.market_cap_b, 0.05) / 0.2) / 2.5) if n.market_cap_b > 0 else 1.0
    downside_loss = _clip(
        0.30
        + 0.25 * n.tech_path_risk
        + 0.25 * n.dilution_risk
        + 0.20 * liquidity_risk
        - 0.20 * (n.irreplaceability - 0.5),  # a true monopoly cushions the fall
        0.15, 0.95,
    )

    odds_ratio = upside_mult / downside_loss
    # Expected per-$1 return: win -> (upside-1) gain ; lose -> -downside.
    expected_value = win_prob * (upside_mult - 1.0) - (1.0 - win_prob) * downside_loss

    # Kelly fraction for a win/loss bet: f* = p/a - q/b
    #   b = fractional gain on win = upside_mult - 1 ; a = fractional loss = downside_loss
    b = max(upside_mult - 1.0, 1e-6)
    a = max(downside_loss, 1e-6)
    kelly = win_prob / a - (1.0 - win_prob) / b
    # Deep-fractional (1/10) Kelly, floored at 0, then hard-capped at 10% for a
    # concentrated-but-diversified 10-20 name book on illiquid small caps that
    # are highly correlated to one AI-capex factor (Step 5). The deep fraction
    # keeps sizes differentiated instead of everything pinning to the cap.
    kelly_weight = _clip(0.10 * kelly, 0.0, 0.10)

    return dict(
        win_prob=win_prob,
        upside_mult=upside_mult,
        downside_loss=downside_loss,
        odds_ratio=odds_ratio,
        expected_value=expected_value,
        kelly_weight=kelly_weight,
    )


def score_node(n: Node) -> ChokepointScore:
    pillars = {name: f(n) for name, f in PILLAR_FUNCS.items()}
    contributions = {name: pillars[name] * WEIGHTS[name] for name in WEIGHTS}
    cp_score = sum(contributions.values())

    payoff = _payoff(n, cp_score)

    flags: list[str] = []
    if n.top3_share >= 0.70:
        flags.append("CONCENTRATED(>70%)")
    if n.market_cap_b > 0 and n.market_cap_b < 1.0 and n.inst_ownership < 0.30:
        flags.append("UNDISCOVERED")
    if n.qual_cycle_months >= 18 and n.qualified:
        flags.append("MOAT:LONG-QUAL")
    if n.ma_potential >= 0.5:
        flags.append("M&A-TARGET")
    if n.dilution_risk >= 0.5:
        flags.append("DILUTION-RISK")
    if n.tech_path_risk >= 0.45:
        flags.append("TECH-PATH-RISK")

    return ChokepointScore(
        ticker=n.ticker,
        name=n.name,
        layer=n.layer,
        chokepoint_score=round(cp_score, 1),
        pillars={k: round(v, 3) for k, v in pillars.items()},
        contributions={k: round(v, 2) for k, v in contributions.items()},
        win_prob=round(payoff["win_prob"], 3),
        upside_mult=round(payoff["upside_mult"], 2),
        downside_loss=round(payoff["downside_loss"], 3),
        odds_ratio=round(payoff["odds_ratio"], 2),
        expected_value=round(payoff["expected_value"], 3),
        kelly_weight=round(payoff["kelly_weight"], 4),
        investable=n.market_cap_b > 0,
        thesis=n.thesis,
        flags=flags,
    )


def score_universe(nodes: list[Node] | None = None) -> list[ChokepointScore]:
    nodes = nodes if nodes is not None else get_universe()
    return [score_node(n) for n in nodes]


def rank(scores: list[ChokepointScore], by: str = "expected_value", investable_only: bool = True) -> list[ChokepointScore]:
    """Rank candidates. ``by`` in {expected_value, odds_ratio, chokepoint_score, kelly_weight}."""
    pool = [s for s in scores if (s.investable or not investable_only)]
    return sorted(pool, key=lambda s: getattr(s, by), reverse=True)
