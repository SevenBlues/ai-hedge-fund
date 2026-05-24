"""
Backtest engine v2 — four-asset (TQQQ / QLD / SPY / Cash).

Same execution model as v1: signals through close[T-1], traded at open[T],
1bp commission + 2bp slippage on traded notional, cash earns ^IRX.

Risk overlays kept identical to v1 in semantics, but apply to the *aggregate*
risk weight (TQQQ + QLD + SPY) rather than only TQQQ:

  - HARD STOP : if the leveraged-weighted portfolio loses 12% from entry
                cost basis on the risky sleeve, flatten the leveraged
                legs (TQQQ + QLD) for `cooldown_days`.
  - TRAIL STOP: 8% from equity peak halves all risky weights.

Adds a `drift_band` parameter — only rebalance if any leg's weight drift
exceeds the band (reduces churn vs daily rebalancing).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestV2Config:
    initial_capital: float = 100_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    hard_stop: float = -0.12
    hard_stop_cooldown_days: int = 5
    trail_drawdown: float = 0.08
    trail_reduce_to: float = 0.50
    cash_yield_floor: float = 0.0
    drift_band: float = 0.03           # rebalance only if max-leg drift > 3pp


@dataclass
class BacktestV2Result:
    equity: pd.Series
    weights: pd.DataFrame
    target_weights: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame
    diagnostics: pd.DataFrame


def _cost_frac(prev: np.ndarray, new: np.ndarray, cfg: BacktestV2Config) -> float:
    turnover = np.abs(new - prev).sum() / 2.0
    return turnover * (cfg.commission_bps + cfg.slippage_bps) / 1e4


def run_backtest_v2(
    master: pd.DataFrame,
    target: pd.DataFrame,
    cfg: BacktestV2Config = BacktestV2Config(),
) -> BacktestV2Result:
    idx = master.index
    n = len(idx)

    spy_open = master["spy_open"].values
    spy_close = master["spy_close"].values
    tqqq_open = master["tqqq_open"].values
    tqqq_close = master["tqqq_close"].values
    qld_open = master["qld_open"].values
    qld_close = master["qld_close"].values
    irx = master["irx_close"].values

    w_tqqq_t = target["w_tqqq"].values
    w_qld_t = target["w_qld"].values
    w_spy_t = target["w_spy"].values
    w_cash_t = target["w_cash"].values
    score = target["score"].values

    equity = np.zeros(n)
    pos_tqqq = np.zeros(n)
    pos_qld = np.zeros(n)
    pos_spy = np.zeros(n)
    pos_cash = np.zeros(n)
    w_tqqq_a = np.zeros(n)
    w_qld_a = np.zeros(n)
    w_spy_a = np.zeros(n)
    w_cash_a = np.zeros(n)
    drawdown = np.zeros(n)
    trail_active = np.zeros(n, dtype=bool)
    peak = -np.inf
    hardstop_until = -1
    # Track risky-sleeve entry value (a single composite cost basis)
    risky_entry_value = np.nan
    risky_entry_units = 0.0            # synthetic "units" for risk-sleeve P&L
    trade_log: list[dict] = []

    equity[0] = cfg.initial_capital
    pos_cash[0] = cfg.initial_capital
    peak = equity[0]

    for t in range(1, n):
        # 1) Mark previous positions from close[t-1] to open[t]
        pos_tqqq_open = pos_tqqq[t - 1] * (tqqq_open[t] / tqqq_close[t - 1]) if pos_tqqq[t - 1] > 0 else 0.0
        pos_qld_open = pos_qld[t - 1] * (qld_open[t] / qld_close[t - 1]) if pos_qld[t - 1] > 0 else 0.0
        pos_spy_open = pos_spy[t - 1] * (spy_open[t] / spy_close[t - 1]) if pos_spy[t - 1] > 0 else 0.0
        day_yield = max(irx[t - 1], cfg.cash_yield_floor) / 100.0 / 252.0
        pos_cash_open = pos_cash[t - 1] * (1.0 + day_yield)
        equity_open = pos_tqqq_open + pos_qld_open + pos_spy_open + pos_cash_open

        # 2) Target weights for day t
        tgt = np.array([w_tqqq_t[t], w_qld_t[t], w_spy_t[t], w_cash_t[t]])
        if np.any(np.isnan(tgt)):
            tgt = np.array([0.0, 0.0, 0.0, 1.0])

        # 2a) Hard-stop cooldown: forbid leveraged legs, push to SPY
        if t <= hardstop_until:
            tgt[2] += tgt[0] + tgt[1]
            tgt[0] = 0.0
            tgt[1] = 0.0

        # 2b) Trailing stop: halve risky weights, top up cash
        if peak > 0 and (equity_open / peak - 1.0) <= -cfg.trail_drawdown:
            trail_active[t] = True
            cut = (tgt[0] + tgt[1] + tgt[2]) * (1 - cfg.trail_reduce_to)
            tgt[0] *= cfg.trail_reduce_to
            tgt[1] *= cfg.trail_reduce_to
            tgt[2] *= cfg.trail_reduce_to
            tgt[3] += cut

        # 3) Drift-band: skip rebalance if no leg moved more than `drift_band`
        prev_w = np.array([
            pos_tqqq_open / equity_open if equity_open > 0 else 0.0,
            pos_qld_open / equity_open if equity_open > 0 else 0.0,
            pos_spy_open / equity_open if equity_open > 0 else 0.0,
            pos_cash_open / equity_open if equity_open > 0 else 0.0,
        ])
        max_drift = float(np.max(np.abs(tgt - prev_w)))
        rebalance = max_drift > cfg.drift_band

        if rebalance:
            cost = _cost_frac(prev_w, tgt, cfg)
            equity_after = equity_open * (1.0 - cost)
            new_tqqq = equity_after * tgt[0]
            new_qld = equity_after * tgt[1]
            new_spy = equity_after * tgt[2]
            new_cash = equity_after * tgt[3]

            # Risky sleeve entry tracking (in $ terms of current risky exposure)
            risky_now = new_tqqq + new_qld + new_spy
            risky_prev = pos_tqqq_open + pos_qld_open + pos_spy_open
            if risky_now > risky_prev + 1e-6:
                added = risky_now - risky_prev
                if risky_entry_units <= 0 or np.isnan(risky_entry_value):
                    risky_entry_value = added
                    risky_entry_units = 1.0
                else:
                    # Weight-update VWAP-style
                    total_basis = risky_entry_value * risky_entry_units + added
                    risky_entry_units += added / (risky_entry_value if risky_entry_value > 0 else 1.0)
                    risky_entry_value = total_basis / risky_entry_units
            elif risky_now < risky_prev - 1e-6 and risky_prev > 0:
                shrink = risky_now / risky_prev
                risky_entry_units *= shrink
                if risky_entry_units < 1e-9:
                    risky_entry_units = 0.0
                    risky_entry_value = np.nan

            trade_log.append({
                "date": idx[t],
                "score": score[t],
                "prev_w": prev_w.copy(),
                "new_w": tgt.copy(),
                "equity_open": equity_open,
                "cost": equity_open * cost,
                "trail_active": bool(trail_active[t]),
                "max_drift": max_drift,
            })
        else:
            new_tqqq = pos_tqqq_open
            new_qld = pos_qld_open
            new_spy = pos_spy_open
            new_cash = pos_cash_open

        # 4) Mark to close[t]
        pos_tqqq[t] = new_tqqq * (tqqq_close[t] / tqqq_open[t]) if tqqq_open[t] > 0 else 0.0
        pos_qld[t] = new_qld * (qld_close[t] / qld_open[t]) if qld_open[t] > 0 else 0.0
        pos_spy[t] = new_spy * (spy_close[t] / spy_open[t]) if spy_open[t] > 0 else 0.0
        pos_cash[t] = new_cash
        equity[t] = pos_tqqq[t] + pos_qld[t] + pos_spy[t] + pos_cash[t]

        w_tqqq_a[t] = pos_tqqq[t] / equity[t] if equity[t] > 0 else 0.0
        w_qld_a[t] = pos_qld[t] / equity[t] if equity[t] > 0 else 0.0
        w_spy_a[t] = pos_spy[t] / equity[t] if equity[t] > 0 else 0.0
        w_cash_a[t] = pos_cash[t] / equity[t] if equity[t] > 0 else 0.0

        peak = max(peak, equity[t])
        drawdown[t] = equity[t] / peak - 1.0

        # 5) Hard-stop on risky sleeve P&L
        risky_now = pos_tqqq[t] + pos_qld[t] + pos_spy[t]
        if risky_now > 0 and not np.isnan(risky_entry_value) and risky_entry_units > 0:
            cost_basis = risky_entry_value * risky_entry_units
            if cost_basis > 0:
                sleeve_ret = risky_now / cost_basis - 1.0
                if sleeve_ret <= cfg.hard_stop:
                    hardstop_until = t + cfg.hard_stop_cooldown_days
                    trade_log.append({
                        "date": idx[t], "event": "HARD_STOP",
                        "sleeve_ret": sleeve_ret,
                    })

    return BacktestV2Result(
        equity=pd.Series(equity, index=idx, name="equity"),
        weights=pd.DataFrame({
            "w_tqqq": w_tqqq_a, "w_qld": w_qld_a,
            "w_spy": w_spy_a, "w_cash": w_cash_a,
        }, index=idx),
        target_weights=target,
        positions=pd.DataFrame({
            "pos_tqqq": pos_tqqq, "pos_qld": pos_qld,
            "pos_spy": pos_spy, "pos_cash": pos_cash,
        }, index=idx),
        trades=pd.DataFrame(trade_log),
        diagnostics=pd.DataFrame({
            "equity": equity, "drawdown": drawdown,
            "trail_active": trail_active, "score": score,
        }, index=idx),
    )
