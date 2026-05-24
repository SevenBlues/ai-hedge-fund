"""
Robustness checks. Vary key thresholds one-at-a-time around the default
and re-run the backtest. A non-overfit strategy should show smooth,
monotone-ish behaviour rather than a single sharp sweet-spot.

Reports CAGR, max drawdown and Sharpe across the grid.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from analysis import equity_curve_metrics
from backtest import BacktestConfig, run_backtest
from data_loader import build_master_frame, load_all
from strategy import StrategyConfig, build_signals, target_weights_frame

RESULTS = Path(__file__).resolve().parent.parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


def run_one(master_full, mask, cfg_s: StrategyConfig) -> dict:
    """Build signals on the FULL series (with proper warmup), then clip
    to the backtest window."""
    signals = build_signals(master_full, cfg_s)
    target = target_weights_frame(signals, cfg_s)
    master_bt = master_full.loc[mask]
    target_bt = target.loc[mask]
    result = run_backtest(master_bt, target_bt, BacktestConfig())
    return equity_curve_metrics(result.equity)


def main() -> None:
    raw = load_all(start="2017-01-01", force=False)
    master_full = build_master_frame(raw)
    mask = (master_full.index >= "2018-05-24") & (master_full.index <= "2026-05-22")

    grids = {
        "vix_low": [16.0, 18.0, 20.0, 22.0, 24.0],
        "vix_high": [26.0, 28.0, 30.0, 32.0, 34.0],
        "momentum_threshold": [0.0, 0.02, 0.05, 0.08, 0.10],
        "irx_lookback_days": [30, 45, 60, 90, 120],
        "trend_sma_days": [150, 175, 200, 225, 250],
    }

    rows = []
    for param, values in grids.items():
        for v in values:
            cfg = StrategyConfig()
            setattr(cfg, param, v)
            m = run_one(master_full, mask, cfg)
            rows.append({
                "param": param,
                "value": v,
                "cagr": m["cagr"],
                "max_drawdown": m["max_drawdown"],
                "sharpe": m["sharpe"],
                "total_return": m["total_return"],
            })
            print(f"{param}={v}: CAGR={m['cagr']:.2%}  DD={m['max_drawdown']:.2%}  Sharpe={m['sharpe']:.2f}")

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "robustness.csv", index=False)
    print("\nSaved:", RESULTS / "robustness.csv")
    print("\nPer-parameter mean/std of CAGR:")
    print(df.groupby("param")["cagr"].agg(["mean", "std"]).round(4))


if __name__ == "__main__":
    main()
