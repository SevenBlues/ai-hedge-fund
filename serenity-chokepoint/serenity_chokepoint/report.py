"""
Reporting: ranked screen table + matplotlib visual report.

Outputs:
  * a console/markdown table of the screening pool ranked by asymmetric odds
  * a 4-panel PNG: supply-chain dependency graph, chokepoint-score bars,
    odds-vs-conviction scatter, and the demand-vs-capacity projection.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import networkx as nx

from serenity_chokepoint.adversarial import redteam_node_full
from serenity_chokepoint.chokepoint_data import LAYERS, Node, get_universe
from serenity_chokepoint.demand_model import project
from serenity_chokepoint.scoring import ChokepointScore, rank, score_universe
from serenity_chokepoint.supply_chain import build_graph, structural_chokepoints


def markdown_table(scores: list[ChokepointScore], top: int = 15) -> str:
    ranked = rank(scores, by="expected_value")[:top]
    head = (
        "| # | Ticker | Layer | CP Score | Win% | Upside | Downside | Odds | E[V] | Kelly | Flags |\n"
        "|---|--------|-------|---------:|-----:|-------:|---------:|-----:|-----:|------:|-------|"
    )
    rows = []
    for i, s in enumerate(ranked, 1):
        rows.append(
            f"| {i} | **{s.ticker}** | L{s.layer} | {s.chokepoint_score:.1f} | "
            f"{s.win_prob*100:.0f}% | {s.upside_mult:.1f}x | {s.downside_loss*100:.0f}% | "
            f"{s.odds_ratio:.1f} | {s.expected_value:+.2f} | {s.kelly_weight*100:.1f}% | "
            f"{', '.join(s.flags) if s.flags else '—'} |"
        )
    return head + "\n" + "\n".join(rows)


def _layer_y(layer: int) -> float:
    # higher layer number (feedstock) at the bottom
    return float(max(LAYERS) - layer)


def render_png(path: str = "serenity_chokepoint_report.png", nodes: list[Node] | None = None) -> str:
    nodes = nodes if nodes is not None else get_universe()
    scores = score_universe(nodes)
    by_tkr = {s.ticker: s for s in scores}
    g = build_graph(nodes)
    central = structural_chokepoints(g)

    fig, axes = plt.subplots(2, 2, figsize=(20, 14))
    fig.suptitle(
        "Serenity Chokepoint Engine — AI Supply-Chain Bottleneck Screen (educational reproduction)",
        fontsize=17, fontweight="bold",
    )

    # ---- Panel 1: supply-chain dependency graph -------------------------------
    ax = axes[0][0]
    # layered layout: x by criticality, y by layer
    pos = {}
    layer_counts: dict[int, int] = {}
    for n in nodes:
        layer_counts[n.layer] = layer_counts.get(n.layer, 0) + 1
    seen: dict[int, int] = {}
    for n in nodes:
        seen[n.layer] = seen.get(n.layer, 0)
        x = seen[n.layer] - (layer_counts[n.layer] - 1) / 2.0
        pos[n.ticker] = (x, _layer_y(n.layer))
        seen[n.layer] += 1

    crit = [central[t]["criticality"] for t in g.nodes]
    sizes = [300 + 9000 * central[t]["criticality"] for t in g.nodes]
    nx.draw_networkx_edges(g, pos, ax=ax, alpha=0.35, arrows=True,
                           arrowstyle="-|>", arrowsize=12, edge_color="#888")
    nodes_drawn = nx.draw_networkx_nodes(
        g, pos, ax=ax, node_size=sizes, node_color=crit, cmap="YlOrRd",
        edgecolors="black", linewidths=0.6,
    )
    nx.draw_networkx_labels(g, pos, ax=ax, font_size=8, font_weight="bold")
    ax.set_title("Dependency graph (A→B = A depends on B)\nnode size/color = topological criticality", fontsize=11)
    for layer in sorted(LAYERS):
        ax.text(-3.2, _layer_y(layer), f"L{layer}", fontsize=8, color="#555", va="center")
    ax.axis("off")
    fig.colorbar(nodes_drawn, ax=ax, fraction=0.035, pad=0.02, label="criticality")

    # ---- Panel 2: chokepoint score bars --------------------------------------
    ax = axes[0][1]
    inv = [s for s in scores if s.investable]
    inv_sorted = sorted(inv, key=lambda s: s.chokepoint_score, reverse=True)
    labels = [s.ticker for s in inv_sorted]
    vals = [s.chokepoint_score for s in inv_sorted]
    colors = ["#1a9850" if v >= 70 else "#fdae61" if v >= 55 else "#d73027" for v in vals]
    ax.barh(labels[::-1], vals[::-1], color=colors[::-1], edgecolor="black", linewidth=0.4)
    ax.axvline(70, color="green", ls="--", lw=1, label="strong choke (70)")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Chokepoint Score (0-100)")
    ax.set_title("How real is the bottleneck?", fontsize=11)
    ax.legend(fontsize=8)

    # ---- Panel 3: odds vs conviction scatter ---------------------------------
    ax = axes[1][0]
    for s in inv:
        x = s.chokepoint_score
        y = s.odds_ratio
        size = 60 + 1600 * max(s.kelly_weight, 0)
        color = "#1a9850" if s.expected_value > 0.3 else "#fdae61" if s.expected_value > 0 else "#d73027"
        ax.scatter(x, y, s=size, c=color, alpha=0.75, edgecolors="black", linewidths=0.6)
        ax.annotate(s.ticker, (x, y), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("Chokepoint Score (conviction / moat)")
    ax.set_ylabel("Odds ratio  (upside x / downside loss)")
    ax.set_title("High-odds zone = top-right (bubble = Kelly weight, green = +E[V])", fontsize=11)
    ax.grid(alpha=0.25)

    # ---- Panel 4: demand vs capacity -----------------------------------------
    ax = axes[1][1]
    proj = project()
    yrs = [r["year"] for r in proj["rows"]]
    dem = [r["demand_index"] for r in proj["rows"]]
    cap = [r["capacity_index"] for r in proj["rows"]]
    ax.plot(yrs, dem, "o-", color="#d73027", lw=2.5, label=f"Optical demand ({proj['demand_cagr']*100:.0f}% CAGR)")
    ax.plot(yrs, cap, "s--", color="#4575b4", lw=2.5, label=f"Chokepoint capacity ({proj['capacity_cagr']*100:.0f}% CAGR)")
    ax.fill_between(yrs, cap, dem, where=[d > c for d, c in zip(dem, cap)], color="#d73027", alpha=0.15)
    ax.set_xlabel("Year")
    ax.set_ylabel("Index (2026 = 100)")
    ax.set_title(f"Demand tsunami vs supply: +{proj['terminal_shortfall_pct']:.0f}% shortfall by {yrs[-1]}", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)

    fig.text(0.5, 0.005,
             "Educational reproduction of a publicly-described framework. Curated/illustrative data — NOT investment advice.",
             ha="center", fontsize=9, style="italic", color="#666")
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def adversarial_report(nodes: list[Node] | None = None, top: int = 15) -> str:
    """Step-3 red/blue-team report: rank by adversarial-adjusted EV and show survivors."""
    nodes = nodes if nodes is not None else get_universe()
    investable = [n for n in nodes if n.market_cap_b > 0]
    results = [(n, redteam_node_full(n)) for n in investable]
    results.sort(key=lambda nr: nr[1].adversarial_ev, reverse=True)

    out = []
    out.append("=" * 104)
    out.append("ADVERSARIAL VALIDATION (Step 3: harshest Devil's Advocate red/blue team)")
    out.append("=" * 104)
    out.append(f"{'TKR':<7}{'Resil':>7}{'AdjEV':>7}{'P(EV>0)':>9}{'Survive':>9}  Strongest objection")
    out.append("-" * 104)
    for n, r in results[:top]:
        flag = "YES" if r.survives else "no"
        crit = f" !{','.join(r.critical_flags)}" if r.critical_flags else ""
        out.append(
            f"{n.ticker:<7}{r.resilience:>7.2f}{r.adversarial_ev:>7.2f}"
            f"{(r.mc_prob_positive_ev or 0)*100:>8.0f}%{flag:>9}{crit}  {r.top_objection[:60]}"
        )
    survivors = [n.ticker for n, r in results if r.survives]
    out.append("")
    out.append(f"SURVIVORS (resilient + no critical hole + Monte-Carlo P(EV>0) >= 55%): {', '.join(survivors) or 'none'}")
    out.append("=> Only survivors earn high conviction / a real position; the rest stay watchlist-only.")
    out.append("=" * 104)
    return "\n".join(out)


def text_report(scores: list[ChokepointScore] | None = None, top: int = 15) -> str:
    scores = scores if scores is not None else score_universe()
    g = build_graph()
    central = structural_chokepoints(g)
    ranked = rank(scores, by="expected_value")[:top]

    out = []
    out.append("=" * 96)
    out.append("SERENITY CHOKEPOINT ENGINE — high-odds screen (educational reproduction, not advice)")
    out.append("=" * 96)
    out.append("")
    out.append(f"{'#':>2} {'TKR':<7}{'L':>2} {'CPscore':>8}{'Win%':>6}{'Up':>6}{'Down':>6}{'Odds':>6}{'E[V]':>7}{'Kelly':>7}  Flags")
    out.append("-" * 96)
    for i, s in enumerate(ranked, 1):
        out.append(
            f"{i:>2} {s.ticker:<7}{s.layer:>2} {s.chokepoint_score:>8.1f}{s.win_prob*100:>5.0f}%"
            f"{s.upside_mult:>5.1f}x{s.downside_loss*100:>5.0f}%{s.odds_ratio:>6.1f}{s.expected_value:>+7.2f}"
            f"{s.kelly_weight*100:>6.1f}%  {', '.join(s.flags)}"
        )
    out.append("")
    out.append("TOP STRUCTURAL CHOKEPOINTS (graph topology corroboration):")
    top_struct = sorted(central.items(), key=lambda kv: kv[1]["criticality"], reverse=True)[:6]
    for tkr, m in top_struct:
        out.append(f"   {tkr:<7} criticality={m['criticality']:.3f}  dependents={m['dependents']}  "
                   f"betweenness={m['betweenness']:.3f}  upstream_PR={m['upstream_pagerank']:.3f}")
    out.append("")
    out.append("SUGGESTED BOOK (positive E[V], deep-fractional Kelly, normalised to 100%):")
    book = [s for s in ranked if s.expected_value > 0 and s.kelly_weight > 0]
    total_k = sum(s.kelly_weight for s in book) or 1.0
    for s in book:
        out.append(f"   {s.ticker:<7} {100*s.kelly_weight/total_k:>5.1f}%   {s.thesis}")
    out.append("=" * 96)
    return "\n".join(out)
