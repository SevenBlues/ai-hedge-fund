"""
The product: a research-driven, high-conviction stock pool.

This is the whole point of the engine, stripped of trading-system noise.
The logic mirrors how the framework actually picks names:

    deep research (the curated, supply-chain-mapped universe)
        -> CERTAINTY GATE  : keep only names whose win is as structurally
                             certain as possible (high chokepoint moat, survives
                             the adversarial red-team, high Monte-Carlo P(EV>0))
        -> RETURN MAXIMISER: among those, rank and concentrate by expected
                             return so the pool maximises upside *given* the
                             win-rate condition.

Output is a readable investment brief — the final pool, per-name thesis,
certainty, upside and a conviction weight — not a backtest dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass

from serenity_chokepoint.adversarial import redteam_node_full
from serenity_chokepoint.chokepoint_data import LAYERS, get_universe
from serenity_chokepoint.scoring import score_node


# ---- the certainty gate (win-rate as确定 as possible) ----------------------- #
MIN_WIN_PROB = 0.60        # structural win probability
MIN_CHOKEPOINT = 60.0      # must be a real bottleneck
MIN_PROB_POSITIVE_EV = 0.60  # Monte-Carlo: positive-EV in >=60% of draws
# (adversarial "survives" is also required — resilient + no critical hole)


@dataclass
class Pick:
    ticker: str
    name: str
    layer: int
    layer_name: str
    thesis: str
    # certainty
    win_prob: float
    prob_positive_ev: float
    chokepoint_score: float
    resilience: float
    # return
    upside_mult: float
    exp_return_per_dollar: float   # win_prob*upside + (1-win_prob)*(1-downside) - 1
    conviction_weight: float       # normalised, return-maximising within the pool
    tier: int
    key_catalyst: str
    key_risk: str


def _exp_return(win_prob: float, upside: float, downside: float) -> float:
    """Expected terminal value per $1, minus 1 = expected return."""
    return win_prob * upside + (1 - win_prob) * (1 - downside) - 1.0


def select_pool(nodes=None, live: bool = False) -> list[Pick]:
    if nodes is None:
        nodes = get_universe()
        if live:
            from serenity_chokepoint.live_data import enrich_universe
            nodes, _ = enrich_universe(nodes)

    picks: list[Pick] = []
    for n in nodes:
        if n.market_cap_b <= 0:
            continue
        cp = score_node(n)
        red = redteam_node_full(n)

        # --- CERTAINTY GATE ---
        passes = (
            red.survives
            and cp.win_prob >= MIN_WIN_PROB
            and cp.chokepoint_score >= MIN_CHOKEPOINT
            and (red.mc_prob_positive_ev or 0) >= MIN_PROB_POSITIVE_EV
        )
        if not passes:
            continue

        exp_ret = _exp_return(cp.win_prob, cp.upside_mult, cp.downside_loss)
        picks.append(Pick(
            ticker=n.ticker, name=n.name, layer=n.layer, layer_name=LAYERS.get(n.layer, "?"),
            thesis=n.thesis,
            win_prob=cp.win_prob, prob_positive_ev=red.mc_prob_positive_ev or 0.0,
            chokepoint_score=cp.chokepoint_score, resilience=red.resilience,
            upside_mult=cp.upside_mult, exp_return_per_dollar=exp_ret,
            conviction_weight=0.0,  # filled below
            tier=0,
            key_catalyst=", ".join(f for f in cp.flags if f in
                                   ("M&A-TARGET", "CONCENTRATED(>70%)", "MOAT:LONG-QUAL", "UNDISCOVERED")) or "volume ramp",
            key_risk=red.top_objection,
        ))

    if not picks:
        return []

    # --- RETURN MAXIMISER within the gate ---
    # Weight by certainty-scaled expected gain: win_prob * (upside - 1).
    # This concentrates capital on names that are BOTH high-win-rate and
    # high-return, which is exactly "maximise return given the win-rate holds".
    raw = {p.ticker: p.win_prob * max(p.upside_mult - 1.0, 0.0) for p in picks}
    total = sum(raw.values()) or 1.0
    # rank for tiering
    order = sorted(picks, key=lambda p: raw[p.ticker], reverse=True)
    for rank_i, p in enumerate(order):
        p.conviction_weight = round(raw[p.ticker] / total, 4)
        p.tier = 1 if rank_i < max(1, len(order) // 3) else (2 if rank_i < 2 * len(order) // 3 else 3)

    return order


def brief(nodes=None, live: bool = False) -> str:
    pool = select_pool(nodes=nodes, live=live)
    out = []
    out.append("=" * 100)
    out.append("SERENITY CHOKEPOINT — HIGH-CONVICTION STOCK POOL (deep research -> certainty gate -> max return)")
    out.append("=" * 100)
    if not pool:
        return "\n".join(out + ["No name clears the certainty gate on current data.", "=" * 100])

    out.append(f"Certainty gate: survives red-team + win_prob>={MIN_WIN_PROB:.0%} + chokepoint>={MIN_CHOKEPOINT:.0f} "
               f"+ P(EV>0)>={MIN_PROB_POSITIVE_EV:.0%}")
    out.append(f"Pool size: {len(pool)} names.   Objective: maximise return GIVEN the win-rate condition.\n")

    blended_win = sum(p.win_prob * p.conviction_weight for p in pool)
    blended_ret = sum(p.exp_return_per_dollar * p.conviction_weight for p in pool)

    for tier in (1, 2, 3):
        names = [p for p in pool if p.tier == tier]
        if not names:
            continue
        label = {1: "CORE (highest conviction)", 2: "BUILD", 3: "STARTER / watch"}[tier]
        out.append(f"── TIER {tier}: {label} " + "─" * (80 - len(label)))
        for p in names:
            out.append(f"  {p.ticker:<6} {p.name:<28} L{p.layer} {p.layer_name}")
            out.append(f"         weight {p.conviction_weight*100:>4.1f}%  | win {p.win_prob*100:.0f}%  "
                       f"P(EV>0) {p.prob_positive_ev*100:.0f}%  | upside {p.upside_mult:.1f}x  "
                       f"exp.return {p.exp_return_per_dollar*100:+.0f}%  | choke {p.chokepoint_score:.0f} resil {p.resilience:.2f}")
            out.append(f"         thesis : {p.thesis}")
            out.append(f"         catalyst: {p.key_catalyst}   |   top risk: {p.key_risk[:70]}")
        out.append("")

    out.append("─" * 100)
    out.append(f"POOL BLEND: weighted win-prob {blended_win*100:.0f}%   weighted expected return {blended_ret*100:+.0f}% "
               f"(per $1, if theses play out on the modelled horizon)")
    out.append("Hold high-conviction, concentrated; add on volume-ramp confirmation; this is research output, not advice.")
    out.append("=" * 100)
    return "\n".join(out)
