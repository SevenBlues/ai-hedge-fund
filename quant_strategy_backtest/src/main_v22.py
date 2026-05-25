"""
v2.1b -> v2.2 ablation: ATR dynamic stop, DXY signal, min-aggregation veto.

Variants (all extend v2.1b = v2 + credit signal):
  v2.1b baseline
  v2.2a + ATR dynamic stop only
  v2.2b + DXY signal only
  v2.2c + min-veto only
  v2.2  + all three
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
from strategy_v22 import StrategyV22Config, build_signals_v22, target_weights_v22

PROJECT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT / "results"
REPORTS = PROJECT / "reports"

START = "2018-05-24"
END = "2026-05-23"
OOS_START = "2023-01-01"


def run_variant(master_full, mask, cfg_strategy: StrategyV22Config,
                cfg_engine: BacktestV22Config, label: str):
    signals = build_signals_v22(master_full, cfg_strategy)
    target = target_weights_v22(signals, master_full, cfg_strategy).loc[mask]
    master_bt = master_full.loc[mask]
    res = run_backtest_v22(master_bt, target, cfg_engine)
    extras = []
    if cfg_strategy.use_dxy_signal: extras.append("DXY")
    if cfg_strategy.use_min_veto: extras.append("minVeto")
    if cfg_engine.use_atr_stop: extras.append("ATRstop")
    if not extras: extras = ["baseline"]
    n_stops = (res.diagnostics["stop_used"].notna() & (res.diagnostics["stop_used"] < 0)).sum()
    n_real_stops = sum(1 for t in res.trades.itertuples()
                       if hasattr(t, "event") and t.event == "STOP")
    print(f"   {label:24s} final=${res.equity.iloc[-1]:>11,.0f}  trades={len(res.trades):5d}  "
          f"composite_max={signals['composite'].max():.3f}  STOP-triggers={n_real_stops}")
    return res, signals


def main() -> None:
    print("[1/3] Loading data ...")
    raw = load_all(start="2017-01-01", end=END, force=False)
    master_full = build_master_frame(raw)
    mask = (master_full.index >= pd.Timestamp(START)) & (master_full.index <= pd.Timestamp(END))
    master_bt = master_full.loc[mask]
    print(f"   Window: {master_bt.index.min().date()} -> {master_bt.index.max().date()} ({len(master_bt)} bars)")

    print("\n[2/3] Running ablation variants ...")

    # Baseline = v2.1b (credit ON, everything else off)
    cfg_base = StrategyV22Config(use_credit_signal=True, use_extreme_bull=False)
    eng_base = BacktestV22Config(use_atr_stop=False)
    res_base, sig_base = run_variant(master_full, mask, cfg_base, eng_base, "v2.1b baseline")

    # v2.2a = + ATR stop
    cfg_a = StrategyV22Config(use_credit_signal=True, use_extreme_bull=False)
    eng_a = BacktestV22Config(use_atr_stop=True, atr_k=3.0)
    res_a, sig_a = run_variant(master_full, mask, cfg_a, eng_a, "v2.2a ATR stop")

    # v2.2b = + DXY signal
    cfg_b = StrategyV22Config(use_credit_signal=True, use_extreme_bull=False, use_dxy_signal=True)
    eng_b = BacktestV22Config(use_atr_stop=False)
    res_b, sig_b = run_variant(master_full, mask, cfg_b, eng_b, "v2.2b DXY signal")

    # v2.2c = + min-veto
    cfg_c = StrategyV22Config(use_credit_signal=True, use_extreme_bull=False, use_min_veto=True)
    eng_c = BacktestV22Config(use_atr_stop=False)
    res_c, sig_c = run_variant(master_full, mask, cfg_c, eng_c, "v2.2c min-veto")

    # v2.2 = all three
    cfg_all = StrategyV22Config(use_credit_signal=True, use_extreme_bull=False, use_dxy_signal=True, use_min_veto=True)
    eng_all = BacktestV22Config(use_atr_stop=True, atr_k=3.0)
    res_all, sig_all = run_variant(master_full, mask, cfg_all, eng_all, "v2.2 (all three)")

    bh_spy = buy_and_hold(master_bt, "SPY")
    bh_qqq = buy_and_hold(master_bt, "QQQ")
    bh_tqqq = buy_and_hold(master_bt, "TQQQ")

    curves = {
        "v2.1b baseline": res_base.equity,
        "v2.2a +ATR stop": res_a.equity,
        "v2.2b +DXY": res_b.equity,
        "v2.2c +min-veto": res_c.equity,
        "v2.2 (all three)": res_all.equity,
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
    ann_df.to_csv(RESULTS / "annual_returns_v22.csv")

    # Plots
    print("\n[3/3] Saving plots ...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    plot_order = ["v2.1b baseline", "v2.2a +ATR stop", "v2.2b +DXY",
                  "v2.2c +min-veto", "v2.2 (all three)", "QQQ B&H", "TQQQ B&H"]
    for name in plot_order:
        ax1.plot(curves[name].index, curves[name].values, label=name, lw=1.2)
    ax1.set_yscale("log"); ax1.set_ylabel("Equity (log)")
    ax1.set_title("v2.2 ablation: ATR stop + DXY + min-veto")
    ax1.legend(loc="best"); ax1.grid(True, alpha=0.3)
    for name in plot_order:
        c = curves[name]; dd = c / c.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.2, label=name)
    ax2.set_ylabel("Drawdown")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax2.grid(True, alpha=0.3); ax2.set_xlabel("Date")
    plt.tight_layout()
    p1 = RESULTS / "v22_equity_comparison.png"
    plt.savefig(p1, dpi=130); plt.close()

    # Composite distributions: show veto effect & DXY contribution
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    axes[0].plot(sig_base.index, sig_base["composite"], label="v2.1b", lw=0.7)
    axes[0].plot(sig_c.index, sig_c["composite"], label="v2.2c (min-veto)", lw=0.7, alpha=0.8)
    axes[0].plot(sig_all.index, sig_all["composite"], label="v2.2 all", lw=0.7, alpha=0.8)
    axes[0].axhline(0.75, color="green", lw=0.3, ls="--")
    axes[0].set_ylabel("Composite"); axes[0].legend(loc="best"); axes[0].grid(True, alpha=0.3)
    if "score_dxy" in sig_b.columns:
        axes[1].plot(sig_b.index, sig_b["score_dxy"], color="C2", lw=0.7, label="DXY score")
        axes[1].axhline(0.5, color="black", lw=0.3)
        axes[1].set_ylabel("DXY score"); axes[1].set_ylim(0, 1)
        axes[1].legend(loc="best"); axes[1].grid(True, alpha=0.3)
    # ATR threshold over time
    diag_a = res_a.diagnostics
    axes[2].plot(diag_a.index, diag_a["stop_used"] * 100, color="C3", lw=0.6, label="ATR stop (%)")
    axes[2].axhline(-12, color="black", lw=0.4, ls="--", label="fixed -12%")
    axes[2].set_ylabel("Stop threshold (%)")
    axes[2].legend(loc="best"); axes[2].grid(True, alpha=0.3)
    plt.tight_layout()
    p2 = RESULTS / "v22_signals.png"
    plt.savefig(p2, dpi=130); plt.close()

    fig, ax = plt.subplots(figsize=(13, 5))
    ann_plot = ann_df[["v2.1b baseline", "v2.2a +ATR stop", "v2.2b +DXY",
                        "v2.2c +min-veto", "v2.2 (all three)", "QQQ B&H"]]
    ann_plot.plot(kind="bar", ax=ax)
    ax.set_title("Annual returns: v2.2 ablation")
    ax.set_ylabel("Return"); ax.axhline(0, color="black", lw=0.6)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    p3 = RESULTS / "v22_annual_returns.png"
    plt.savefig(p3, dpi=130); plt.close()

    format_metrics_table(metrics_full).to_csv(RESULTS / "metrics_summary_v22.csv")
    res_all.equity.to_csv(RESULTS / "equity_curve_v22.csv")

    def _safe(v):
        import datetime
        try:
            if pd.isna(v): return None
        except (TypeError, ValueError): pass
        if isinstance(v, (datetime.date, datetime.datetime)): return str(v)
        try: return float(v)
        except (TypeError, ValueError): return str(v)

    (REPORTS / "summary_v22.json").write_text(json.dumps({
        "window": {"start": str(master_bt.index.min().date()),
                   "end": str(master_bt.index.max().date())},
        "metrics_full": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in metrics_full.items()},
        "in_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in in_m.items()},
        "out_of_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in oos_m.items()},
    }, indent=2, default=str))
    print(f"\nSaved: {p1}\n       {p2}\n       {p3}")


if __name__ == "__main__":
    main()
