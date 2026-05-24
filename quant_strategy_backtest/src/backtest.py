"""
Daily-bar backtesting engine for the dual-asset (TQQQ/SPY/Cash) strategy.

Execution model
---------------
* Signals are produced from data through close[T-1].
* Resulting target weights are *executed at open[T]* (so we never use
  same-day close info to make the same-day trade).
* Position P&L for day T accrues from the executed open price to that
  day's close, plus close-to-close for subsequent holding days.
* Transaction cost: 1 bp + 2 bp slippage applied to the **traded notional**
  whenever a leg's weight changes.
* Cash earns the prevailing 13w T-bill rate on a daily basis.

Risk overlays
-------------
* HARD STOP   : if cumulative return on an open TQQQ position falls
                below -12% (measured from entry VWAP), flatten the
                TQQQ leg the next open and force score-floor=0 (cash)
                for `cooldown_days` trading days.
* TRAIL STOP  : if total portfolio equity falls 8% from its running
                peak, multiply the (TQQQ, SPY) target weights by 0.5
                until equity reclaims the prior peak.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    initial_capital: float = 100_000.0
    commission_bps: float = 1.0           # 1 bp per traded notional
    slippage_bps: float = 2.0             # 2 bp per traded notional
    hard_stop: float = -0.12              # -12% on TQQQ position
    hard_stop_cooldown_days: int = 5
    trail_drawdown: float = 0.08          # -8% from equity peak
    trail_reduce_to: float = 0.50         # cut risk weights in half
    # Daily cash yield from ^IRX (annualized % -> daily decimal)
    cash_yield_floor: float = 0.0


@dataclass
class BacktestResult:
    equity: pd.Series
    weights: pd.DataFrame              # actually traded weights post overlays
    target_weights: pd.DataFrame       # raw model targets
    positions: pd.DataFrame            # daily $ in each leg
    trades: pd.DataFrame               # row per rebalance
    diagnostics: pd.DataFrame          # per-day metrics (dd, score, stops)


def _apply_costs(prev_w: np.ndarray, new_w: np.ndarray, cfg: BacktestConfig) -> float:
    """Return cost as a fraction of equity for a rebalance."""
    turnover = np.abs(new_w - prev_w).sum() / 2.0  # one-sided
    return turnover * (cfg.commission_bps + cfg.slippage_bps) / 1e4


def run_backtest(
    master: pd.DataFrame,
    target: pd.DataFrame,
    cfg: BacktestConfig = BacktestConfig(),
) -> BacktestResult:
    idx = master.index
    n = len(idx)

    spy_open = master["spy_open"].values
    spy_close = master["spy_close"].values
    tqqq_open = master["tqqq_open"].values
    tqqq_close = master["tqqq_close"].values
    irx = master["irx_close"].values    # annualized percent

    w_tqqq_t = target["w_tqqq"].values
    w_spy_t = target["w_spy"].values
    w_cash_t = target["w_cash"].values
    score = target["score"].values

    equity = np.zeros(n)
    pos_tqqq = np.zeros(n)              # dollar value
    pos_spy = np.zeros(n)
    pos_cash = np.zeros(n)
    w_tqqq_a = np.zeros(n)              # actually traded weights
    w_spy_a = np.zeros(n)
    w_cash_a = np.zeros(n)
    drawdown = np.zeros(n)
    peak = -np.inf
    trail_active = np.zeros(n, dtype=bool)
    hardstop_until = -1                 # bar index until which TQQQ is forbidden
    tqqq_entry_value_per_unit = np.nan  # entry "cost basis" for hard-stop check
    tqqq_shares = 0.0                   # synthetic shares (for entry tracking)
    trade_log: list[dict] = []

    equity[0] = cfg.initial_capital
    pos_cash[0] = cfg.initial_capital
    peak = equity[0]

    for t in range(1, n):
        # 1) Mark previous position from close[t-1] to open[t]
        if pos_tqqq[t - 1] > 0:
            pos_tqqq_open = pos_tqqq[t - 1] * (tqqq_open[t] / tqqq_close[t - 1])
        else:
            pos_tqqq_open = 0.0
        if pos_spy[t - 1] > 0:
            pos_spy_open = pos_spy[t - 1] * (spy_open[t] / spy_close[t - 1])
        else:
            pos_spy_open = 0.0
        # Cash earns 1 day of T-bill yield (use yesterday's reported yield)
        day_yield = max(irx[t - 1], cfg.cash_yield_floor) / 100.0 / 252.0
        pos_cash_open = pos_cash[t - 1] * (1.0 + day_yield)

        equity_open = pos_tqqq_open + pos_spy_open + pos_cash_open

        # 2) Decide target weights for day t (already lagged in `target`)
        tgt_tqqq = w_tqqq_t[t]
        tgt_spy = w_spy_t[t]
        tgt_cash = w_cash_t[t]
        if np.isnan(tgt_tqqq):
            tgt_tqqq, tgt_spy, tgt_cash = 0.0, 0.0, 1.0

        # 2a) hard-stop cooldown: forbid TQQQ leg, reallocate to SPY
        if t <= hardstop_until:
            tgt_spy = tgt_spy + tgt_tqqq
            tgt_tqqq = 0.0

        # 2b) trailing drawdown: halve risk weights, add to cash
        if peak > 0 and (equity_open / peak - 1.0) <= -cfg.trail_drawdown:
            trail_active[t] = True
            cut = (tgt_tqqq + tgt_spy) * (1 - cfg.trail_reduce_to)
            tgt_tqqq *= cfg.trail_reduce_to
            tgt_spy *= cfg.trail_reduce_to
            tgt_cash += cut

        # 3) Compute trade vs current (open) weights
        prev_w = np.array([
            pos_tqqq_open / equity_open if equity_open > 0 else 0.0,
            pos_spy_open / equity_open if equity_open > 0 else 0.0,
            pos_cash_open / equity_open if equity_open > 0 else 0.0,
        ])
        new_w = np.array([tgt_tqqq, tgt_spy, tgt_cash])

        cost_frac = _apply_costs(prev_w, new_w, cfg)
        equity_after_cost = equity_open * (1.0 - cost_frac)

        new_tqqq = equity_after_cost * tgt_tqqq
        new_spy = equity_after_cost * tgt_spy
        new_cash = equity_after_cost * tgt_cash

        # Hard-stop entry tracking: record cost basis when TQQQ leg increases
        if new_tqqq > pos_tqqq_open + 1e-6:
            # Adding to TQQQ at open[t] price - update entry VWAP
            added_value = new_tqqq - pos_tqqq_open
            added_shares = added_value / tqqq_open[t]
            old_basis = tqqq_entry_value_per_unit if not np.isnan(tqqq_entry_value_per_unit) else 0.0
            new_total_shares = tqqq_shares + added_shares
            if new_total_shares > 0:
                tqqq_entry_value_per_unit = (
                    (old_basis * tqqq_shares) + (tqqq_open[t] * added_shares)
                ) / new_total_shares
            tqqq_shares = new_total_shares
        elif new_tqqq < pos_tqqq_open - 1e-6 and pos_tqqq_open > 0:
            # Reducing/closing -> shrink shares proportionally
            shrink = new_tqqq / pos_tqqq_open if pos_tqqq_open > 0 else 0.0
            tqqq_shares *= shrink
            if tqqq_shares < 1e-9:
                tqqq_shares = 0.0
                tqqq_entry_value_per_unit = np.nan

        traded = abs(new_tqqq - pos_tqqq_open) + abs(new_spy - pos_spy_open) + abs(new_cash - pos_cash_open)
        if traded > 1e-6:
            trade_log.append({
                "date": idx[t],
                "score": score[t],
                "prev_w": prev_w.copy(),
                "new_w": new_w.copy(),
                "equity_open": equity_open,
                "cost": equity_open * cost_frac,
                "trail_active": bool(trail_active[t]),
            })

        # 4) Mark to close[t]
        pos_tqqq[t] = new_tqqq * (tqqq_close[t] / tqqq_open[t]) if tqqq_open[t] > 0 else 0.0
        pos_spy[t] = new_spy * (spy_close[t] / spy_open[t]) if spy_open[t] > 0 else 0.0
        pos_cash[t] = new_cash  # cash already grew open->open above; ignore intraday for cash
        equity[t] = pos_tqqq[t] + pos_spy[t] + pos_cash[t]

        w_tqqq_a[t] = pos_tqqq[t] / equity[t] if equity[t] > 0 else 0.0
        w_spy_a[t] = pos_spy[t] / equity[t] if equity[t] > 0 else 0.0
        w_cash_a[t] = pos_cash[t] / equity[t] if equity[t] > 0 else 0.0

        # 5) Update peak / drawdown
        peak = max(peak, equity[t])
        drawdown[t] = equity[t] / peak - 1.0

        # 6) Hard-stop check (close-of-day) on the TQQQ leg
        if pos_tqqq[t] > 0 and not np.isnan(tqqq_entry_value_per_unit) and tqqq_entry_value_per_unit > 0:
            pos_return = tqqq_close[t] / tqqq_entry_value_per_unit - 1.0
            if pos_return <= cfg.hard_stop:
                # Flatten TQQQ at next open by setting cooldown
                hardstop_until = t + cfg.hard_stop_cooldown_days
                trade_log.append({
                    "date": idx[t],
                    "score": score[t],
                    "event": "HARD_STOP",
                    "pos_return": pos_return,
                })

    equity_s = pd.Series(equity, index=idx, name="equity")
    weights_actual = pd.DataFrame(
        {"w_tqqq": w_tqqq_a, "w_spy": w_spy_a, "w_cash": w_cash_a},
        index=idx,
    )
    positions = pd.DataFrame(
        {"pos_tqqq": pos_tqqq, "pos_spy": pos_spy, "pos_cash": pos_cash},
        index=idx,
    )
    trades = pd.DataFrame(trade_log)
    diagnostics = pd.DataFrame(
        {
            "equity": equity,
            "drawdown": drawdown,
            "trail_active": trail_active,
            "score": score,
        },
        index=idx,
    )
    return BacktestResult(
        equity=equity_s,
        weights=weights_actual,
        target_weights=target,
        positions=positions,
        trades=trades,
        diagnostics=diagnostics,
    )
