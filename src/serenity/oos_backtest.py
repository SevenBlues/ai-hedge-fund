"""
Out-of-sample, walk-forward backtest for the chokepoint "ramp" factor.

The first backtest (``backtest.py``) is honestly in-sample: the universe is the
hand-picked list of Serenity's known winners and the weights come from today's
scores. This module removes those leaks to give a genuinely out-of-sample read:

  * NON-HINDSIGHT UNIVERSE — a broad, fixed list of ~45 AI-hardware / semi /
    optical / materials supply-chain names that deliberately includes laggards
    and non-chokepoints (INTC, TXN, MCHP, SWKS, ...). Selection is done by the
    factor each month, not by the analyst. (Caveat: the list is still drawn up
    in 2026 and Yahoo drops most delisted names, so some survivorship remains —
    this is stated in the report, not hidden.)

  * POINT-IN-TIME SIGNAL — at each monthly rebalance the score uses ONLY prices
    available up to that date: 12-1 momentum (the canonical, look-ahead-free
    factor) plus a "re-rating continuation" flag (did the name just print a big
    up-month, i.e. a qualification/ramp gap?). This is the mechanical,
    price-only version of the chokepoint thesis the event study validated.

  * TRAIN / TEST SPLIT — the rule (lookbacks, top-K, jump threshold) is fixed on
    an early TRAIN window; the held-out TEST window is never used to choose
    parameters or names. We report TRAIN, TEST and FULL separately, plus the
    excess return over SOXX so a rising-tide AI market doesn't masquerade as
    alpha.

No parameter is optimised on the test window. Monthly, non-overlapping holding
periods => no return overlap leakage. A name not yet public at month t is
naturally excluded at t (no survivorship-into-the-future on listing).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.serenity.backtest import fetch_history

# Broad, fixed AI-hardware supply-chain candidate set (winners AND laggards),
# all US-listed to keep returns in one currency. Chosen by sector membership,
# not by outcome.
CANDIDATE_UNIVERSE = [
    # GPUs / accelerators / ASIC
    "NVDA", "AMD", "AVGO", "MRVL", "ARM", "INTC",
    # optical / transceivers / photonics (the chokepoint heartland + peers)
    "COHR", "LITE", "AAOI", "POET", "CIEN", "INFN", "MTSI", "ANET", "CRDO", "ALAB",
    # substrates / materials / RF / power
    "AXTI", "MP", "ON", "QRVO", "SWKS", "WOLF", "SITM", "FORM",
    # memory / storage
    "MU", "WDC", "STX",
    # analog / MCU / broad semi (deliberate laggards)
    "TXN", "MCHP", "ADI", "NXPI",
    # foundry / equipment / test (qualification layer)
    "TSM", "ASML", "AMAT", "LRCX", "KLAC", "TER", "AEHR", "ACLS", "AMKR", "UCTT", "ICHR",
]

# Fixed rule parameters (set on TRAIN intuition / standard values; NOT tuned on test)
MOM_LOOKBACK = 12        # months
MOM_SKIP = 1             # skip most recent month (avoid short-term reversal)
JUMP_THRESHOLD = 0.20    # a >=20% up-month = re-rating/ramp gap proxy
JUMP_WINDOW = 3          # look for such a gap in the last N months
JUMP_TILT = 0.5          # how much the ramp flag adds to the z-scored momentum
TOP_K = 8                # portfolio breadth
TRAIN_FRACTION = 0.55    # first 55% of months define/justify the rule


@dataclass
class PerfStats:
    name: str
    total_return: float
    cagr: float
    vol: float
    sharpe: float
    max_drawdown: float
    n_months: int


def _stats_monthly(name: str, monthly_returns) -> PerfStats:
    import numpy as np

    r = monthly_returns.dropna()
    if len(r) < 6:
        return PerfStats(name, 0, 0, 0, 0, 0, len(r))
    equity = (1 + r).cumprod()
    total = float(equity.iloc[-1] - 1)
    years = len(r) / 12.0
    cagr = float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0
    vol = float(r.std() * math.sqrt(12))
    sharpe = float((r.mean() * 12) / (r.std() * math.sqrt(12))) if r.std() > 0 else 0.0
    dd = float((equity / equity.cummax() - 1).min())
    return PerfStats(name, total, cagr, vol, sharpe, dd, len(r))


def _build_prices(period: str = "8y"):
    import pandas as pd

    hist = fetch_history(CANDIDATE_UNIVERSE + ["SOXX", "QQQ", "SPY"], period=period, interval="1mo")
    if "_error" in hist:
        return None, hist["_error"]
    prices = pd.DataFrame({t: s for t, s in hist.items() if not t.startswith("_")}).sort_index()
    # month-end alignment; do NOT forward-fill across listing gaps (keep NaN pre-IPO)
    return prices, None


def _signal_at(prices, i: int, col: str, rets):
    """Point-in-time signal for one name using ONLY data up to month index i.

    Returns None if insufficient history (name effectively not yet investable).
    """
    need = MOM_LOOKBACK + MOM_SKIP
    if i < need:
        return None
    p_now = prices[col].iloc[i - MOM_SKIP]
    p_then = prices[col].iloc[i - need]
    p_listed = prices[col].iloc[i]
    if any(x != x for x in (p_now, p_then, p_listed)) or p_then == 0:  # NaN/zero guard
        return None
    momentum = p_now / p_then - 1.0
    # re-rating/ramp flag: a big up-month within the last JUMP_WINDOW months
    window = rets[col].iloc[max(0, i - JUMP_WINDOW + 1): i + 1]
    rerate = 1.0 if (window.max() if len(window) else 0) >= JUMP_THRESHOLD else 0.0
    return momentum, rerate


def walk_forward(period: str = "8y"):
    import numpy as np
    import pandas as pd

    prices, err = _build_prices(period)
    if err:
        return {"error": err}

    rets = prices.pct_change()
    dates = prices.index
    cand = [c for c in CANDIDATE_UNIVERSE if c in prices.columns]

    strat_rets = {}   # forward-month date -> portfolio return
    ew_rets = {}      # equal-weight all-available candidates
    picks_log = {}

    # decide weights at month i (info <= i), realise return at i+1
    for i in range(len(dates) - 1):
        raw = {}
        for c in cand:
            sig = _signal_at(prices, i, c, rets)
            if sig is not None:
                raw[c] = sig
        if len(raw) < TOP_K + 2:
            continue
        moms = np.array([v[0] for v in raw.values()])
        mu, sd = moms.mean(), (moms.std() or 1.0)
        scored = {c: (v[0] - mu) / sd + JUMP_TILT * v[1] for c, v in raw.items()}
        picks = sorted(scored, key=scored.get, reverse=True)[:TOP_K]

        fwd_date = dates[i + 1]
        fwd = rets.loc[fwd_date]
        sel = [c for c in picks if fwd.get(c) == fwd.get(c)]  # drop NaN forward (delisted next month)
        if sel:
            strat_rets[fwd_date] = float(np.mean([fwd[c] for c in sel]))
            picks_log[fwd_date] = sel
        avail = [c for c in raw if fwd.get(c) == fwd.get(c)]
        if avail:
            ew_rets[fwd_date] = float(np.mean([fwd[c] for c in avail]))

    strat = pd.Series(strat_rets).sort_index()
    ew = pd.Series(ew_rets).sort_index()
    if len(strat) < 12:
        return {"error": "insufficient history for a walk-forward (need network / longer period)"}

    # chronological train/test split on the strategy's own dates
    split = int(len(strat) * TRAIN_FRACTION)
    split_date = strat.index[split]
    bench = {b: rets[b].reindex(strat.index) for b in ("SOXX", "QQQ", "SPY") if b in rets.columns}

    def seg(s, lo=None, hi=None):
        return s.loc[lo:hi] if (lo is not None or hi is not None) else s

    result = {
        "split_date": str(split_date.date()),
        "n_months": len(strat),
        "params": {
            "universe_size": len(cand), "top_k": TOP_K, "mom": f"{MOM_LOOKBACK}-{MOM_SKIP}",
            "jump_threshold": JUMP_THRESHOLD, "jump_tilt": JUMP_TILT,
        },
        "full": {
            "strategy": _stats_monthly("Chokepoint-ramp factor", strat),
            "equal_weight": _stats_monthly("Equal-weight candidates", ew),
            **{b: _stats_monthly(b, s) for b, s in bench.items()},
        },
        "train": {
            "strategy": _stats_monthly("strategy[train]", seg(strat, hi=split_date)),
            "equal_weight": _stats_monthly("EW[train]", seg(ew, hi=split_date)),
            **{b: _stats_monthly(f"{b}[train]", seg(s, hi=split_date)) for b, s in bench.items()},
        },
        "test": {
            "strategy": _stats_monthly("strategy[TEST/OOS]", seg(strat.loc[split_date:].iloc[1:])),
            "equal_weight": _stats_monthly("EW[TEST/OOS]", seg(ew.loc[split_date:].iloc[1:])),
            **{b: _stats_monthly(f"{b}[TEST/OOS]", seg(s.loc[split_date:].iloc[1:])) for b, s in bench.items()},
        },
        "series": {"strategy": strat, "equal_weight": ew, **bench},
        "picks_log": picks_log,
    }
    return result


# --------------------------------------------------------------------------- #
# Reporting + chart
# --------------------------------------------------------------------------- #
def _fmt(s: PerfStats) -> str:
    return (f"{s.name:<26} ret={s.total_return*100:>8.1f}%  CAGR={s.cagr*100:>6.1f}%  "
            f"vol={s.vol*100:>5.1f}%  Sharpe={s.sharpe:>5.2f}  maxDD={s.max_drawdown*100:>6.1f}%  (n={s.n_months})")


def text_report(period: str = "8y") -> str:
    r = walk_forward(period)
    out = ["=" * 100, "OUT-OF-SAMPLE WALK-FORWARD — chokepoint 'ramp' factor (price-only, point-in-time)", "=" * 100]
    if "error" in r:
        return "\n".join(out + [f"[oos] {r['error']}"])

    p = r["params"]
    out.append(f"universe={p['universe_size']} fixed AI-supply-chain names | monthly | top-{p['top_k']} | "
               f"signal = {p['mom']} momentum + {p['jump_tilt']}*ramp-flag(>= {int(p['jump_threshold']*100)}% up-month)")
    out.append(f"train/test split at {r['split_date']}  (rule fixed on train; test never used to choose params/names)\n")

    for seg_name, title in (("train", "IN-SAMPLE (train)"), ("test", "OUT-OF-SAMPLE (held-out test)"), ("full", "FULL period")):
        out.append(f"-- {title} " + "-" * (96 - len(title)))
        seg = r[seg_name]
        for key in ("strategy", "equal_weight", "SOXX", "QQQ", "SPY"):
            if key in seg:
                out.append("   " + _fmt(seg[key]))
        if "strategy" in seg and "SOXX" in seg:
            excess = seg["strategy"].cagr - seg["SOXX"].cagr
            out.append(f"   => excess CAGR vs SOXX: {excess*100:+.1f} pts   "
                       f"Sharpe edge: {seg['strategy'].sharpe - seg['SOXX'].sharpe:+.2f}")
        out.append("")

    t = r["test"]
    verdict = ("HOLDS OUT-OF-SAMPLE" if t["strategy"].sharpe > t.get("SOXX", t["equal_weight"]).sharpe
               and t["strategy"].cagr > t.get("SOXX", t["equal_weight"]).cagr else "does NOT clearly beat sector beta OOS")
    out.append(f"VERDICT: the chokepoint-ramp factor {verdict} "
               f"(test Sharpe {t['strategy'].sharpe:.2f} vs SOXX {t.get('SOXX', t['equal_weight']).sharpe:.2f}).")
    out.append("CAVEAT: fixed universe drawn in 2026 + Yahoo drops most delisted names => residual survivorship; "
               "monthly long-only; illustrative, NOT a live track record or advice.")
    out.append("=" * 100)
    return "\n".join(out)


def render_png(path: str = "serenity_oos.png", period: str = "8y") -> str | None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    r = walk_forward(period)
    if "error" in r:
        return None
    s = r["series"]
    split = pd.Timestamp(r["split_date"])

    fig, ax = plt.subplots(figsize=(15, 7))
    colors = {"strategy": "#1a9850", "equal_weight": "#666", "SOXX": "#d73027", "QQQ": "#4575b4", "SPY": "#999"}
    labels = {"strategy": "Chokepoint-ramp factor (top-8)", "equal_weight": "Equal-weight candidates",
              "SOXX": "SOXX (semi sector)", "QQQ": "QQQ", "SPY": "SPY"}
    for k, series in s.items():
        ser = series.dropna()
        eq = (1 + ser).cumprod()
        ax.plot(eq.index, eq.values, lw=2.6 if k == "strategy" else 1.5,
                ls="-" if k != "equal_weight" else "--",
                color=colors.get(k, "#333"), label=labels.get(k, k), alpha=0.95 if k == "strategy" else 0.8)
    ax.axvline(split, color="black", ls=":", lw=1.4)
    ax.axvspan(split, eq.index.max(), color="green", alpha=0.05)
    ymax = ax.get_ylim()[1]
    ax.text(split, ymax * 0.96, "  OUT-OF-SAMPLE  -->", fontsize=11, color="green", va="top", fontweight="bold")
    ax.text(s["strategy"].index.min(), ymax * 0.96, "<-- in-sample (train)  ", fontsize=10, color="#555", va="top", ha="left")
    ax.set_yscale("log")
    ax.set_title("Out-of-sample walk-forward: chokepoint 'ramp' factor vs sector beta\n"
                 "(price-only point-in-time signal, monthly rebalance, log scale)", fontweight="bold")
    ax.set_ylabel("growth of $1 (log)")
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(alpha=0.25, which="both")
    fig.text(0.5, 0.01, "Illustrative reproduction — residual survivorship from fixed universe; not investment advice.",
             ha="center", fontsize=8, style="italic", color="#666")
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
