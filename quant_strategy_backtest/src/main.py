"""
End-to-end runner: data -> signals -> backtest -> metrics -> plots -> report.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from data_loader import build_master_frame, load_all
from strategy import StrategyConfig, build_signals, target_weights_frame
from backtest import BacktestConfig, run_backtest
from analysis import (
    annual_returns,
    buy_and_hold,
    equity_curve_metrics,
    format_metrics_table,
)
from plots import plot_annual_returns, plot_equity_curves, plot_score_and_weights

PROJECT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT / "results"
REPORTS = PROJECT / "reports"


def in_sample_out_sample_split(
    master: pd.DataFrame,
    train_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = master.loc[master.index <= train_end]
    test = master.loc[master.index > train_end]
    return train, test


def run(backtest_start: str, backtest_end: str, oos_start: str) -> dict:
    print(f"\n[1/5] Downloading data ...")
    raw = load_all(start="2017-01-01", end=backtest_end, force=False)
    master_full = build_master_frame(raw)
    # We need 252+200 days of warm-up *before* the strategy can produce a signal,
    # so load extra history before the official `backtest_start`.
    master = master_full.loc[master_full.index >= "2017-01-01"]
    print(f"   Master frame: {master.shape}, {master.index.min().date()} -> {master.index.max().date()}")

    print("\n[2/5] Building signals ...")
    cfg_strategy = StrategyConfig()
    signals = build_signals(master, cfg_strategy)
    target = target_weights_frame(signals, cfg_strategy)

    # Clip to backtest window
    mask = (master.index >= pd.Timestamp(backtest_start)) & (master.index <= pd.Timestamp(backtest_end))
    master_bt = master.loc[mask]
    target_bt = target.loc[mask]
    signals_bt = signals.loc[mask]
    print(f"   Backtest window: {master_bt.index.min().date()} -> {master_bt.index.max().date()} "
          f"({len(master_bt)} bars)")

    print("\n[3/5] Running backtest ...")
    cfg_bt = BacktestConfig()
    result = run_backtest(master_bt, target_bt, cfg_bt)
    eq = result.equity
    print(f"   Final equity: ${eq.iloc[-1]:,.2f} (start ${cfg_bt.initial_capital:,.0f})")

    print("\n[4/5] Computing benchmarks & metrics ...")
    bh_spy = buy_and_hold(master_bt, "SPY", initial=cfg_bt.initial_capital)
    bh_tqqq = buy_and_hold(master_bt, "TQQQ", initial=cfg_bt.initial_capital)
    bh_qqq = buy_and_hold(master_bt, "QQQ", initial=cfg_bt.initial_capital)

    curves = {
        "Strategy": eq,
        "SPY B&H": bh_spy,
        "QQQ B&H": bh_qqq,
        "TQQQ B&H": bh_tqqq,
    }
    metrics = {name: equity_curve_metrics(c) for name, c in curves.items()}
    table = format_metrics_table(metrics)
    print("\n=== Performance summary (full backtest window) ===")
    print(table.to_string())

    # In-sample / out-of-sample split for overfitting check
    in_eq = eq.loc[eq.index <= oos_start]
    oos_eq = eq.loc[eq.index > oos_start]
    in_bh = bh_spy.loc[bh_spy.index <= oos_start]
    oos_bh = bh_spy.loc[bh_spy.index > oos_start]
    in_qqq = bh_qqq.loc[bh_qqq.index <= oos_start]
    oos_qqq = bh_qqq.loc[bh_qqq.index > oos_start]

    print(f"\n=== In-sample window (<= {oos_start}) ===")
    in_metrics = {
        "Strategy": equity_curve_metrics(in_eq),
        "SPY B&H": equity_curve_metrics(in_bh),
        "QQQ B&H": equity_curve_metrics(in_qqq),
    }
    print(format_metrics_table(in_metrics).to_string())

    print(f"\n=== Out-of-sample window (> {oos_start}) ===")
    oos_metrics = {
        "Strategy": equity_curve_metrics(oos_eq),
        "SPY B&H": equity_curve_metrics(oos_bh),
        "QQQ B&H": equity_curve_metrics(oos_qqq),
    }
    print(format_metrics_table(oos_metrics).to_string())

    print("\n[5/5] Saving plots & report ...")
    p1 = plot_equity_curves(curves, "Strategy vs benchmarks (log scale)", "equity_curves.png")
    p2 = plot_annual_returns(curves, "annual_returns.png")
    p3 = plot_score_and_weights(signals_bt, result.weights, master_bt, "signals_and_weights.png")

    # CSV exports
    eq.to_csv(RESULTS / "equity_curve.csv")
    result.weights.to_csv(RESULTS / "weights_actual.csv")
    signals_bt.to_csv(RESULTS / "signals.csv")
    annual_returns(eq).to_csv(RESULTS / "annual_returns.csv")
    result.trades.to_csv(RESULTS / "trades.csv", index=False)
    table.to_csv(RESULTS / "metrics_summary.csv")

    def _json_safe(v):
        import datetime
        if pd.isna(v) if isinstance(v, float) else False:
            return None
        if isinstance(v, (datetime.date, datetime.datetime)):
            return str(v)
        try:
            return float(v)
        except (TypeError, ValueError):
            return str(v)

    summary = {
        "window": {"start": str(master_bt.index.min().date()),
                   "end": str(master_bt.index.max().date())},
        "metrics_full": {k: {kk: _json_safe(vv) for kk, vv in v.items()} for k, v in metrics.items()},
        "in_sample": {k: {kk: _json_safe(vv) for kk, vv in v.items()} for k, v in in_metrics.items()},
        "out_of_sample": {k: {kk: _json_safe(vv) for kk, vv in v.items()} for k, v in oos_metrics.items()},
        "plots": [str(p1.name), str(p2.name), str(p3.name)],
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {p1}\n       {p2}\n       {p3}")
    print(f"Summary: {REPORTS / 'summary.json'}")
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2018-05-24")
    ap.add_argument("--end", default="2026-05-23")
    ap.add_argument("--oos-start", default="2023-01-01",
                    help="In-sample <= this date; out-of-sample > this date")
    args = ap.parse_args()
    run(args.start, args.end, args.oos_start)
