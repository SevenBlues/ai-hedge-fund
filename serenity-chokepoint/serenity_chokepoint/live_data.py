"""
Live-data layer for the Serenity Chokepoint Engine.

Refreshes the *market-derived* fields of each curated :class:`Node`
(market cap, institutional ownership, analyst coverage, short interest and a
forward EV/Sales proxy) from Yahoo Finance, while preserving the *structural*
fields that no public feed can know (top-3 supply share, physical
irreplaceability, qualification-cycle length, demand/capacity CAGR, ramp
multiple). Those structural fields are the analyst's domain judgement — the
whole point of the framework is that they cannot be screened mechanically.

Design goals:
  * graceful offline fallback — if yfinance is missing or the network is
    blocked, ``enrich_universe`` simply returns the curated nodes untouched and
    records ``live=False`` so the caller knows it is running on curated data;
  * never hang — every network call is wrapped and best-effort;
  * transparent — ``enrich_universe`` returns a changelog of every field it
    overwrote, so a human can audit live vs curated.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from serenity_chokepoint.chokepoint_data import Node, get_universe


# Curated US tickers map 1:1 to Yahoo; non-US / proxy names need an exchange
# suffix (or are graph-only structural nodes with no clean listing).
YAHOO_SYMBOL: dict[str, str | None] = {
    "SIVE": "SIVE.ST",     # Sivers — Nasdaq Stockholm
    "IQE": "IQE.L",        # IQE plc — LSE
    "SOI": "SOIT.PA",      # Soitec — Euronext Paris
    "XFAB": "XFAB.PA",     # X-FAB — Euronext Paris
    "VNP": "VNP.TO",       # 5N Plus — TSX
    "INPACT": None,        # IntelliEPI proxy — no clean liquid US line
    "SHIN-ETSU": None,     # graph-only structural node
}


@dataclass
class LiveQuote:
    ticker: str
    ok: bool
    market_cap_b: float | None = None
    inst_ownership: float | None = None
    analyst_coverage: int | None = None
    short_interest: float | None = None
    ev_to_revenue: float | None = None   # trailing EV/Sales (valuation-stretch proxy)
    price: float | None = None
    error: str | None = None


_CACHE: dict[str, LiveQuote] = {}


def fetch_live_quote(ticker: str) -> LiveQuote:
    """Best-effort single-ticker pull from Yahoo Finance. Never raises."""
    if ticker in _CACHE:
        return _CACHE[ticker]

    symbol = YAHOO_SYMBOL.get(ticker, ticker)
    if symbol is None:
        q = LiveQuote(ticker=ticker, ok=False, error="no public listing (structural/graph-only node)")
        _CACHE[ticker] = q
        return q

    try:
        import yfinance as yf
    except Exception as e:  # pragma: no cover - import guard
        q = LiveQuote(ticker=ticker, ok=False, error=f"yfinance unavailable: {e}")
        _CACHE[ticker] = q
        return q

    try:
        info = yf.Ticker(symbol).info or {}
        mc = info.get("marketCap")
        ev_rev = info.get("enterpriseToRevenue") or info.get("priceToSalesTrailing12Months")
        q = LiveQuote(
            ticker=ticker,
            ok=mc is not None,
            market_cap_b=(mc / 1e9) if mc else None,
            inst_ownership=info.get("heldPercentInstitutions"),
            analyst_coverage=info.get("numberOfAnalystOpinions"),
            short_interest=info.get("shortPercentOfFloat"),
            ev_to_revenue=ev_rev,
            price=info.get("currentPrice") or info.get("regularMarketPrice"),
            error=None if mc is not None else "no marketCap in response",
        )
    except Exception as e:
        q = LiveQuote(ticker=ticker, ok=False, error=f"{type(e).__name__}: {str(e)[:120]}")

    _CACHE[ticker] = q
    return q


def enrich_node(node: Node, quote: LiveQuote) -> tuple[Node, list[str]]:
    """Return a copy of ``node`` with market-derived fields refreshed from ``quote``.

    Structural fields are never touched. Returns (new_node, changelog).
    """
    if not quote.ok:
        return node, []

    changes: list[str] = []
    new = dataclasses.replace(node)

    if quote.market_cap_b is not None and quote.market_cap_b > 0:
        if abs(quote.market_cap_b - node.market_cap_b) / max(node.market_cap_b, 0.01) > 0.05:
            changes.append(f"market_cap_b {node.market_cap_b:.2f}->{quote.market_cap_b:.2f}")
        new.market_cap_b = round(quote.market_cap_b, 3)

    if quote.inst_ownership is not None:
        if abs(quote.inst_ownership - node.inst_ownership) > 0.03:
            changes.append(f"inst_ownership {node.inst_ownership:.2f}->{quote.inst_ownership:.2f}")
        new.inst_ownership = round(quote.inst_ownership, 3)

    if quote.analyst_coverage is not None and quote.analyst_coverage > 0:
        if quote.analyst_coverage != node.analyst_coverage:
            changes.append(f"analyst_coverage {node.analyst_coverage}->{quote.analyst_coverage}")
        new.analyst_coverage = int(quote.analyst_coverage)

    if quote.short_interest is not None:
        if abs(quote.short_interest - node.short_interest) > 0.02:
            changes.append(f"short_interest {node.short_interest:.2f}->{quote.short_interest:.2f}")
        new.short_interest = round(quote.short_interest, 3)

    # Translate trailing EV/Sales into our "forward EV/Sales on ramped revenue"
    # convention by dividing by the projected ramp multiple — keeps the scoring
    # field semantically consistent with the curated version.
    if quote.ev_to_revenue and quote.ev_to_revenue > 0 and node.ramp_rev_mult > 0:
        fwd = quote.ev_to_revenue / node.ramp_rev_mult
        if abs(fwd - node.fwd_ev_sales) > 0.3:
            changes.append(f"fwd_ev_sales {node.fwd_ev_sales:.1f}->{fwd:.1f} (live EV/Rev {quote.ev_to_revenue:.0f})")
        new.fwd_ev_sales = round(fwd, 2)

    return new, changes


def enrich_universe(nodes: list[Node] | None = None) -> tuple[list[Node], dict]:
    """Refresh the whole universe from live data.

    Returns (enriched_nodes, report) where report has:
        live (bool)            : did any live quote succeed
        refreshed (list[str])  : tickers successfully refreshed
        changelog (dict)       : ticker -> list of field changes
        errors (dict)          : ticker -> error string
    """
    nodes = nodes if nodes is not None else get_universe()
    out: list[Node] = []
    changelog: dict[str, list[str]] = {}
    errors: dict[str, str] = {}
    refreshed: list[str] = []

    for n in nodes:
        q = fetch_live_quote(n.ticker)
        if q.ok:
            new, changes = enrich_node(n, q)
            out.append(new)
            refreshed.append(n.ticker)
            if changes:
                changelog[n.ticker] = changes
        else:
            out.append(n)
            if q.error:
                errors[n.ticker] = q.error

    return out, {
        "live": len(refreshed) > 0,
        "refreshed": refreshed,
        "changelog": changelog,
        "errors": errors,
    }
