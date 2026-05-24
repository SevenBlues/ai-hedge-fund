"""
v2 → v2.1 ablation study.

Variants (all share the same data, execution model, costs):
  v2          : baseline (smooth + QLD)
  v2.1a       : v2 + extreme-bull tier expansion only
  v2.1b       : v2 + credit-spread signal only
  v2.1        : v2 + BOTH improvements

Reports full-window, in-sample (<= 2023-01-01), OOS (> 2023-01-01),
and per-year breakdown so the contribution of each change is visible.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from analysis import buy_and_hold, equity_curve_metrics, format_metrics_table
from backtest_v2 import BacktestV2Config, run_backtest_v2
from data_loader import build_master_frame, load_all
from strategy_v2 import StrategyV2Config, build_signals_v2, target_weights_v2
from strategy_v21 import StrategyV21Config, build_signals_v21, target_weights_v21

PROJECT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT / "results"
REPORTS = PROJECT / "reports"

START = "2018-05-24"
END = "2026-05-23"
OOS_START = "2023-01-01"


def run_strategy_v21(master_full, mask, cfg: StrategyV21Config, label: str):
    signals = build_signals_v21(master_full, cfg)
    target = target_weights_v21(signals, master_full, cfg).loc[mask]
    master_bt = master_full.loc[mask]
    res = run_backtest_v2(master_bt, target, BacktestV2Config())
    print(f"   {label:14s} final=${res.equity.iloc[-1]:>11,.0f}  trades={len(res.trades):5d}  composite_max={signals['composite'].max():.3f}")
    return res, signals


def main() -> None:
    print("[1/3] Loading data ...")
    raw = load_all(start="2017-01-01", end=END, force=False)
    master_full = build_master_frame(raw)
    mask = (master_full.index >= pd.Timestamp(START)) & (master_full.index <= pd.Timestamp(END))
    master_bt = master_full.loc[mask]
    print(f"   Window: {master_bt.index.min().date()} -> {master_bt.index.max().date()} "
          f"({len(master_bt)} bars)")

    # ---- v2 baseline (re-run for an apples-to-apples comparison) -----------
    print("\n[2/3] Running ablation variants ...")
    cfg_v2 = StrategyV2Config()
    sig_v2 = build_signals_v2(master_full, cfg_v2)
    tgt_v2 = target_weights_v2(sig_v2, master_full, cfg_v2).loc[mask]
    res_v2 = run_backtest_v2(master_bt, tgt_v2, BacktestV2Config())
    eq_v2 = res_v2.equity
    print(f"   {'v2 baseline':14s} final=${eq_v2.iloc[-1]:>11,.0f}  trades={len(res_v2.trades):5d}  composite_max={sig_v2['composite'].max():.3f}")

    # v2.1a = extreme-bull only
    res_a, sig_a = run_strategy_v21(master_full, mask,
                                     StrategyV21Config(use_extreme_bull=True,
                                                       use_credit_signal=False),
                                     "v2.1a ext-bull")
    eq_a = res_a.equity

    # v2.1b = credit signal only
    res_b, sig_b = run_strategy_v21(master_full, mask,
                                     StrategyV21Config(use_extreme_bull=False,
                                                       use_credit_signal=True),
                                     "v2.1b credit")
    eq_b = res_b.equity

    # v2.1 = both
    res_full, sig_full = run_strategy_v21(master_full, mask,
                                           StrategyV21Config(use_extreme_bull=True,
                                                             use_credit_signal=True),
                                           "v2.1 (both)")
    eq_full = res_full.equity

    bh_spy = buy_and_hold(master_bt, "SPY")
    bh_qqq = buy_and_hold(master_bt, "QQQ")
    bh_tqqq = buy_and_hold(master_bt, "TQQQ")

    curves = {
        "v2 (baseline)": eq_v2,
        "v2.1a ext-bull only": eq_a,
        "v2.1b credit only": eq_b,
        "v2.1 (both)": eq_full,
        "SPY B&H": bh_spy,
        "QQQ B&H": bh_qqq,
        "TQQQ B&H": bh_tqqq,
    }

    print("\n=== Full window (2018-05 -> 2026-05) ===")
    metrics_full = {n: equity_curve_metrics(c) for n, c in curves.items()}
    print(format_metrics_table(metrics_full).to_string())

    print(f"\n=== In-sample (<= {OOS_START}) ===")
    in_m = {n: equity_curve_metrics(c.loc[c.index <= OOS_START])
            for n, c in curves.items()}
    print(format_metrics_table(in_m).to_string())

    print(f"\n=== Out-of-sample (> {OOS_START}) ===")
    oos_m = {n: equity_curve_metrics(c.loc[c.index > OOS_START])
             for n, c in curves.items()}
    print(format_metrics_table(oos_m).to_string())

    # Annual
    print("\n=== Annual returns ===")
    ann_rows = {}
    for name, c in curves.items():
        y = c.resample("YE").last().pct_change()
        y.iloc[0] = c.resample("YE").last().iloc[0] / c.iloc[0] - 1
        ann_rows[name] = y
    ann_df = pd.DataFrame(ann_rows)
    ann_df.index = ann_df.index.year
    print(ann_df.map(lambda x: f"{x:+.2%}" if pd.notna(x) else "n/a").to_string())
    ann_df.to_csv(RESULTS / "annual_returns_v21.csv")

    # ---- Plots -------------------------------------------------------------
    print("\n[3/3] Saving plots ...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    plot_order = ["v2 (baseline)", "v2.1a ext-bull only",
                  "v2.1b credit only", "v2.1 (both)",
                  "QQQ B&H", "TQQQ B&H"]
    for name in plot_order:
        ax1.plot(curves[name].index, curves[name].values, label=name, lw=1.3)
    ax1.set_yscale("log"); ax1.set_ylabel("Equity (log)")
    ax1.set_title("v2 → v2.1 ablation: extreme-bull tier + credit-spread signal")
    ax1.legend(loc="best"); ax1.grid(True, alpha=0.3)
    for name in plot_order:
        c = curves[name]; dd = c / c.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.22, label=name)
    ax2.set_ylabel("Drawdown")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax2.grid(True, alpha=0.3); ax2.set_xlabel("Date")
    plt.tight_layout()
    p1 = RESULTS / "v21_equity_comparison.png"
    plt.savefig(p1, dpi=130); plt.close()

    # Composite distributions: did adding credit really change anything?
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(sig_v2.index, sig_v2["composite"], label="v2 composite (6 signals)", lw=0.6)
    axes[0].plot(sig_full.index, sig_full["composite"], label="v2.1 composite (7 signals)",
                 lw=0.6, alpha=0.8)
    axes[0].axhline(0.75, color="green", lw=0.4, ls="--", label="TQQQ tier")
    axes[0].axhline(0.85, color="red", lw=0.4, ls="--", label="extreme-bull")
    axes[0].set_ylabel("Composite"); axes[0].legend(loc="best"); axes[0].grid(True, alpha=0.3)
    if "score_credit" in sig_full.columns:
        axes[1].plot(sig_full.index, sig_full["score_credit"], color="C3", lw=0.7,
                     label="credit score (HYG/IEF)")
        axes[1].axhline(0.5, color="black", lw=0.3)
        axes[1].set_ylabel("Credit score"); axes[1].set_ylim(0, 1)
        axes[1].legend(loc="best"); axes[1].grid(True, alpha=0.3)
    plt.tight_layout()
    p2 = RESULTS / "v21_composite_credit.png"
    plt.savefig(p2, dpi=130); plt.close()

    # Annual bar
    fig, ax = plt.subplots(figsize=(13, 5))
    ann_plot = ann_df[["v2 (baseline)", "v2.1a ext-bull only",
                        "v2.1b credit only", "v2.1 (both)",
                        "QQQ B&H", "TQQQ B&H"]]
    ann_plot.plot(kind="bar", ax=ax)
    ax.set_title("Annual returns: ablation")
    ax.set_ylabel("Return"); ax.axhline(0, color="black", lw=0.6)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    p3 = RESULTS / "v21_annual_returns.png"
    plt.savefig(p3, dpi=130); plt.close()

    eq_full.to_csv(RESULTS / "equity_curve_v21.csv")
    res_full.weights.to_csv(RESULTS / "weights_actual_v21.csv")
    res_full.trades.to_csv(RESULTS / "trades_v21.csv", index=False)
    format_metrics_table(metrics_full).to_csv(RESULTS / "metrics_summary_v21.csv")

    def _safe(v):
        import datetime
        try:
            if pd.isna(v): return None
        except (TypeError, ValueError): pass
        if isinstance(v, (datetime.date, datetime.datetime)): return str(v)
        try: return float(v)
        except (TypeError, ValueError): return str(v)

    (REPORTS / "summary_v21.json").write_text(json.dumps({
        "window": {"start": str(master_bt.index.min().date()),
                   "end": str(master_bt.index.max().date())},
        "metrics_full": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in metrics_full.items()},
        "in_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in in_m.items()},
        "out_of_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in oos_m.items()},
    }, indent=2, default=str))
    print(f"\nSaved: {p1}\n       {p2}\n       {p3}")


if __name__ == "__main__":
    main()
