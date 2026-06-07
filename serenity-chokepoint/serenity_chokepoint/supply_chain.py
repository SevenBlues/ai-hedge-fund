"""
Supply-chain dependency graph + structural-chokepoint detection.

The framework's Step 1 says: build the dependency graph and weight nodes by
market share / how many downstream paths flow through them. A real chokepoint
is not just a hand-label — it should show up *topologically*: lots of critical
paths route through it (high betweenness) and powerful nodes depend on it (high
reverse PageRank / eigenvector centrality).

We build a directed graph where an edge ``A -> B`` means "A structurally
depends on B" (B is upstream of A). We then compute centralities to
*independently* corroborate which nodes the model flagged as chokepoints.
"""

from __future__ import annotations

import networkx as nx

from serenity_chokepoint.chokepoint_data import Node, get_universe, LAYERS


def build_graph(nodes: list[Node] | None = None) -> nx.DiGraph:
    nodes = nodes if nodes is not None else get_universe()
    by_ticker = {n.ticker: n for n in nodes}
    g = nx.DiGraph()
    for n in nodes:
        g.add_node(
            n.ticker,
            name=n.name,
            layer=n.layer,
            layer_name=LAYERS.get(n.layer, "?"),
            share=n.top3_share,
            irreplaceability=n.irreplaceability,
            market_cap_b=n.market_cap_b,
        )
    # Edge A -> B : A depends on upstream B. Weight by B's supply concentration
    # (a dependency on a concentrated supplier is a "heavier" structural risk).
    for n in nodes:
        for up in n.depends_on:
            if up in by_ticker:
                g.add_edge(n.ticker, up, weight=by_ticker[up].top3_share)
    return g


def structural_chokepoints(g: nx.DiGraph) -> dict[str, dict]:
    """Return per-node topological centrality metrics.

    - dependents       : how many nodes (transitively) rely on this node upstream
    - betweenness      : fraction of shortest dependency paths passing through it
    - upstream_pagerank: PageRank on the reversed graph — flow of dependence
                         pooling into upstream suppliers (high => critical source)
    """
    rev = g.reverse(copy=True)
    betw = nx.betweenness_centrality(g, weight="weight", normalized=True)
    try:
        pr = nx.pagerank(rev, weight="weight")
    except nx.PowerIterationFailedConvergence:
        pr = {n: 0.0 for n in g.nodes}

    out: dict[str, dict] = {}
    for node in g.nodes:
        # transitive dependents = ancestors in the dependency DAG
        dependents = len(nx.ancestors(g, node))
        out[node] = {
            "dependents": dependents,
            "betweenness": round(betw.get(node, 0.0), 4),
            "upstream_pagerank": round(pr.get(node, 0.0), 4),
            "criticality": round(
                0.5 * pr.get(node, 0.0) * 10  # scale pagerank into ~0..1 band
                + 0.3 * betw.get(node, 0.0)
                + 0.2 * min(dependents / max(len(g) - 1, 1), 1.0),
                4,
            ),
        }
    return out


def ascii_layers(nodes: list[Node] | None = None) -> str:
    """A quick textual layer map for terminals without matplotlib."""
    nodes = nodes if nodes is not None else get_universe()
    lines = ["AI-compute supply chain (top = system, bottom = feedstock):", ""]
    for layer in sorted(LAYERS):
        members = [n for n in nodes if n.layer == layer]
        if not members:
            continue
        tickers = ", ".join(f"{n.ticker}" for n in members)
        lines.append(f"  L{layer} {LAYERS[layer]:<38} {tickers}")
    return "\n".join(lines)
