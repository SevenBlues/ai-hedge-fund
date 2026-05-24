"""
Performance analytics + benchmark comparison.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def equity_curve_metrics(equity: pd.Series, periods_per_year: int = 252) -> dict:
    if len(equity) < 2:
        return {}
    ret = equity.pct_change().dropna()
    n_years = (equity.index[-1] - equity.index[0]).days / 365.25
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / n_years) - 1.0 if n_years > 0 else np.nan
    ann_vol = ret.std() * np.sqrt(periods_per_year)
    sharpe = (ret.mean() * periods_per_year) / (ret.std() * np.sqrt(periods_per_year)) if ret.std() > 0 else np.nan
    downside = ret[ret < 0].std() * np.sqrt(periods_per_year)
    sortino = (ret.mean() * periods_per_year) / downside if downside > 0 else np.nan

    roll_max = equity.cummax()
    dd = equity / roll_max - 1.0
    max_dd = dd.min()
    # Calmar
    calmar = cagr / abs(max_dd) if max_dd < 0 else np.nan

    # Drawdown duration
    underwater = (dd < 0).astype(int)
    # length of longest streak of consecutive underwater days
    longest = 0
    cur = 0
    for v in underwater.values:
        cur = cur + 1 if v else 0
        longest = max(longest, cur)

    win_days = (ret > 0).mean()
    best_day = ret.max()
    worst_day = ret.min()

    return {
        "start": equity.index[0].date(),
        "end": equity.index[-1].date(),
        "years": round(n_years, 2),
        "total_return": total_return,
        "cagr": cagr,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": calmar,
        "longest_dd_days": longest,
        "win_day_pct": win_days,
        "best_day": best_day,
        "worst_day": worst_day,
    }


def buy_and_hold(master: pd.DataFrame, ticker: str, initial: float = 100_000.0) -> pd.Series:
    col = f"{ticker.lower()}_close"
    p = master[col]
    eq = initial * p / p.iloc[0]
    eq.name = f"BH_{ticker}"
    return eq


def annual_returns(equity: pd.Series) -> pd.Series:
    return equity.resample("YE").last().pct_change().dropna()


def rolling_metrics(equity: pd.Series, window_days: int = 252) -> pd.DataFrame:
    ret = equity.pct_change()
    rolling_ret = (1 + ret).rolling(window_days).apply(lambda x: x.prod() - 1, raw=False)
    rolling_vol = ret.rolling(window_days).std() * np.sqrt(252)
    return pd.DataFrame({"rolling_1y_return": rolling_ret, "rolling_1y_vol": rolling_vol})


def format_metrics_table(metrics_dict: dict[str, dict]) -> pd.DataFrame:
    df = pd.DataFrame(metrics_dict).T
    pct_cols = ["total_return", "cagr", "ann_vol", "max_drawdown", "win_day_pct", "best_day", "worst_day"]
    for c in pct_cols:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: f"{x:.2%}" if pd.notna(x) else "n/a")
    for c in ["sharpe", "sortino", "calmar"]:
        if c in df.columns:
            df[c] = df[c].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "n/a")
    return df
