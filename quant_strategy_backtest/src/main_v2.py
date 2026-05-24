"""
Compare strategy v1 (fixed buckets, TQQQ/SPY/Cash) against
v2 (smooth scoring + QLD tier + vol-targeting + drift band).

Same data, same window, same execution model.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from analysis import buy_and_hold, equity_curve_metrics, format_metrics_table
from backtest import BacktestConfig, run_backtest
from backtest_v2 import BacktestV2Config, run_backtest_v2
from data_loader import build_master_frame, load_all
from strategy import StrategyConfig, build_signals, target_weights_frame
from strategy_v2 import StrategyV2Config, build_signals_v2, target_weights_v2

RESULTS = Path(__file__).resolve().parent.parent / "results"
REPORTS = Path(__file__).resolve().parent.parent / "reports"
RESULTS.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

START = "2018-05-24"
END = "2026-05-23"
OOS_START = "2023-01-01"


def main() -> None:
    print("[1/4] Loading data ...")
    raw = load_all(start="2017-01-01", end=END, force=False)
    master_full = build_master_frame(raw)
    mask = (master_full.index >= pd.Timestamp(START)) & (master_full.index <= pd.Timestamp(END))
    master_bt = master_full.loc[mask]
    print(f"   Window: {master_bt.index.min().date()} -> {master_bt.index.max().date()} ({len(master_bt)} bars)")

    # ---- v1 ----------------------------------------------------------------
    print("\n[2/4] Running v1 (fixed buckets, TQQQ/SPY/Cash) ...")
    cfg_s1 = StrategyConfig()
    signals_v1 = build_signals(master_full, cfg_s1)
    target_v1 = target_weights_frame(signals_v1, cfg_s1).loc[mask]
    res_v1 = run_backtest(master_bt, target_v1, BacktestConfig())
    eq_v1 = res_v1.equity
    n_trades_v1 = len(res_v1.trades)
    print(f"   v1 final: ${eq_v1.iloc[-1]:,.0f}   trades={n_trades_v1}")

    # ---- v2 default (smooth + QLD + drift-band, vol-target OFF) ------------
    print("\n[3/4] Running v2 (smooth + QLD + drift-band) ...")
    cfg_s2 = StrategyV2Config()
    signals_v2 = build_signals_v2(master_full, cfg_s2)
    target_v2 = target_weights_v2(signals_v2, master_full, cfg_s2).loc[mask]
    res_v2 = run_backtest_v2(master_bt, target_v2, BacktestV2Config())
    eq_v2 = res_v2.equity
    n_trades_v2 = len(res_v2.trades)
    print(f"   v2 final: ${eq_v2.iloc[-1]:,.0f}   trades={n_trades_v2}")

    # Also a v2 variant with vol-target ON, to attribute the contribution
    cfg_s2_voltgt = StrategyV2Config(use_vol_target=True)
    signals_v2vt = build_signals_v2(master_full, cfg_s2_voltgt)
    target_v2vt = target_weights_v2(signals_v2vt, master_full, cfg_s2_voltgt).loc[mask]
    res_v2vt = run_backtest_v2(master_bt, target_v2vt, BacktestV2Config())
    eq_v2nv = res_v2vt.equity        # keep variable name for downstream code

    # ---- Benchmarks --------------------------------------------------------
    bh_spy = buy_and_hold(master_bt, "SPY")
    bh_qqq = buy_and_hold(master_bt, "QQQ")
    bh_tqqq = buy_and_hold(master_bt, "TQQQ")

    curves = {
        "v1 (fixed buckets)": eq_v1,
        "v2 (smooth+QLD)": eq_v2,
        "v2 +vol-target 25%": eq_v2nv,
        "SPY B&H": bh_spy,
        "QQQ B&H": bh_qqq,
        "TQQQ B&H": bh_tqqq,
    }
    metrics = {name: equity_curve_metrics(c) for name, c in curves.items()}
    table = format_metrics_table(metrics)
    print("\n=== Full window (2018-05 -> 2026-05) ===")
    print(table.to_string())

    # In/OOS split for the two strategy variants
    print(f"\n=== In-sample (<= {OOS_START}) ===")
    in_metrics = {n: equity_curve_metrics(c.loc[c.index <= OOS_START])
                  for n, c in {"v1": eq_v1, "v2": eq_v2, "SPY": bh_spy, "QQQ": bh_qqq}.items()}
    print(format_metrics_table(in_metrics).to_string())

    print(f"\n=== Out-of-sample (> {OOS_START}) ===")
    oos_metrics = {n: equity_curve_metrics(c.loc[c.index > OOS_START])
                   for n, c in {"v1": eq_v1, "v2": eq_v2, "SPY": bh_spy, "QQQ": bh_qqq}.items()}
    print(format_metrics_table(oos_metrics).to_string())

    # Annual returns
    print("\n=== Annual returns ===")
    ann_rows = {}
    for name, c in {"v1": eq_v1, "v2": eq_v2, "SPY": bh_spy, "QQQ": bh_qqq, "TQQQ": bh_tqqq}.items():
        y = c.resample("YE").last().pct_change()
        first_val = c.iloc[0]
        y.iloc[0] = c.resample("YE").last().iloc[0] / first_val - 1
        ann_rows[name] = y
    ann_df = pd.DataFrame(ann_rows)
    ann_df.index = ann_df.index.year
    print(ann_df.map(lambda x: f"{x:+.2%}" if pd.notna(x) else "n/a").to_string())
    ann_df.to_csv(RESULTS / "annual_returns_v2.csv")

    # ---- Plots -------------------------------------------------------------
    print("\n[4/4] Saving plots ...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    plot_order = ["v1 (fixed buckets)", "v2 (smooth+QLD)",
                  "SPY B&H", "QQQ B&H", "TQQQ B&H"]
    for name in plot_order:
        ax1.plot(curves[name].index, curves[name].values, label=name, lw=1.3)
    ax1.set_yscale("log"); ax1.set_ylabel("Equity (log)")
    ax1.set_title("v1 vs v2 vs benchmarks")
    ax1.legend(loc="best"); ax1.grid(True, alpha=0.3)
    for name in plot_order:
        c = curves[name]; dd = c / c.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.25, label=name)
    ax2.set_ylabel("Drawdown"); ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax2.grid(True, alpha=0.3); ax2.set_xlabel("Date")
    plt.tight_layout()
    p_eq = RESULTS / "v2_equity_comparison.png"
    plt.savefig(p_eq, dpi=130); plt.close()

    # Weights comparison
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].stackplot(res_v1.weights.index, res_v1.weights["w_tqqq"],
                      res_v1.weights["w_spy"], res_v1.weights["w_cash"],
                      labels=["TQQQ", "SPY", "Cash"], colors=["C3", "C0", "lightgray"])
    axes[0].set_title("v1 actual weights"); axes[0].set_ylim(0, 1)
    axes[0].legend(loc="upper left")
    axes[1].stackplot(res_v2.weights.index, res_v2.weights["w_tqqq"],
                      res_v2.weights["w_qld"], res_v2.weights["w_spy"], res_v2.weights["w_cash"],
                      labels=["TQQQ", "QLD", "SPY", "Cash"],
                      colors=["C3", "C1", "C0", "lightgray"])
    axes[1].set_title("v2 actual weights"); axes[1].set_ylim(0, 1)
    axes[1].legend(loc="upper left")
    plt.tight_layout()
    p_w = RESULTS / "v2_weights_comparison.png"
    plt.savefig(p_w, dpi=130); plt.close()

    # Annual bar chart
    fig, ax = plt.subplots(figsize=(13, 5))
    ann_plot = ann_df[["v1", "v2", "SPY", "QQQ", "TQQQ"]]
    ann_plot.plot(kind="bar", ax=ax)
    ax.set_title("Annual returns: v1 vs v2 vs benchmarks")
    ax.set_ylabel("Return"); ax.axhline(0, color="black", lw=0.6)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    p_a = RESULTS / "v2_annual_returns.png"
    plt.savefig(p_a, dpi=130); plt.close()

    eq_v2.to_csv(RESULTS / "equity_curve_v2.csv")
    res_v2.weights.to_csv(RESULTS / "weights_actual_v2.csv")
    res_v2.trades.to_csv(RESULTS / "trades_v2.csv", index=False)
    table.to_csv(RESULTS / "metrics_summary_v2.csv")
    print(f"\nSaved: {p_eq}\n       {p_w}\n       {p_a}")

    # JSON summary
    def _safe(v):
        import datetime
        try:
            if pd.isna(v): return None
        except (TypeError, ValueError): pass
        if isinstance(v, (datetime.date, datetime.datetime)): return str(v)
        try: return float(v)
        except (TypeError, ValueError): return str(v)

    summary = {
        "window": {"start": str(master_bt.index.min().date()),
                   "end": str(master_bt.index.max().date())},
        "trades": {"v1": int(n_trades_v1), "v2": int(n_trades_v2)},
        "metrics_full": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in metrics.items()},
        "in_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in in_metrics.items()},
        "out_of_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in oos_metrics.items()},
    }
    (REPORTS / "summary_v2.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"Summary: {REPORTS / 'summary_v2.json'}")


if __name__ == "__main__":
    main()
