"""
Real market data loader (Yahoo Finance via yfinance).
Downloads price/yield series, caches to CSV, and aligns trading calendar.

No simulated data. All values are point-in-time as reported by Yahoo.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = {
    "TQQQ": "TQQQ",     # 3x leveraged Nasdaq ETF (offensive)
    "SPY": "SPY",       # S&P 500 ETF (defensive)
    "QQQ": "QQQ",       # Nasdaq-100 (momentum reference - longer history than TQQQ)
    "VIX": "^VIX",      # CBOE Volatility Index
    "IRX": "^IRX",      # 13-week T-Bill yield (Fed policy proxy)
    "FVX": "^FVX",      # 5-year Treasury yield (rate cycle signal)
    "SHY": "SHY",       # 1-3 year Treasury ETF (2y proxy)
}


def _cache_path(key: str) -> Path:
    return DATA_DIR / f"{key}.csv"


def download_one(key: str, ticker: str, start: str, end: str, force: bool = False) -> pd.DataFrame:
    path = _cache_path(key)
    if path.exists() and not force:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if df.index.min() <= pd.Timestamp(start) and df.index.max() >= pd.Timestamp(end) - pd.Timedelta(days=7):
            return df
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
    df.to_csv(path)
    return df


def load_all(start: str = "2017-01-01", end: str | None = None, force: bool = False) -> dict[str, pd.DataFrame]:
    if end is None:
        end = pd.Timestamp.today().strftime("%Y-%m-%d")
    out: dict[str, pd.DataFrame] = {}
    for key, ticker in TICKERS.items():
        out[key] = download_one(key, ticker, start=start, end=end, force=force)
    return out


def build_master_frame(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Combine into a single trading-day-aligned frame using SPY calendar."""
    base = data["SPY"].index
    frame = pd.DataFrame(index=base)
    frame["spy_open"] = data["SPY"]["Open"]
    frame["spy_close"] = data["SPY"]["Close"]
    frame["tqqq_open"] = data["TQQQ"]["Open"].reindex(base)
    frame["tqqq_close"] = data["TQQQ"]["Close"].reindex(base)
    frame["qqq_close"] = data["QQQ"]["Close"].reindex(base)
    frame["vix_close"] = data["VIX"]["Close"].reindex(base)
    frame["irx_close"] = data["IRX"]["Close"].reindex(base)     # in percent points
    frame["fvx_close"] = data["FVX"]["Close"].reindex(base)
    frame["shy_close"] = data["SHY"]["Close"].reindex(base)
    # Forward-fill the macro series for missing publication days (VIX/IRX share NYSE calendar but be safe)
    macro_cols = ["vix_close", "irx_close", "fvx_close", "shy_close"]
    frame[macro_cols] = frame[macro_cols].ffill(limit=3)
    return frame.dropna()


if __name__ == "__main__":
    data = load_all(start="2017-01-01", force=False)
    for k, df in data.items():
        print(f"{k:6s} rows={len(df):5d} {df.index.min().date()} -> {df.index.max().date()}")
    master = build_master_frame(data)
    print("\nMaster frame:", master.shape, master.index.min().date(), "->", master.index.max().date())
    print(master.tail(3))
