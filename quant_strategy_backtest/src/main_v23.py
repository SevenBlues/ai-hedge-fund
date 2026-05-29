"""
v2.1b -> v2.3 ablation: microstructure features from daily OHLC.

Variants (all extend v2.1b = v2 + credit signal; dxy/veto/atr OFF):
  v2.1b baseline
  v2.3a + close-strength (CLV) only
  v2.3b + overnight-gap momentum only
  v2.3c + range-expansion risk only
  v2.3  + all three microstructure features
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from analysis import buy_and_hold, equity_curve_metrics, format_metrics_table
from backtest_v22 import BacktestV22Config, run_backtest_v22
from data_loader import build_master_frame, load_all
from strategy_v23 import StrategyV23Config, build_signals_v23, target_weights_v23

PROJECT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT / "results"
REPORTS = PROJECT / "reports"

START = "2018-05-24"
END = "2026-05-23"
OOS_START = "2023-01-01"


def run_variant(master_full, mask, cfg: StrategyV23Config, label: str):
    signals = build_signals_v23(master_full, cfg)
    target = target_weights_v23(signals, master_full, cfg).loc[mask]
    master_bt = master_full.loc[mask]
    res = run_backtest_v22(master_bt, target, BacktestV22Config(use_atr_stop=False))
    print(f"   {label:26s} final=${res.equity.iloc[-1]:>11,.0f}  trades={len(res.trades):5d}  "
          f"composite_max={signals['composite'].max():.3f}")
    return res, signals


def main() -> None:
    print("[1/3] Loading data ...")
    raw = load_all(start="2017-01-01", end=END, force=False)
    master_full = build_master_frame(raw)
    mask = (master_full.index >= pd.Timestamp(START)) & (master_full.index <= pd.Timestamp(END))
    master_bt = master_full.loc[mask]
    print(f"   Window: {master_bt.index.min().date()} -> {master_bt.index.max().date()} ({len(master_bt)} bars)")

    print("\n[2/3] Running ablation variants ...")
    base = dict(use_credit_signal=True, use_extreme_bull=False,
                use_dxy_signal=False, use_min_veto=False)

    res_base, sig_base = run_variant(master_full, mask,
                                     StrategyV23Config(**base), "v2.1b baseline")
    res_a, sig_a = run_variant(master_full, mask,
                               StrategyV23Config(**base, use_clv_signal=True), "v2.3a close-strength")
    res_b, sig_b = run_variant(master_full, mask,
                               StrategyV23Config(**base, use_gap_signal=True), "v2.3b gap-momentum")
    res_c, sig_c = run_variant(master_full, mask,
                               StrategyV23Config(**base, use_range_signal=True), "v2.3c range-expansion")
    res_all, sig_all = run_variant(master_full, mask,
                                   StrategyV23Config(**base, use_clv_signal=True,
                                                     use_gap_signal=True, use_range_signal=True),
                                   "v2.3 (all three)")

    bh_spy = buy_and_hold(master_bt, "SPY")
    bh_qqq = buy_and_hold(master_bt, "QQQ")
    bh_tqqq = buy_and_hold(master_bt, "TQQQ")

    curves = {
        "v2.1b baseline": res_base.equity,
        "v2.3a +close-strength": res_a.equity,
        "v2.3b +gap-momentum": res_b.equity,
        "v2.3c +range-expansion": res_c.equity,
        "v2.3 (all three)": res_all.equity,
        "SPY B&H": bh_spy,
        "QQQ B&H": bh_qqq,
        "TQQQ B&H": bh_tqqq,
    }

    print("\n=== Full window ===")
    metrics_full = {n: equity_curve_metrics(c) for n, c in curves.items()}
    print(format_metrics_table(metrics_full).to_string())

    print(f"\n=== In-sample (<= {OOS_START}) ===")
    in_m = {n: equity_curve_metrics(c.loc[c.index <= OOS_START]) for n, c in curves.items()}
    print(format_metrics_table(in_m).to_string())

    print(f"\n=== Out-of-sample (> {OOS_START}) ===")
    oos_m = {n: equity_curve_metrics(c.loc[c.index > OOS_START]) for n, c in curves.items()}
    print(format_metrics_table(oos_m).to_string())

    print("\n=== Annual returns ===")
    ann_rows = {}
    for name, c in curves.items():
        y = c.resample("YE").last().pct_change()
        y.iloc[0] = c.resample("YE").last().iloc[0] / c.iloc[0] - 1
        ann_rows[name] = y
    ann_df = pd.DataFrame(ann_rows)
    ann_df.index = ann_df.index.year
    print(ann_df.map(lambda x: f"{x:+.2%}" if pd.notna(x) else "n/a").to_string())
    ann_df.to_csv(RESULTS / "annual_returns_v23.csv")

    print("\n[3/3] Saving plots ...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    plot_order = ["v2.1b baseline", "v2.3a +close-strength", "v2.3b +gap-momentum",
                  "v2.3c +range-expansion", "v2.3 (all three)", "QQQ B&H", "TQQQ B&H"]
    for name in plot_order:
        ax1.plot(curves[name].index, curves[name].values, label=name, lw=1.2)
    ax1.set_yscale("log"); ax1.set_ylabel("Equity (log)")
    ax1.set_title("v2.3 ablation: microstructure features (CLV / gap / range)")
    ax1.legend(loc="best"); ax1.grid(True, alpha=0.3)
    for name in plot_order:
        c = curves[name]; dd = c / c.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.2, label=name)
    ax2.set_ylabel("Drawdown")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax2.grid(True, alpha=0.3); ax2.set_xlabel("Date")
    plt.tight_layout()
    p1 = RESULTS / "v23_equity_comparison.png"
    plt.savefig(p1, dpi=130); plt.close()

    # Microstructure scores visualization
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    if "score_clv" in sig_a.columns:
        axes[0].plot(sig_a.index, sig_a["score_clv"], color="C0", lw=0.6, label="close-strength (CLV)")
    if "score_gap" in sig_b.columns:
        axes[1].plot(sig_b.index, sig_b["score_gap"], color="C1", lw=0.6, label="gap-momentum")
    if "score_range" in sig_c.columns:
        axes[2].plot(sig_c.index, sig_c["score_range"], color="C2", lw=0.6, label="range-expansion")
    for ax in axes:
        ax.axhline(0.5, color="black", lw=0.3); ax.set_ylim(0, 1)
        ax.legend(loc="best"); ax.grid(True, alpha=0.3)
    axes[2].set_xlabel("Date")
    plt.tight_layout()
    p2 = RESULTS / "v23_micro_scores.png"
    plt.savefig(p2, dpi=130); plt.close()

    fig, ax = plt.subplots(figsize=(13, 5))
    ann_plot = ann_df[["v2.1b baseline", "v2.3a +close-strength", "v2.3b +gap-momentum",
                       "v2.3c +range-expansion", "v2.3 (all three)", "QQQ B&H"]]
    ann_plot.plot(kind="bar", ax=ax)
    ax.set_title("Annual returns: v2.3 ablation")
    ax.set_ylabel("Return"); ax.axhline(0, color="black", lw=0.6)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    p3 = RESULTS / "v23_annual_returns.png"
    plt.savefig(p3, dpi=130); plt.close()

    format_metrics_table(metrics_full).to_csv(RESULTS / "metrics_summary_v23.csv")
    res_all.equity.to_csv(RESULTS / "equity_curve_v23.csv")

    def _safe(v):
        import datetime
        try:
            if pd.isna(v): return None
        except (TypeError, ValueError): pass
        if isinstance(v, (datetime.date, datetime.datetime)): return str(v)
        try: return float(v)
        except (TypeError, ValueError): return str(v)

    (REPORTS / "summary_v23.json").write_text(json.dumps({
        "window": {"start": str(master_bt.index.min().date()),
                   "end": str(master_bt.index.max().date())},
        "metrics_full": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in metrics_full.items()},
        "in_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in in_m.items()},
        "out_of_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in oos_m.items()},
    }, indent=2, default=str))
    print(f"\nSaved: {p1}\n       {p2}\n       {p3}")


if __name__ == "__main__":
    main()
