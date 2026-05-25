"""
Backtest engine v2.2 — extends v2 engine with optional ATR-based stop.

If `target["atr_pct_lag"]` is present and `cfg.use_atr_stop` is True,
the per-day hard stop threshold is set to -cfg.atr_k * atr_pct_lag[t]
instead of the fixed cfg.hard_stop. Everything else identical to v2 engine.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestV22Config:
    initial_capital: float = 100_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    hard_stop: float = -0.12               # fixed stop (used if use_atr_stop=False)
    use_atr_stop: bool = False
    atr_k: float = 3.0                     # dynamic stop = -k * atr_pct
    hard_stop_cooldown_days: int = 5
    trail_drawdown: float = 0.08
    trail_reduce_to: float = 0.50
    cash_yield_floor: float = 0.0
    drift_band: float = 0.03


@dataclass
class BacktestV22Result:
    equity: pd.Series
    weights: pd.DataFrame
    target_weights: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame
    diagnostics: pd.DataFrame


def _cost_frac(prev: np.ndarray, new: np.ndarray, cfg: BacktestV22Config) -> float:
    turnover = np.abs(new - prev).sum() / 2.0
    return turnover * (cfg.commission_bps + cfg.slippage_bps) / 1e4


def run_backtest_v22(master: pd.DataFrame, target: pd.DataFrame,
                      cfg: BacktestV22Config = BacktestV22Config()) -> BacktestV22Result:
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

    if cfg.use_atr_stop and "atr_pct_lag" in target.columns:
        atr_pct = target["atr_pct_lag"].values
    else:
        atr_pct = np.full(n, np.nan)

    equity = np.zeros(n)
    pos_tqqq = np.zeros(n); pos_qld = np.zeros(n); pos_spy = np.zeros(n); pos_cash = np.zeros(n)
    w_tqqq_a = np.zeros(n); w_qld_a = np.zeros(n); w_spy_a = np.zeros(n); w_cash_a = np.zeros(n)
    drawdown = np.zeros(n)
    trail_active = np.zeros(n, dtype=bool)
    stop_used = np.full(n, np.nan)
    peak = -np.inf
    hardstop_until = -1
    risky_entry_value = np.nan
    risky_entry_units = 0.0
    trade_log: list[dict] = []

    equity[0] = cfg.initial_capital
    pos_cash[0] = cfg.initial_capital
    peak = equity[0]

    for t in range(1, n):
        pos_tqqq_open = pos_tqqq[t - 1] * (tqqq_open[t] / tqqq_close[t - 1]) if pos_tqqq[t - 1] > 0 else 0.0
        pos_qld_open = pos_qld[t - 1] * (qld_open[t] / qld_close[t - 1]) if pos_qld[t - 1] > 0 else 0.0
        pos_spy_open = pos_spy[t - 1] * (spy_open[t] / spy_close[t - 1]) if pos_spy[t - 1] > 0 else 0.0
        day_yield = max(irx[t - 1], cfg.cash_yield_floor) / 100.0 / 252.0
        pos_cash_open = pos_cash[t - 1] * (1.0 + day_yield)
        equity_open = pos_tqqq_open + pos_qld_open + pos_spy_open + pos_cash_open

        tgt = np.array([w_tqqq_t[t], w_qld_t[t], w_spy_t[t], w_cash_t[t]])
        if np.any(np.isnan(tgt)):
            tgt = np.array([0.0, 0.0, 0.0, 1.0])

        if t <= hardstop_until:
            tgt[2] += tgt[0] + tgt[1]
            tgt[0] = 0.0; tgt[1] = 0.0

        if peak > 0 and (equity_open / peak - 1.0) <= -cfg.trail_drawdown:
            trail_active[t] = True
            cut = (tgt[0] + tgt[1] + tgt[2]) * (1 - cfg.trail_reduce_to)
            tgt[0] *= cfg.trail_reduce_to
            tgt[1] *= cfg.trail_reduce_to
            tgt[2] *= cfg.trail_reduce_to
            tgt[3] += cut

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

            risky_now = new_tqqq + new_qld + new_spy
            risky_prev = pos_tqqq_open + pos_qld_open + pos_spy_open
            if risky_now > risky_prev + 1e-6:
                added = risky_now - risky_prev
                if risky_entry_units <= 0 or np.isnan(risky_entry_value):
                    risky_entry_value = added; risky_entry_units = 1.0
                else:
                    total_basis = risky_entry_value * risky_entry_units + added
                    risky_entry_units += added / (risky_entry_value if risky_entry_value > 0 else 1.0)
                    risky_entry_value = total_basis / risky_entry_units
            elif risky_now < risky_prev - 1e-6 and risky_prev > 0:
                shrink = risky_now / risky_prev
                risky_entry_units *= shrink
                if risky_entry_units < 1e-9:
                    risky_entry_units = 0.0; risky_entry_value = np.nan

            trade_log.append({
                "date": idx[t], "score": score[t],
                "prev_w": prev_w.copy(), "new_w": tgt.copy(),
                "equity_open": equity_open, "cost": equity_open * cost,
                "trail_active": bool(trail_active[t]),
                "max_drift": max_drift,
            })
        else:
            new_tqqq = pos_tqqq_open; new_qld = pos_qld_open
            new_spy = pos_spy_open; new_cash = pos_cash_open

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

        # ATR or fixed hard-stop check
        risky_now = pos_tqqq[t] + pos_qld[t] + pos_spy[t]
        if risky_now > 0 and not np.isnan(risky_entry_value) and risky_entry_units > 0:
            cost_basis = risky_entry_value * risky_entry_units
            if cost_basis > 0:
                sleeve_ret = risky_now / cost_basis - 1.0
                if cfg.use_atr_stop and not np.isnan(atr_pct[t]):
                    stop_threshold = -cfg.atr_k * atr_pct[t]
                else:
                    stop_threshold = cfg.hard_stop
                stop_used[t] = stop_threshold
                if sleeve_ret <= stop_threshold:
                    hardstop_until = t + cfg.hard_stop_cooldown_days
                    trade_log.append({
                        "date": idx[t], "event": "STOP",
                        "sleeve_ret": sleeve_ret,
                        "stop_threshold": stop_threshold,
                    })

    return BacktestV22Result(
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
            "stop_used": stop_used,
        }, index=idx),
    )
