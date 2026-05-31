"""
Offline unit tests for the Serenity Chokepoint Engine.

These intentionally exercise only the deterministic, network-free core so they
run anywhere (CI included). Anything that needs yfinance (live data, backtests)
is tested via its pure helpers on synthetic series, never by hitting the network.

    pytest tests/test_serenity.py -q
"""

from __future__ import annotations

import dataclasses

import pandas as pd
import pytest

from serenity_chokepoint.chokepoint_data import by_ticker, get_universe
from serenity_chokepoint.scoring import WEIGHTS, rank, score_node, score_universe


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100


def test_pillars_and_score_in_range():
    for s in score_universe():
        assert 0.0 <= s.chokepoint_score <= 100.0
        for v in s.pillars.values():
            assert 0.0 <= v <= 1.0
        assert 0.10 <= s.win_prob <= 0.85          # humility bounds
        assert 0.0 <= s.downside_loss <= 1.0
        assert 0.0 <= s.kelly_weight <= 0.10        # fractional-Kelly cap
        assert s.upside_mult >= 1.0


def test_known_anchors_score_high():
    """AXTI and SIVE are the framework's flagship chokepoints -> must rank as real."""
    scored = {s.ticker: s for s in score_universe()}
    assert scored["AXTI"].chokepoint_score >= 70
    assert scored["SIVE"].chokepoint_score >= 65
    # the system anchor NVDA offers little asymmetry here
    assert scored["NVDA"].chokepoint_score < scored["AXTI"].chokepoint_score


def test_concentration_curve_monotonic():
    """Higher top-3 share must never lower the concentration pillar."""
    base = by_ticker()["AAOI"]
    prev = -1.0
    for share in (0.3, 0.5, 0.7, 0.85, 0.95):
        n = dataclasses.replace(base, top3_share=share)
        v = score_node(n).pillars["supply_concentration"]
        assert v >= prev
        prev = v


def test_rank_excludes_non_investable_and_is_sorted():
    ranked = rank(score_universe(), by="expected_value", investable_only=True)
    assert all(s.investable for s in ranked)
    assert "SHIN-ETSU" not in {s.ticker for s in ranked}   # graph-only node filtered
    evs = [s.expected_value for s in ranked]
    assert evs == sorted(evs, reverse=True)


# --------------------------------------------------------------------------- #
# supply-chain graph
# --------------------------------------------------------------------------- #
def test_graph_edges_and_centrality():
    from serenity_chokepoint.supply_chain import build_graph, structural_chokepoints

    g = build_graph()
    # edges only connect known tickers
    tickers = {n.ticker for n in get_universe()}
    for a, b in g.edges():
        assert a in tickers and b in tickers
    central = structural_chokepoints(g)
    assert set(central) == set(g.nodes)
    # AXTI sits deep upstream -> many transitive dependents + non-zero betweenness
    assert central["AXTI"]["dependents"] >= 3
    assert central["AXTI"]["betweenness"] > 0


# --------------------------------------------------------------------------- #
# demand model
# --------------------------------------------------------------------------- #
def test_demand_outruns_capacity():
    from serenity_chokepoint.demand_model import project

    p = project()
    assert len(p["rows"]) == 5  # base year + 4
    assert p["demand_cagr"] > p["capacity_cagr"]
    assert p["rows"][0]["shortfall_pct"] == 0.0          # both start at 100
    assert p["terminal_shortfall_pct"] > 0               # demand pulls ahead


# --------------------------------------------------------------------------- #
# adversarial
# --------------------------------------------------------------------------- #
def test_redteam_bounds_and_attacks():
    from serenity_chokepoint.adversarial import redteam_node_full

    for n in get_universe():
        if n.market_cap_b <= 0:
            continue
        r = redteam_node_full(n)
        assert 0.0 <= r.resilience <= 1.0
        assert r.attacks, "every node must face attack vectors"
        assert all(0.0 <= a.severity <= 1.0 for a in r.attacks)
        assert 0.0 <= (r.mc_prob_positive_ev or 0) <= 1.0


def test_monte_carlo_is_deterministic():
    from serenity_chokepoint.adversarial import monte_carlo

    n = by_ticker()["SIVE"]
    a, b = monte_carlo(n, n=1000, seed=42), monte_carlo(n, n=1000, seed=42)
    assert a["prob_positive_ev"] == b["prob_positive_ev"]


def test_llm_redteam_degrades_gracefully():
    """Must return a dict (never raise) even without API keys / pydantic."""
    from serenity_chokepoint.adversarial import llm_redteam

    res = llm_redteam(by_ticker()["AXTI"])
    assert isinstance(res, dict) and "objections" in res


# --------------------------------------------------------------------------- #
# live data (offline paths only)
# --------------------------------------------------------------------------- #
def test_live_no_listing_is_not_ok():
    from serenity_chokepoint.live_data import fetch_live_quote

    q = fetch_live_quote("SHIN-ETSU")   # mapped to None -> no network call
    assert q.ok is False


def test_enrich_node_preserves_structural_fields():
    from serenity_chokepoint.live_data import LiveQuote, enrich_node

    n = by_ticker()["AXTI"]
    q = LiveQuote(ticker="AXTI", ok=True, market_cap_b=6.7, inst_ownership=0.58,
                  analyst_coverage=5, short_interest=0.13, ev_to_revenue=57.0)
    new, changes = enrich_node(n, q)
    # market-derived fields refreshed ...
    assert new.market_cap_b == pytest.approx(6.7)
    assert new.inst_ownership == pytest.approx(0.58)
    # ... structural fields untouched
    assert new.top3_share == n.top3_share
    assert new.irreplaceability == n.irreplaceability
    assert new.qual_cycle_months == n.qual_cycle_months
    assert changes  # something was logged


def test_enrich_node_noop_when_quote_not_ok():
    from serenity_chokepoint.live_data import LiveQuote, enrich_node

    n = by_ticker()["AXTI"]
    new, changes = enrich_node(n, LiveQuote(ticker="AXTI", ok=False))
    assert new is n and changes == []


# --------------------------------------------------------------------------- #
# the product: the pool
# --------------------------------------------------------------------------- #
def test_pool_respects_certainty_gate():
    from serenity_chokepoint.pool import MIN_CHOKEPOINT, MIN_PROB_POSITIVE_EV, MIN_WIN_PROB, select_pool

    pool = select_pool()  # curated, offline
    assert pool, "curated universe should yield a non-empty high-conviction pool"
    for p in pool:
        assert p.win_prob >= MIN_WIN_PROB
        assert p.chokepoint_score >= MIN_CHOKEPOINT
        assert p.prob_positive_ev >= MIN_PROB_POSITIVE_EV
    # weights are a normalised, return-maximising allocation
    assert sum(p.conviction_weight for p in pool) == pytest.approx(1.0, abs=1e-3)
    # tiers are assigned and core has the heaviest name
    assert {p.tier for p in pool} <= {1, 2, 3}
    top = max(pool, key=lambda p: p.conviction_weight)
    assert top.tier == 1


# --------------------------------------------------------------------------- #
# backtest / oos pure helpers (no network)
# --------------------------------------------------------------------------- #
def test_oos_pure_helpers():
    from serenity_chokepoint.oos_backtest import _ann
    from serenity_chokepoint.backtest import _stats

    # 12 months of +5%/mo -> strong positive annualised return, positive Sharpe
    r = pd.Series([0.05] * 12)
    ann, sharpe = _ann(r)
    assert ann > 0 and sharpe > 0

    daily = pd.Series([0.001] * 300)
    s = _stats("flat-up", daily)
    assert s.total_return > 0
    assert s.max_drawdown <= 0


def test_exp_return_monotonic_in_winprob():
    from serenity_chokepoint.pool import _exp_return

    lo = _exp_return(0.4, 4.0, 0.5)
    hi = _exp_return(0.8, 4.0, 0.5)
    assert hi > lo
