"""
v3 strategy runner & comparison vs v1, v2, TQQQ B&H, QQQ B&H, SPY B&H.

v3 is a single-asset (TQQQ) variant: regime gate from v2 composite,
plus a 5%-step rebalancing band around TQQQ's 20d SMA.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from analysis import buy_and_hold, equity_curve_metrics, format_metrics_table
from backtest import BacktestConfig, run_backtest          # reuse v1 engine
from backtest_v2 import BacktestV2Config, run_backtest_v2
from data_loader import build_master_frame, load_all
from strategy import StrategyConfig, build_signals, target_weights_frame
from strategy_v2 import StrategyV2Config, build_signals_v2, target_weights_v2
from strategy_v3 import StrategyV3Config, build_signals_v3, target_weights_v3

PROJECT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT / "results"
REPORTS = PROJECT / "reports"
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
    print("\n[2/4] Running v1 ...")
    cfg_s1 = StrategyConfig()
    sig_v1 = build_signals(master_full, cfg_s1)
    tgt_v1 = target_weights_frame(sig_v1, cfg_s1).loc[mask]
    res_v1 = run_backtest(master_bt, tgt_v1, BacktestConfig())
    eq_v1 = res_v1.equity
    print(f"   v1  final: ${eq_v1.iloc[-1]:,.0f}  trades={len(res_v1.trades)}")

    # ---- v2 ----------------------------------------------------------------
    print("\n   Running v2 ...")
    cfg_s2 = StrategyV2Config()
    sig_v2 = build_signals_v2(master_full, cfg_s2)
    tgt_v2 = target_weights_v2(sig_v2, master_full, cfg_s2).loc[mask]
    res_v2 = run_backtest_v2(master_bt, tgt_v2, BacktestV2Config())
    eq_v2 = res_v2.equity
    print(f"   v2  final: ${eq_v2.iloc[-1]:,.0f}  trades={len(res_v2.trades)}")

    # ---- v3 (gate + bands, TQQQ-only) -------------------------------------
    print("\n[3/4] Running v3 (gate + rebalancing bands, TQQQ-only) ...")
    cfg_s3 = StrategyV3Config()
    sig_v3 = build_signals_v3(master_full, cfg_s3)
    tgt_v3 = target_weights_v3(sig_v3, master_full, cfg_s3).loc[mask]
    # Reuse v1 engine: it takes a (w_tqqq, w_spy, w_cash) frame.
    tgt_v3_eng = tgt_v3[["w_tqqq", "w_spy", "w_cash", "score"]].copy()
    res_v3 = run_backtest(master_bt, tgt_v3_eng, BacktestConfig())
    eq_v3 = res_v3.equity
    print(f"   v3  final: ${eq_v3.iloc[-1]:,.0f}  trades={len(res_v3.trades)}")

    # ---- Benchmarks --------------------------------------------------------
    bh_spy = buy_and_hold(master_bt, "SPY")
    bh_qqq = buy_and_hold(master_bt, "QQQ")
    bh_tqqq = buy_and_hold(master_bt, "TQQQ")

    # --- A TQQQ-only buy & hold with regime gate ON/OFF only (no bands)
    # to isolate the contribution of bands vs gate alone
    print("\n   Running v3b (gate only, no bands) for attribution ...")
    cfg_s3b = StrategyV3Config(band_weight_step=0.0)   # bands disabled
    sig_v3b = build_signals_v3(master_full, cfg_s3b)
    tgt_v3b = target_weights_v3(sig_v3b, master_full, cfg_s3b).loc[mask]
    res_v3b = run_backtest(master_bt,
                            tgt_v3b[["w_tqqq", "w_spy", "w_cash", "score"]].copy(),
                            BacktestConfig())
    eq_v3b = res_v3b.equity
    print(f"   v3b final: ${eq_v3b.iloc[-1]:,.0f}  trades={len(res_v3b.trades)}")

    curves = {
        "v1 (buckets, TQQQ/SPY)": eq_v1,
        "v2 (smooth+QLD)": eq_v2,
        "v3 (gate+bands, TQQQ only)": eq_v3,
        "v3b (gate only, no bands)": eq_v3b,
        "SPY B&H": bh_spy,
        "QQQ B&H": bh_qqq,
        "TQQQ B&H": bh_tqqq,
    }
    metrics = {name: equity_curve_metrics(c) for name, c in curves.items()}
    print("\n=== Full window (2018-05 -> 2026-05) ===")
    print(format_metrics_table(metrics).to_string())

    # In/OOS
    print(f"\n=== In-sample (<= {OOS_START}) ===")
    in_m = {n: equity_curve_metrics(c.loc[c.index <= OOS_START])
            for n, c in {"v1": eq_v1, "v2": eq_v2, "v3": eq_v3,
                         "v3b": eq_v3b, "TQQQ": bh_tqqq, "QQQ": bh_qqq}.items()}
    print(format_metrics_table(in_m).to_string())

    print(f"\n=== Out-of-sample (> {OOS_START}) ===")
    oos_m = {n: equity_curve_metrics(c.loc[c.index > OOS_START])
             for n, c in {"v1": eq_v1, "v2": eq_v2, "v3": eq_v3,
                          "v3b": eq_v3b, "TQQQ": bh_tqqq, "QQQ": bh_qqq}.items()}
    print(format_metrics_table(oos_m).to_string())

    # Annual returns
    print("\n=== Annual returns ===")
    ann_rows = {}
    for name, c in {"v1": eq_v1, "v2": eq_v2, "v3": eq_v3, "v3b": eq_v3b,
                    "SPY": bh_spy, "QQQ": bh_qqq, "TQQQ": bh_tqqq}.items():
        y = c.resample("YE").last().pct_change()
        y.iloc[0] = c.resample("YE").last().iloc[0] / c.iloc[0] - 1
        ann_rows[name] = y
    ann_df = pd.DataFrame(ann_rows)
    ann_df.index = ann_df.index.year
    print(ann_df.map(lambda x: f"{x:+.2%}" if pd.notna(x) else "n/a").to_string())
    ann_df.to_csv(RESULTS / "annual_returns_v3.csv")

    # ---- Plots -------------------------------------------------------------
    print("\n[4/4] Saving plots ...")

    # Equity + drawdown
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    plot_order = ["v1 (buckets, TQQQ/SPY)", "v2 (smooth+QLD)",
                  "v3 (gate+bands, TQQQ only)", "QQQ B&H", "TQQQ B&H"]
    for name in plot_order:
        ax1.plot(curves[name].index, curves[name].values, label=name, lw=1.3)
    ax1.set_yscale("log"); ax1.set_ylabel("Equity (log)")
    ax1.set_title("v1 vs v2 vs v3 vs benchmarks")
    ax1.legend(loc="best"); ax1.grid(True, alpha=0.3)
    for name in plot_order:
        c = curves[name]; dd = c / c.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.22, label=name)
    ax2.set_ylabel("Drawdown")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax2.grid(True, alpha=0.3); ax2.set_xlabel("Date")
    plt.tight_layout()
    p_eq = RESULTS / "v3_equity_comparison.png"
    plt.savefig(p_eq, dpi=130); plt.close()

    # v3 weights & deviation
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    axes[0].plot(master_bt.index, master_bt["tqqq_close"], color="C3", lw=0.8, label="TQQQ")
    sma = master_bt["tqqq_close"].rolling(cfg_s3.sma_days).mean()
    axes[0].plot(master_bt.index, sma, color="black", lw=0.7, label=f"{cfg_s3.sma_days}d SMA")
    axes[0].set_yscale("log"); axes[0].set_ylabel("TQQQ"); axes[0].legend(loc="best")
    axes[0].grid(True, alpha=0.3)
    axes[1].plot(tgt_v3.index, tgt_v3["deviation"] * 100, lw=0.7, color="C2")
    axes[1].axhline(0, color="black", lw=0.4)
    axes[1].axhline(25, color="red", lw=0.4, ls=":")
    axes[1].axhline(-25, color="green", lw=0.4, ls=":")
    axes[1].set_ylabel("TQQQ vs SMA (%)"); axes[1].grid(True, alpha=0.3)
    axes[2].stackplot(res_v3.weights.index, res_v3.weights["w_tqqq"], res_v3.weights["w_cash"],
                      labels=["TQQQ", "Cash"], colors=["C3", "lightgray"])
    axes[2].set_ylim(0, 1); axes[2].set_ylabel("v3 weights")
    axes[2].legend(loc="upper left")
    plt.tight_layout()
    p_w = RESULTS / "v3_signals_and_weights.png"
    plt.savefig(p_w, dpi=130); plt.close()

    # Annual bars
    fig, ax = plt.subplots(figsize=(13, 5))
    ann_plot = ann_df[["v1", "v2", "v3", "v3b", "QQQ", "TQQQ"]]
    ann_plot.plot(kind="bar", ax=ax)
    ax.set_title("Annual returns: v1 vs v2 vs v3 vs benchmarks")
    ax.set_ylabel("Return"); ax.axhline(0, color="black", lw=0.6)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    p_a = RESULTS / "v3_annual_returns.png"
    plt.savefig(p_a, dpi=130); plt.close()

    eq_v3.to_csv(RESULTS / "equity_curve_v3.csv")
    res_v3.weights.to_csv(RESULTS / "weights_actual_v3.csv")
    res_v3.trades.to_csv(RESULTS / "trades_v3.csv", index=False)
    tgt_v3.to_csv(RESULTS / "target_weights_v3.csv")
    format_metrics_table(metrics).to_csv(RESULTS / "metrics_summary_v3.csv")

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
        "metrics_full": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in metrics.items()},
        "in_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in in_m.items()},
        "out_of_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in oos_m.items()},
    }
    (REPORTS / "summary_v3.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {p_eq}\n       {p_w}\n       {p_a}")
    print(f"Summary: {REPORTS / 'summary_v3.json'}")


if __name__ == "__main__":
    main()
