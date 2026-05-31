"""
Live full-market scanner for the chokepoint "ramp" factor.

Unlike ``pool`` (which scores a fixed, hand-curated watchlist), ``scan`` casts a
wide net over a broad AI supply-chain universe, pulls *live* prices, and ranks
every name by a **point-in-time, price-derived** signal — so the output changes
with the market day to day and surfaces names beyond the curated list.

The signal is the same mechanical "chokepoint-ramp" factor the out-of-sample
backtest validated, computable with zero look-ahead from prices alone:

    score ≈ z(12-1 momentum) + tilt·(recent re-rating gap) + tilt·(small-cap)

It is NOT the deep-research chokepoint score (that needs human-verified
structural data). Think of ``scan`` as the radar that finds candidates, and
``validate`` / ``pool`` as the deep dive on the ones worth researching.

Needs network (yfinance). Educational; not financial advice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Broad, fixed AI-hardware / semi / optical / materials supply-chain universe —
# winners AND laggards. The factor (not the analyst) does the selecting, and you
# can override it entirely with --tickers.
DEFAULT_UNIVERSE = [
    # accelerators / ASIC / CPU
    "NVDA", "AMD", "AVGO", "MRVL", "ARM", "INTC", "QCOM",
    # optical / transceivers / photonics
    "COHR", "LITE", "AAOI", "POET", "CIEN", "INFN", "MTSI", "ANET", "CRDO", "ALAB", "GLW",
    # substrates / materials / RF / power
    "AXTI", "MP", "ON", "QRVO", "SWKS", "WOLF", "SITM", "FORM", "NVTS", "POWI", "MPWR",
    # memory / storage
    "MU", "WDC", "STX", "SNDK",
    # analog / mcu / broad semi
    "TXN", "MCHP", "ADI", "NXPI", "LSCC", "RMBS",
    # foundry / equipment / test / packaging
    "TSM", "ASML", "AMAT", "LRCX", "KLAC", "TER", "AEHR", "ACLS", "AMKR", "UCTT", "ICHR", "ONTO", "CAMT", "NVMI",
    # interconnect / power infra / cooling
    "VRT", "VICR", "AEIS", "ENVX",
]

MOM_LOOKBACK = 12        # months
MOM_SKIP = 1             # skip most recent month
JUMP_THRESHOLD = 0.20    # >=20% up-month = re-rating/ramp gap
JUMP_WINDOW = 3
JUMP_TILT = 0.6
SIZE_TILT = 0.4          # smaller cap -> more "undiscovered"


@dataclass
class ScanRow:
    ticker: str
    score: float                       # 0..100 percentile-ranked composite
    momentum_12_1: float
    rerate: bool
    market_cap_b: float | None = None
    in_curated: bool = False
    components: dict = field(default_factory=dict)


def _zscores(values: list[float]) -> list[float]:
    import numpy as np
    a = np.array(values, dtype=float)
    sd = a.std()
    return list((a - a.mean()) / sd) if sd > 0 else [0.0] * len(a)


def _fetch_prices(tickers: list[str], period: str):
    """One batched monthly-close download. Returns {ticker: list[float]} or None."""
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        df = yf.download(tickers, period=period, interval="1mo",
                         auto_adjust=True, progress=False, threads=True)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    # Multi-ticker -> columns are a MultiIndex with a "Close" level; single -> flat.
    try:
        close = df["Close"] if "Close" in df.columns.get_level_values(0) else df
    except Exception:
        close = df.get("Close", df)
    out: dict[str, list[float]] = {}
    if hasattr(close, "columns"):
        for t in close.columns:
            s = close[t].dropna()
            if len(s) >= MOM_LOOKBACK + MOM_SKIP + 1:
                out[str(t)] = [float(x) for x in s.values]
    else:  # single series
        s = close.dropna()
        if len(s) >= MOM_LOOKBACK + MOM_SKIP + 1:
            out[tickers[0]] = [float(x) for x in s.values]
    return out or None


def _market_cap_b(ticker: str) -> float | None:
    try:
        import yfinance as yf
        fi = yf.Ticker(ticker).fast_info
        mc = getattr(fi, "market_cap", None)          # snake-case attribute
        if mc is None and hasattr(fi, "get"):
            mc = fi.get("marketCap")                   # camelCase key
        return round(mc / 1e9, 3) if mc else None
    except Exception:
        return None


def scan(tickers: list[str] | None = None, period: str = "2y", top: int = 25,
         enrich_cap: bool = True) -> dict:
    """Rank a broad universe by the live chokepoint-ramp factor."""
    from serenity_chokepoint.chokepoint_data import by_ticker

    universe = [t.upper() for t in (tickers or DEFAULT_UNIVERSE)]
    prices = _fetch_prices(universe, period)
    if not prices:
        return {"error": "no price data (need network / yfinance, or bad tickers)"}

    curated = set(by_ticker())
    raw_mom, names = [], []
    rerate_flags = []
    for t, p in prices.items():
        # monthly returns
        rets = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
        mom = p[-1 - MOM_SKIP] / p[-(MOM_LOOKBACK + MOM_SKIP)] - 1.0
        window = rets[-JUMP_WINDOW:]
        rerate = max(window) >= JUMP_THRESHOLD if window else False
        names.append(t)
        raw_mom.append(mom)
        rerate_flags.append(rerate)

    mom_z = _zscores(raw_mom)

    # optional small-cap tilt for the displayed/ranked names
    caps = {t: None for t in names}
    if enrich_cap:
        # enrich a generous slice (rank a first pass by momentum, enrich the top)
        prelim = sorted(range(len(names)), key=lambda i: mom_z[i] + JUMP_TILT * rerate_flags[i], reverse=True)
        for i in prelim[: max(top * 2, 40)]:
            caps[names[i]] = _market_cap_b(names[i])
    cap_vals = [math.log10(caps[t]) if caps[t] else 1.0 for t in names]  # ~log $B
    size_z = [-z for z in _zscores(cap_vals)]  # smaller cap -> higher

    raw = [mom_z[i] + JUMP_TILT * (1.0 if rerate_flags[i] else 0.0) + SIZE_TILT * size_z[i]
           for i in range(len(names))]
    order = sorted(range(len(names)), key=lambda i: raw[i], reverse=True)
    n = len(order)

    rows: list[ScanRow] = []
    for rank_pos, i in enumerate(order):
        pct = 100.0 * (n - 1 - rank_pos) / max(n - 1, 1)
        rows.append(ScanRow(
            ticker=names[i], score=round(pct, 1),
            momentum_12_1=round(raw_mom[i], 3), rerate=rerate_flags[i],
            market_cap_b=caps[names[i]], in_curated=names[i] in curated,
            components={"mom_z": round(mom_z[i], 2), "size_z": round(size_z[i], 2)},
        ))
    return {"rows": rows, "n": n, "period": period, "universe_size": len(universe)}


def text_report(tickers: list[str] | None = None, period: str = "2y", top: int = 25) -> str:
    res = scan(tickers=tickers, period=period, top=top)
    out = ["=" * 92, "SERENITY CHOKEPOINT — LIVE MARKET SCAN (point-in-time ramp factor)", "=" * 92]
    if "error" in res:
        return "\n".join(out + [f"[scan] {res['error']}", "Try: serenity scan --tickers NVDA,AXTI,SIVE  (and check your connection)."])
    out.append(f"Scanned {res['n']}/{res['universe_size']} names over {res['period']}. "
               f"Signal = 12-1 momentum + re-rating gap + small-cap tilt (live, changes daily).")
    out.append(f"{'#':>2} {'TICKER':<7}{'SCORE':>7}{'MOM(12-1)':>11}{'RAMP':>6}{'MKT$B':>9}   note")
    out.append("-" * 92)
    for i, r in enumerate(res["rows"][:top], 1):
        cap = f"{r.market_cap_b:.1f}" if r.market_cap_b else "  ?"
        ramp = "🔥" if r.rerate else "  "
        note = "curated" if r.in_curated else "NEW find"
        out.append(f"{i:>2} {r.ticker:<7}{r.score:>7.1f}{r.momentum_12_1*100:>10.0f}%{ramp:>6}{cap:>9}   {note}")
    out.append("-" * 92)
    out.append("SCORE = cross-sectional percentile of the ramp factor (100 = strongest in this scan).")
    out.append("'NEW find' = surfaced by the radar but NOT in the curated pool — candidates to research next.")
    out.append("Radar only: confirm with `serenity validate <T>` / deep research. Not financial advice.")
    out.append("=" * 92)
    return "\n".join(out)
