"""
Backtest layer for the Serenity Chokepoint Engine.

Tests the core claim of the framework — that physically-concentrated,
hard-to-qualify chokepoints re-rate hard once volume ramps — against real price
history (Yahoo Finance). Three complementary tests:

1. ``portfolio_backtest`` — constant-mix backtest of the engine's
   Kelly-weighted "survivor" book vs an equal-weight universe and vs NVDA/QQQ.
   Reports CAGR, vol, Sharpe, max drawdown.

2. ``factor_backtest`` — cross-sectional test: does a high-Chokepoint-Score
   basket beat a low-Chokepoint-Score basket over the window? (a crude IC /
   long-short read on whether "chokepoint-ness" has been a paying factor).

3. ``event_study`` — data-driven proxy for "qualification -> ramp -> re-rating":
   detect each name's large single-day re-rating jumps (earnings/qualification
   gaps) and measure the average N-day FORWARD return after them vs the
   unconditional baseline. If chokepoints really ramp, those jumps should be
   followed by continuation, not mean-reversion.

HONEST CAVEATS (printed in the report too):
  * The universe and scores are defined with *today's* knowledge, so the
    portfolio/factor tests are IN-SAMPLE / survivorship-tinged — illustrative,
    not a clean out-of-sample track record. The event study is the more honest,
    point-in-time-ish test.
  * Returns are computed in each listing's LOCAL currency (FX ignored) — a
    second-order caveat for the non-US names.
  * Needs network for yfinance; degrades to a clear "no data" message offline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from serenity_chokepoint.chokepoint_data import get_universe
from serenity_chokepoint.live_data import YAHOO_SYMBOL
from serenity_chokepoint.scoring import rank, score_universe

TRADING_DAYS = 252


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def _yahoo(ticker: str) -> str | None:
    return YAHOO_SYMBOL.get(ticker, ticker)


def fetch_history(tickers: list[str], period: str = "2y", interval: str = "1d") -> dict:
    """Return {ticker: pandas.Series of adjusted close}. Best-effort, never raises."""
    try:
        import yfinance as yf
    except Exception as e:  # pragma: no cover
        return {"_error": f"yfinance unavailable: {e}"}

    out: dict = {}
    for t in tickers:
        sym = _yahoo(t)
        if sym is None:
            continue
        try:
            h = yf.Ticker(sym).history(period=period, interval=interval, auto_adjust=True)
            if h is not None and not h.empty and "Close" in h:
                s = h["Close"].dropna()
                if len(s) > 30:
                    out[t] = s
        except Exception:
            continue
    if not out:
        out["_error"] = "no price history returned (offline or all tickers failed)"
    return out


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
@dataclass
class PerfStats:
    name: str
    total_return: float
    cagr: float
    vol: float
    sharpe: float
    max_drawdown: float
    n_days: int


def _stats(name: str, returns) -> PerfStats:
    import numpy as np

    r = returns.dropna()
    if len(r) < 20:
        return PerfStats(name, 0, 0, 0, 0, 0, len(r))
    equity = (1 + r).cumprod()
    total = float(equity.iloc[-1] - 1)
    years = len(r) / TRADING_DAYS
    cagr = float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0
    vol = float(r.std() * math.sqrt(TRADING_DAYS))
    sharpe = float((r.mean() * TRADING_DAYS) / (r.std() * math.sqrt(TRADING_DAYS))) if r.std() > 0 else 0.0
    dd = float((equity / equity.cummax() - 1).min())
    return PerfStats(name, total, cagr, vol, sharpe, dd, len(r))


def _aligned_returns(history: dict):
    """Build an aligned daily-returns DataFrame from the price dict."""
    import pandas as pd

    prices = {t: s for t, s in history.items() if not t.startswith("_")}
    df = pd.DataFrame(prices).sort_index()
    df = df.ffill().dropna(how="all")
    return df.pct_change().dropna(how="all")


# --------------------------------------------------------------------------- #
# 1) Portfolio backtest (constant-mix daily rebalance to target weights)
# --------------------------------------------------------------------------- #
def portfolio_backtest(period: str = "2y", live_weights: bool = False) -> dict:
    nodes = get_universe()
    if live_weights:
        from serenity_chokepoint.live_data import enrich_universe
        nodes, _ = enrich_universe(nodes)
    scores = score_universe(nodes)

    # Engine book = positive-EV survivors, deep-fractional-Kelly weights normalised.
    from serenity_chokepoint.adversarial import redteam_node_full
    node_map = {n.ticker: n for n in nodes}
    book = [s for s in rank(scores, by="expected_value")
            if s.expected_value > 0 and s.kelly_weight > 0 and redteam_node_full(node_map[s.ticker]).survives]
    wsum = sum(s.kelly_weight for s in book) or 1.0
    weights = {s.ticker: s.kelly_weight / wsum for s in book}

    bench = ["NVDA", "QQQ"]
    history = fetch_history(list(weights) + [s.ticker for s in scores] + bench, period=period)
    if "_error" in history:
        return {"error": history["_error"]}

    rets = _aligned_returns(history)
    results: list[PerfStats] = []

    # engine book
    cols = [t for t in weights if t in rets.columns]
    if cols:
        w = {t: weights[t] for t in cols}
        wsum2 = sum(w.values()) or 1.0
        port = sum(rets[t] * (w[t] / wsum2) for t in cols)
        results.append(_stats("Engine survivors (Kelly)", port))

    # equal-weight full investable universe
    uni_cols = [s.ticker for s in scores if s.ticker in rets.columns and s.investable]
    if uni_cols:
        eq = rets[uni_cols].mean(axis=1)
        results.append(_stats("Equal-weight universe", eq))

    for b in bench:
        if b in rets.columns:
            results.append(_stats(b, rets[b]))

    return {
        "weights": weights,
        "stats": results,
        "returns": rets,
        "engine_cols": cols,
        "period": period,
    }


# --------------------------------------------------------------------------- #
# 2) Cross-sectional factor backtest
# --------------------------------------------------------------------------- #
def factor_backtest(period: str = "2y", live: bool = False) -> dict:
    nodes = get_universe()
    if live:
        from serenity_chokepoint.live_data import enrich_universe
        nodes, _ = enrich_universe(nodes)
    scores = [s for s in score_universe(nodes) if s.investable]
    scores.sort(key=lambda s: s.chokepoint_score, reverse=True)

    n = len(scores)
    k = max(2, n // 3)
    high = [s.ticker for s in scores[:k]]
    low = [s.ticker for s in scores[-k:]]

    history = fetch_history(high + low, period=period)
    if "_error" in history:
        return {"error": history["_error"]}
    rets = _aligned_returns(history)

    high_c = [t for t in high if t in rets.columns]
    low_c = [t for t in low if t in rets.columns]
    out = {"high_basket": high_c, "low_basket": low_c}
    if high_c and low_c:
        hr = rets[high_c].mean(axis=1)
        lr = rets[low_c].mean(axis=1)
        out["high"] = _stats("High-chokepoint basket", hr)
        out["low"] = _stats("Low-chokepoint basket", lr)
        out["long_short"] = _stats("Long high / short low", hr - lr)
    return out


# --------------------------------------------------------------------------- #
# 3) Event study: forward returns after big re-rating jumps
# --------------------------------------------------------------------------- #
def event_study(period: str = "3y", jump_threshold: float = 0.12, fwd_days: int = 60) -> dict:
    """Proxy 'qualification/ramp re-rating' with large single-day up-gaps and
    measure the average forward return after them vs the unconditional baseline."""
    import numpy as np

    nodes = [n for n in get_universe() if n.market_cap_b > 0]
    history = fetch_history([n.ticker for n in nodes], period=period)
    if "_error" in history:
        return {"error": history["_error"]}

    event_fwd: list[float] = []
    base_fwd: list[float] = []
    n_events = 0
    per_ticker: dict[str, int] = {}

    for t, s in history.items():
        if t.startswith("_"):
            continue
        s = s.dropna()
        r = s.pct_change()
        vals = s.values
        for i in range(1, len(vals) - fwd_days):
            fwd = vals[i + fwd_days] / vals[i] - 1.0
            base_fwd.append(fwd)
            if r.iloc[i] >= jump_threshold:
                event_fwd.append(fwd)
                n_events += 1
                per_ticker[t] = per_ticker.get(t, 0) + 1

    if not event_fwd:
        return {"error": "no re-rating events detected in window"}

    return {
        "fwd_days": fwd_days,
        "jump_threshold": jump_threshold,
        "n_events": n_events,
        "event_mean_fwd": float(np.mean(event_fwd)),
        "event_median_fwd": float(np.median(event_fwd)),
        "baseline_mean_fwd": float(np.mean(base_fwd)),
        "hit_rate": float(np.mean([1 if x > 0 else 0 for x in event_fwd])),
        "edge": float(np.mean(event_fwd) - np.mean(base_fwd)),
        "per_ticker": dict(sorted(per_ticker.items(), key=lambda kv: kv[1], reverse=True)),
    }


# --------------------------------------------------------------------------- #
# Reporting + chart
# --------------------------------------------------------------------------- #
def _fmt(s: PerfStats) -> str:
    return (f"{s.name:<26} ret={s.total_return*100:>7.1f}%  CAGR={s.cagr*100:>6.1f}%  "
            f"vol={s.vol*100:>5.1f}%  Sharpe={s.sharpe:>5.2f}  maxDD={s.max_drawdown*100:>6.1f}%  (n={s.n_days})")


def text_report(period: str = "2y", live: bool = False) -> str:
    out = ["=" * 96, "SERENITY CHOKEPOINT — BACKTEST (real Yahoo Finance history)", "=" * 96]

    pb = portfolio_backtest(period=period, live_weights=live)
    if "error" in pb:
        return "\n".join(out + [f"[portfolio] {pb['error']}",
                                "Backtest needs network access for yfinance. Skipped."])

    out.append(f"\n1) PORTFOLIO ({pb['period']}, constant-mix; engine book = {', '.join(pb['engine_cols'])}):")
    for s in pb["stats"]:
        out.append("   " + _fmt(s))

    fb = factor_backtest(period=period, live=live)
    out.append("\n2) FACTOR (high- vs low-Chokepoint-Score baskets):")
    if "error" in fb:
        out.append(f"   {fb['error']}")
    else:
        out.append(f"   high={fb['high_basket']}  low={fb['low_basket']}")
        for key in ("high", "low", "long_short"):
            if key in fb:
                out.append("   " + _fmt(fb[key]))

    es = event_study(period="3y")
    out.append("\n3) EVENT STUDY (qualification/ramp re-rating proxy = +12% day, 60d forward):")
    if "error" in es:
        out.append(f"   {es['error']}")
    else:
        out.append(f"   {es['n_events']} events; forward {es['fwd_days']}d mean={es['event_mean_fwd']*100:+.1f}% "
                   f"(median {es['event_median_fwd']*100:+.1f}%, hit-rate {es['hit_rate']*100:.0f}%)")
        out.append(f"   baseline {es['fwd_days']}d mean={es['baseline_mean_fwd']*100:+.1f}%  =>  "
                   f"EDGE {es['edge']*100:+.1f}%  ({'ramp-continuation CONFIRMED' if es['edge'] > 0 else 'no continuation edge'})")
        out.append(f"   most events: {', '.join(f'{k}({v})' for k, v in list(es['per_ticker'].items())[:6])}")

    out.append("\nCAVEAT: in-sample / survivorship-tinged (universe chosen with hindsight); local-currency returns; "
               "illustrative validation, NOT a live track record or investment advice.")
    out.append("=" * 96)
    return "\n".join(out)


def render_png(path: str = "serenity_backtest.png", period: str = "2y", live: bool = False) -> str | None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pb = portfolio_backtest(period=period, live_weights=live)
    if "error" in pb:
        return None
    rets = pb["returns"]

    fig, axes = plt.subplots(1, 2, figsize=(18, 6.5))
    fig.suptitle("Serenity Chokepoint — Backtest (real history, illustrative/in-sample)", fontweight="bold")

    # equity curves
    ax = axes[0]
    cols = pb["engine_cols"]
    if cols:
        w = {t: pb["weights"][t] for t in cols}
        ws = sum(w.values()) or 1.0
        eq = (1 + sum(rets[t] * (w[t] / ws) for t in cols)).cumprod()
        ax.plot(eq.index, eq.values, lw=2.5, color="#1a9850", label="Engine survivors (Kelly)")
    uni = [s.ticker for s in score_universe(get_universe()) if s.ticker in rets.columns and s.investable]
    if uni:
        eqe = (1 + rets[uni].mean(axis=1)).cumprod()
        ax.plot(eqe.index, eqe.values, lw=1.8, ls="--", color="#666", label="Equal-weight universe")
    for b, c in (("NVDA", "#762a83"), ("QQQ", "#4575b4")):
        if b in rets.columns:
            eqb = (1 + rets[b]).cumprod()
            ax.plot(eqb.index, eqb.values, lw=1.5, alpha=0.8, color=c, label=b)
    ax.set_title(f"Growth of $1 ({pb['period']})")
    ax.set_ylabel("equity (x)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)

    # event study bar
    ax = axes[1]
    es = event_study(period="3y")
    if "error" not in es:
        ax.bar(["after re-rating\njump (+12% day)", "unconditional\nbaseline"],
               [es["event_mean_fwd"] * 100, es["baseline_mean_fwd"] * 100],
               color=["#1a9850", "#999"], edgecolor="black")
        ax.set_title(f"Forward {es['fwd_days']}d return: ramp continuation?\n{es['n_events']} events, edge {es['edge']*100:+.1f}%")
        ax.set_ylabel("mean forward 60d return (%)")
        ax.axhline(0, color="black", lw=0.8)
    ax.grid(alpha=0.2, axis="y")

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
