"""
Proxy chokepoint score — what we CAN say about a name that isn't in the curated
universe, without pretending to know what we can't.

The full Chokepoint Score has six pillars. Five of them are *structural* —
top-3 supply share, physical irreplaceability, demand-vs-capacity gap,
qualification barrier — and **no public market feed can know them**. They are the
analyst's job (that is the whole thesis). Exactly ONE pillar is mechanically
screenable from market data:

    information_asymmetry  = small cap + low institutional ownership + thin
                             analyst coverage   (i.e. "is it still undiscovered?")

So this module computes that one pillar honestly from live Yahoo data, reports
the short-interest slice of the catalyst pillar as a side clue, and **refuses to
fabricate the four structural pillars** — it lists them as UNKNOWN with the
weight each carries, so the user sees exactly how much of the score is still
missing (76 of 100 points) and what to go research.

The practical payoff: it turns "not in the universe → n/a" into a real triage
signal. A tiny, unloved, thinly-covered name *fits the profile* and is worth the
structural research; a $50B, 85%-institutional, 20-analyst name is already
discovered — the opposite of Serenity's sweet spot — and you can move on.

Educational; not financial advice.
"""

from __future__ import annotations

from dataclasses import dataclass

from serenity_chokepoint.chokepoint_data import Node
from serenity_chokepoint.live_data import fetch_live_quote
from serenity_chokepoint.scoring import WEIGHTS, _information_asymmetry, _clip


# The four pillars that cannot be screened — shown so the user knows what's missing.
STRUCTURAL_PILLARS = {
    "supply_concentration": "top-3 supply share (>70% is the chokepoint gate)",
    "irreplaceability": "material-science moat / no viable second source",
    "demand_supply_gap": "AI end-market CAGR running ahead of node capacity CAGR",
    "qualification_barrier": "designed-in already + length of the cert cycle",
}


@dataclass
class ProxyScore:
    ticker: str
    ok: bool
    info_asym: float = 0.0           # 0..1, the one reliably-screenable pillar
    catalyst_short: float = 0.0      # 0..1, short-interest slice of catalyst only
    market_cap_b: float | None = None
    inst_ownership: float | None = None
    analyst_coverage: int | None = None
    short_interest: float | None = None
    error: str | None = None

    @property
    def observable_points(self) -> float:
        """Score-points (out of 100) we can actually justify from market data.
        Only information_asymmetry is complete; catalyst is partial (short int only)."""
        cat_internal_short_weight = 0.20      # short interest is 20% of the catalyst pillar
        return (self.info_asym * WEIGHTS["information_asymmetry"]
                + self.catalyst_short * WEIGHTS["catalyst_optionality"] * cat_internal_short_weight)

    @property
    def missing_weight(self) -> int:
        """How many of the 100 score-points are structural / unknowable here."""
        return sum(WEIGHTS[p] for p in STRUCTURAL_PILLARS)


def _node_for_quote(q) -> Node:
    """Minimal Node carrying ONLY the market fields; structural fields are neutral
    placeholders never read by _information_asymmetry."""
    return Node(
        ticker=q.ticker, name=q.ticker, layer=0,
        top3_share=0.0, irreplaceability=0.0, qual_cycle_months=0, qualified=False,
        market_cap_b=q.market_cap_b or 0.0,
        inst_ownership=q.inst_ownership if q.inst_ownership is not None else 0.5,
        analyst_coverage=q.analyst_coverage or 0,
        demand_cagr=0.0, capacity_cagr=0.0, ramp_rev_mult=1.0, fwd_ev_sales=0.0,
        dilution_risk=0.5, tech_path_risk=0.5,
        short_interest=q.short_interest or 0.0,
    )


def proxy_chokepoint(ticker: str) -> ProxyScore:
    q = fetch_live_quote(ticker.upper())
    if not q.ok:
        return ProxyScore(ticker.upper(), ok=False, error=q.error or "no market data")
    node = _node_for_quote(q)
    info = _information_asymmetry(node)
    cat_short = _clip((q.short_interest or 0.0) / 0.25)
    return ProxyScore(
        ticker=ticker.upper(), ok=True,
        info_asym=info, catalyst_short=cat_short,
        market_cap_b=q.market_cap_b, inst_ownership=q.inst_ownership,
        analyst_coverage=q.analyst_coverage, short_interest=q.short_interest,
    )


def undiscovered_verdict(info_asym: float) -> tuple[str, str]:
    """Translate the information_asymmetry pillar into a triage call."""
    if info_asym >= 0.6:
        return ("✅ FITS THE PROFILE",
                "small / lightly-owned / thinly-covered — this is the undiscovered sweet spot. Worth doing the structural research.")
    if info_asym >= 0.35:
        return ("🟡 BORDERLINE",
                "partly discovered — some asymmetry left, but the market is starting to notice. Research only if the moat is exceptional.")
    return ("🔴 ALREADY DISCOVERED",
            "large-cap / well-owned / well-covered — the OPPOSITE of Serenity's overlooked-bottleneck sweet spot. The easy alpha is gone.")


def moat_lines(ps: ProxyScore) -> list[str]:
    """Compact MOAT-section lines for the thesis report (proxy branch)."""
    if not ps.ok:
        return [f"   proxy unavailable ({ps.error}); structural moat needs human research."]
    head, why = undiscovered_verdict(ps.info_asym)
    mc = f"${ps.market_cap_b:.1f}B" if ps.market_cap_b else "n/a"
    inst = f"{ps.inst_ownership*100:.0f}%" if ps.inst_ownership is not None else "n/a"
    cov = ps.analyst_coverage if ps.analyst_coverage is not None else "n/a"
    return [
        f"   screenable pillar — information asymmetry: {ps.info_asym:.2f}  {head}",
        f"     ({why})",
        f"     market cap {mc} · institutional {inst} · analysts {cov}",
        f"   STILL UNKNOWN (need human research, {ps.missing_weight}/100 score-weight): "
        + ", ".join(STRUCTURAL_PILLARS),
    ]


def text_report(ticker: str) -> str:
    ps = proxy_chokepoint(ticker)
    W = 82
    out = ["=" * W, f"SERENITY PROXY CHOKEPOINT — {ps.ticker}   (market-observable estimate only)", "=" * W]
    if not ps.ok:
        return "\n".join(out + [f"[proxy] {ps.error}",
                                "Try a US-listed ticker, or run `serenity growth <T>` for the timing lens."])

    out.append("⚠️  PARTIAL by design. Only 1 of 6 pillars (information asymmetry) is screenable from")
    out.append("    market data. The 4 structural pillars below are UNKNOWN — they need human research.")
    out.append("    Do NOT treat this as a real chokepoint score, and do NOT trade on it.\n")

    head, why = undiscovered_verdict(ps.info_asym)
    out.append("▍ SCREENABLE — information asymmetry (\"is it still undiscovered?\")")
    out.append(f"     pillar score : {ps.info_asym:.2f} / 1.00   {head}")
    out.append(f"     {why}")
    mc = f"${ps.market_cap_b:.1f}B" if ps.market_cap_b else "n/a"
    out.append(f"     inputs       : market cap {mc} · "
               f"institutional {ps.inst_ownership*100:.0f}% · analysts {ps.analyst_coverage}"
               if ps.inst_ownership is not None else f"     inputs       : market cap {mc}")
    si = f"{ps.short_interest*100:.1f}%" if ps.short_interest is not None else "n/a"
    out.append(f"     side clue    : short interest {si} (one slice of the catalyst pillar)\n")

    out.append(f"▍ UNKNOWN — structural pillars ({ps.missing_weight} of 100 score-points, human research):")
    for p, desc in STRUCTURAL_PILLARS.items():
        out.append(f"     ? {p:<22} (weight {WEIGHTS[p]:>2})  {desc}")

    out.append("")
    out.append("-" * W)
    out.append(f"  Market-observable points justified: {ps.observable_points:.1f} / 100  "
               f"(the other {100 - ps.observable_points:.0f} need research)")
    out.append(f"  TRIAGE: {head} — "
               + ("go do the structural research (REPRODUCE.md)." if ps.info_asym >= 0.6
                  else "probably not a Serenity-style setup; spend your research time elsewhere."))
    out.append("  Then: `serenity growth " + ps.ticker + "` for timing. NOT financial advice.")
    out.append("=" * W)
    return "\n".join(out)
