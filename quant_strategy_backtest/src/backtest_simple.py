"""
Lightweight 2-asset (one risk asset + cash) backtest engine for v2.5 sleeves.

Same execution model as the main engine: signals through close[T-1],
trade at open[T], 1bp + 2bp costs on traded notional, cash earns ^IRX,
drift band suppresses tiny rebalances.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestSimpleConfig:
    initial_capital: float = 100_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    drift_band: float = 0.03


def run_backtest_simple(master: pd.DataFrame, target: pd.DataFrame,
                         asset_open_col: str, asset_close_col: str,
                         cfg: BacktestSimpleConfig = BacktestSimpleConfig()) -> pd.Series:
    idx = master.index
    n = len(idx)
    a_open = master[asset_open_col].values
    a_close = master[asset_close_col].values
    irx = master["irx_close"].values
    w_a_t = target["w_asset"].values

    pos_a = np.zeros(n); pos_c = np.zeros(n); eq = np.zeros(n)
    eq[0] = cfg.initial_capital; pos_c[0] = cfg.initial_capital

    for t in range(1, n):
        pos_a_open = pos_a[t-1] * (a_open[t]/a_close[t-1]) if pos_a[t-1] > 0 and a_close[t-1] > 0 else 0.0
        day_yield = max(irx[t-1], 0) / 100.0 / 252.0
        pos_c_open = pos_c[t-1] * (1.0 + day_yield)
        equity_open = pos_a_open + pos_c_open

        tgt_a = w_a_t[t] if not np.isnan(w_a_t[t]) else 0.0
        tgt_c = 1.0 - tgt_a
        prev_w_a = pos_a_open / equity_open if equity_open > 0 else 0.0

        if abs(tgt_a - prev_w_a) > cfg.drift_band:
            turnover = abs(tgt_a - prev_w_a)
            cost = turnover * (cfg.commission_bps + cfg.slippage_bps) / 1e4
            eq_after = equity_open * (1.0 - cost)
            new_a = eq_after * tgt_a; new_c = eq_after * tgt_c
        else:
            new_a = pos_a_open; new_c = pos_c_open

        pos_a[t] = new_a * (a_close[t]/a_open[t]) if a_open[t] > 0 else 0.0
        pos_c[t] = new_c
        eq[t] = pos_a[t] + pos_c[t]

    return pd.Series(eq, index=idx, name="sleeve_equity")
