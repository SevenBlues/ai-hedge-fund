"""
One-page thesis — the full Serenity method for a single name.

Synthesises the three lenses into one verdict:

    MOAT   (structural chokepoint score + pillars + flags)     — what you're betting on
    TIMING (growth / ramp-inflection analysis)                 — whether the ramp has started
    RISK   (adversarial red-team + Monte-Carlo)                — whether it survives attack

The combined verdict reads the moat × timing × survival matrix, mirroring how
Serenity actually decides: a strong moat whose ramp is just inflecting and that
survives the red-team is the PRIME setup; a strong moat that hasn't ramped yet is
POSITIONED EARLY (buy the moat, watch for the inflection); anything that fails the
red-team is out, however good the story.

Educational; not financial advice.
"""

from __future__ import annotations

from serenity_chokepoint.adversarial import redteam_node_full
from serenity_chokepoint.chokepoint_data import LAYERS, by_ticker
from serenity_chokepoint.growth import analyze_growth
from serenity_chokepoint.scoring import score_node

_RAMP_UP = ("EARLY RAMP", "ACCELERATING", "SCALING")
_RAMP_DOWN = ("DECELERATING", "CONTRACTING")


def _verdict(curated: bool, choke: float, stage: str, growth_score: float,
             survives: bool, top_objection: str) -> tuple[str, str]:
    """Return (headline, one-line rationale)."""
    if not curated:
        return ("❓ NOT A CURATED CHOKEPOINT",
                "No human-researched structural data for this name — establish the moat first (see REPRODUCE.md). Growth/momentum shown for context only.")
    if not survives:
        return ("⛔ FAILS VALIDATION",
                f"The thesis does not survive the red-team: {top_objection}")
    ramp_up = any(k in stage for k in _RAMP_UP)
    ramp_down = any(k in stage for k in _RAMP_DOWN)
    if choke >= 70 and ramp_up:
        return ("🎯 PRIME SETUP",
                "Strong structural moat, the volume ramp is inflecting, and it survives the red-team. This is the setup.")
    if choke >= 65 and not ramp_up and not ramp_down:
        return ("⏳ POSITIONED EARLY",
                "Strong moat, but the ramp isn't in the numbers yet — buy the moat ahead of the inflection and watch growth turn.")
    if choke >= 65 and ramp_down:
        return ("⚠️ MOAT INTACT, GROWTH FADING",
                "The chokepoint holds but growth is decelerating — re-rating catalyst is further out; size smaller / wait.")
    if choke >= 60 and ramp_up:
        return ("📈 SOLID, RAMPING",
                "Decent chokepoint with the ramp underway and survives the red-team — a real candidate, just not a monopoly.")
    if choke < 55:
        return ("🟠 WEAK CHOKEPOINT",
                "Not concentrated/irreplaceable enough to be a true bottleneck — the structural edge is thin.")
    return ("🟢 WATCHLIST",
            "Passes the gate but isn't a standout on either moat or timing — keep it on the radar.")


def thesis_report(ticker: str) -> str:
    t = ticker.upper()
    universe = by_ticker()
    curated = t in universe

    out = ["=" * 84, f"SERENITY THESIS — {t}   (moat × timing × risk)", "=" * 84]

    # ---- MOAT ----
    cp = red = None
    if curated:
        node = universe[t]
        cp = score_node(node)
        red = redteam_node_full(node)
        out.append(f"\n▍ MOAT  — structural chokepoint     score {cp.chokepoint_score:.0f}/100")
        out.append(f"   {node.name}  ·  Layer {node.layer} {LAYERS.get(node.layer,'?')}")
        out.append(f"   thesis: {node.thesis}")
        top_pillars = sorted(cp.pillars.items(), key=lambda kv: kv[1], reverse=True)[:3]
        out.append("   strongest pillars: " + ", ".join(f"{k} {v:.2f}" for k, v in top_pillars))
        out.append(f"   flags: {', '.join(cp.flags) or '—'}")
    else:
        out.append("\n▍ MOAT  — structural chokepoint     n/a")
        out.append(f"   {t} is not in the curated chokepoint universe.")
        out.append("   The structural moat needs human research (supply share, qualification, irreplaceability).")

    # ---- TIMING ----
    g = analyze_growth(t)
    out.append(f"\n▍ TIMING — growth / ramp inflection   score {g.growth_score:.0f}/100" if g.ok
               else "\n▍ TIMING — growth                   n/a")
    if g.ok:
        out.append(f"   stage: {g.ramp_stage}")
        out.append("   " + "; ".join(g.notes[:5]))
    else:
        out.append(f"   {g.error}")

    # ---- RISK ----
    if curated and red is not None:
        out.append(f"\n▍ RISK  — adversarial red-team       resilience {red.resilience:.2f}  P(EV>0) {(red.mc_prob_positive_ev or 0)*100:.0f}%")
        out.append(f"   survives multi-round red-team: {'YES' if red.survives else 'NO'}")
        out.append(f"   strongest objection: {red.top_objection}")
        if cp is not None:
            out.append(f"   odds: win {cp.win_prob*100:.0f}%  upside {cp.upside_mult:.1f}x  E[V] {cp.expected_value:+.2f}")
    else:
        out.append("\n▍ RISK  — adversarial red-team       n/a (needs curated structural data)")

    # ---- VERDICT ----
    headline, why = _verdict(
        curated,
        cp.chokepoint_score if cp else 0.0,
        g.ramp_stage if g.ok else "",
        g.growth_score if g.ok else 0.0,
        red.survives if red else False,
        red.top_objection if red else "",
    )
    out.append("\n" + "─" * 84)
    out.append(f"  VERDICT: {headline}")
    out.append(f"  {why}")
    out.append("─" * 84)
    out.append("Method: structure (chokepoint) × timing (growth) × survival (red-team). Not financial advice.")
    out.append("=" * 84)
    return "\n".join(out)
