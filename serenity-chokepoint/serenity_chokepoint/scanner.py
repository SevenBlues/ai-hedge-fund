"""
Live MOMENTUM RANKING over a broad universe.

⚠️ This is explicitly NOT the chokepoint analysis method — it is a plain
price-momentum ranking, included as a convenience radar. The chokepoint method
(structural moat + growth inflection + adversarial validation) is what this
project is actually about; momentum just tells you what has already moved.

``scan`` casts a wide net over a broad AI supply-chain universe (or your own
``--tickers``), pulls live prices, and ranks names by a blended multi-horizon
momentum score (3- / 6- / 12-month returns, volatility-adjusted), flagging a
recent re-rating gap. Output changes daily with the market and surfaces names
beyond the curated list — use it to spot what's moving, then switch to
``serenity validate`` / ``serenity growth`` to do the real analysis.

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

# Blended multi-horizon momentum weights (3m/6m/12m) and a re-rating-gap flag.
HORIZON_WEIGHTS = {3: 0.25, 6: 0.35, 12: 0.40}
VOL_ADJUST = True        # divide momentum by volatility (risk-adjusted)
JUMP_THRESHOLD = 0.20    # >=20% up-month = recent re-rating gap
JUMP_WINDOW = 3


@dataclass
class ScanRow:
    ticker: str
    score: float                       # 0..100 percentile-ranked momentum
    ret_3m: float
    ret_6m: float
    ret_12m: float
    vol: float
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
            if len(s) >= 13:
                out[str(t)] = [float(x) for x in s.values]
    else:  # single series
        s = close.dropna()
        if len(s) >= 13:
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


def _horizon_return(prices: list[float], months: int) -> float | None:
    if len(prices) <= months:
        return None
    return prices[-1] / prices[-1 - months] - 1.0


def scan(tickers: list[str] | None = None, period: str = "2y", top: int = 25,
         enrich_cap: bool = True) -> dict:
    """Rank a broad universe by blended, volatility-adjusted multi-horizon momentum."""
    from serenity_chokepoint.chokepoint_data import by_ticker

    universe = [t.upper() for t in (tickers or DEFAULT_UNIVERSE)]
    prices = _fetch_prices(universe, period)
    if not prices:
        return {"error": "no price data (need network / yfinance, or bad tickers)"}

    curated = set(by_ticker())
    names: list[str] = []
    rets_by_h: dict[int, list[float]] = {h: [] for h in HORIZON_WEIGHTS}
    vols: list[float] = []
    rerate_flags: list[bool] = []

    import numpy as np
    for t, p in prices.items():
        monthly = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
        names.append(t)
        for h in HORIZON_WEIGHTS:
            rets_by_h[h].append(_horizon_return(p, h) or 0.0)
        vols.append(float(np.std(monthly) * math.sqrt(12)) if monthly else 0.0)
        window = monthly[-JUMP_WINDOW:]
        rerate_flags.append(max(window) >= JUMP_THRESHOLD if window else False)

    # blend z-scored horizon returns; optionally divide by volatility (risk-adjusted)
    z_by_h = {h: _zscores(rets_by_h[h]) for h in HORIZON_WEIGHTS}
    blended = []
    for i in range(len(names)):
        m = sum(HORIZON_WEIGHTS[h] * z_by_h[h][i] for h in HORIZON_WEIGHTS)
        if VOL_ADJUST and vols[i] > 0:
            m = m / (1.0 + vols[i])           # damp high-volatility names
        blended.append(m)

    order = sorted(range(len(names)), key=lambda i: blended[i], reverse=True)
    n = len(order)

    # market-cap display only (no longer tilts the ranking — this is pure momentum)
    caps = {t: None for t in names}
    if enrich_cap:
        for i in order[: max(top, 25)]:
            caps[names[i]] = _market_cap_b(names[i])

    rows: list[ScanRow] = []
    for rank_pos, i in enumerate(order):
        pct = 100.0 * (n - 1 - rank_pos) / max(n - 1, 1)
        rows.append(ScanRow(
            ticker=names[i], score=round(pct, 1),
            ret_3m=round(rets_by_h[3][i], 3), ret_6m=round(rets_by_h[6][i], 3),
            ret_12m=round(rets_by_h[12][i], 3), vol=round(vols[i], 3),
            rerate=rerate_flags[i], market_cap_b=caps[names[i]],
            in_curated=names[i] in curated,
        ))
    return {"rows": rows, "n": n, "period": period, "universe_size": len(universe)}


def text_report(tickers: list[str] | None = None, period: str = "2y", top: int = 25) -> str:
    res = scan(tickers=tickers, period=period, top=top)
    out = ["=" * 96, "SERENITY — LIVE MOMENTUM RANKING  (⚠️ momentum only, NOT the chokepoint method)", "=" * 96]
    if "error" in res:
        return "\n".join(out + [f"[scan] {res['error']}", "Try: serenity scan --tickers NVDA,AXTI,SIVE  (and check your connection)."])
    out.append(f"Ranked {res['n']}/{res['universe_size']} names. "
               f"Momentum = vol-adjusted blend of 3m/6m/12m returns (live, changes daily).")
    out.append(f"{'#':>2} {'TICKER':<7}{'MOM':>6}{'3m':>7}{'6m':>7}{'12m':>8}{'vol':>6}{'gap':>5}{'MKT$B':>9}  note")
    out.append("-" * 96)
    for i, r in enumerate(res["rows"][:top], 1):
        cap = f"{r.market_cap_b:.1f}" if r.market_cap_b else "  ?"
        gap = "🔥" if r.rerate else " ·"
        note = "curated" if r.in_curated else "new"
        out.append(f"{i:>2} {r.ticker:<7}{r.score:>6.0f}{r.ret_3m*100:>6.0f}%{r.ret_6m*100:>6.0f}%"
                   f"{r.ret_12m*100:>7.0f}%{r.vol*100:>5.0f}%{gap:>5}{cap:>9}  {note}")
    out.append("-" * 96)
    out.append("MOM = percentile of vol-adjusted 3m/6m/12m momentum (100 = strongest here).  🔥 = recent >20% month.")
    out.append("'new' = not in the curated pool. Momentum tells you what ALREADY moved — it is NOT a buy signal.")
    out.append("Do the real work next: `serenity growth <T>` + `serenity validate <T>`. Not financial advice.")
    out.append("=" * 96)
    return "\n".join(out)
