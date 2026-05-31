"""
v2.6 -- deepen multi-asset diversification.

Builds on v2.5 with two changes:
  (a) Bond sleeve upgrade -- IRX rate-cycle as 3rd sub-score (alongside
      trend and momentum), fixing the 2022 rate-hike failure of the
      generic recipe (Sharpe 0.15 -> hopefully much better).
  (b) Two new sleeves -- EFA (international developed equity) and DBC
      (broad commodities) -- to expand the diversification basis.

Ablations (each combined with InvVol + monthly rebalance):
  v2.5  3 sleeves       Nasdaq + Gold + Bond(simple)
  v2.6a +Bond upgrade   Nasdaq + Gold + Bond(v2)
  v2.6b +EFA            Nasdaq + Gold + Bond(simple) + EFA
  v2.6c +DBC            Nasdaq + Gold + Bond(simple) + DBC
  v2.6  full            Nasdaq + Gold + Bond(v2) + EFA + DBC
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis import buy_and_hold, equity_curve_metrics, format_metrics_table
from backtest_simple import BacktestSimpleConfig, run_backtest_simple
from backtest_v22 import BacktestV22Config, run_backtest_v22
from data_loader import build_master_frame, load_all
from main_v25 import combine_equal_weight, combine_inv_vol, daily_returns
from strategy_bond import BondSleeveConfig, build_bond_signals, target_weights_bond
from strategy_simple import SimpleSleeveConfig, build_simple_signals, target_weights_simple
from strategy_v22 import StrategyV22Config, build_signals_v22, target_weights_v22

PROJECT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT / "results"
REPORTS = PROJECT / "reports"

START = "2018-05-24"
END = "2026-05-23"
OOS_START = "2023-01-01"
INITIAL = 100_000.0


def build_simple_sleeve(master_full, mask, asset_open_col, asset_close_col, label):
    cfg = SimpleSleeveConfig(label=label, asset_open_col=asset_open_col, asset_close_col=asset_close_col)
    sig = build_simple_signals(master_full, cfg)
    tgt = target_weights_simple(sig, cfg).loc[mask]
    master_bt = master_full.loc[mask]
    eq = run_backtest_simple(master_bt, tgt, asset_open_col, asset_close_col, BacktestSimpleConfig())
    return eq * (INITIAL / eq.iloc[0])


def build_bond_sleeve_v2(master_full, mask):
    cfg = BondSleeveConfig()
    sig = build_bond_signals(master_full, cfg)
    tgt = target_weights_bond(sig, cfg).loc[mask]
    master_bt = master_full.loc[mask]
    eq = run_backtest_simple(master_bt, tgt, cfg.asset_open_col, cfg.asset_close_col, BacktestSimpleConfig())
    return eq * (INITIAL / eq.iloc[0])


def build_nasdaq_sleeve(master_full, mask):
    cfg = StrategyV22Config(use_credit_signal=True, use_extreme_bull=False)
    sig = build_signals_v22(master_full, cfg)
    tgt = target_weights_v22(sig, master_full, cfg).loc[mask]
    master_bt = master_full.loc[mask]
    res = run_backtest_v22(master_bt, tgt, BacktestV22Config(use_atr_stop=False))
    return res.equity * (INITIAL / res.equity.iloc[0])


def combo_invvol_lev_match(returns, ref_returns):
    """InvVol combo levered to match ref_returns vol."""
    base = combine_inv_vol(returns, INITIAL, leverage=1.0)
    base_vol = daily_returns(base).std() * np.sqrt(252)
    target_vol = ref_returns.std() * np.sqrt(252)
    lev = target_vol / base_vol if base_vol > 0 else 1.0
    return combine_inv_vol(returns, INITIAL, leverage=lev), lev


def main() -> None:
    print("[1/4] Loading data & building 5 sleeves ...")
    raw = load_all(start="2017-01-01", end=END, force=False)
    master_full = build_master_frame(raw)
    mask = (master_full.index >= pd.Timestamp(START)) & (master_full.index <= pd.Timestamp(END))
    master_bt = master_full.loc[mask]
    print(f"   Window: {master_bt.index.min().date()} -> {master_bt.index.max().date()} ({len(master_bt)} bars)")

    eq_n = build_nasdaq_sleeve(master_full, mask)
    eq_g = build_simple_sleeve(master_full, mask, "gld_open", "gld_close", "Gold")
    eq_b1 = build_simple_sleeve(master_full, mask, "tlt_open", "tlt_close", "BondSimple")
    eq_b2 = build_bond_sleeve_v2(master_full, mask)
    eq_e = build_simple_sleeve(master_full, mask, "efa_open", "efa_close", "Intl")
    eq_d = build_simple_sleeve(master_full, mask, "dbc_open", "dbc_close", "Commod")

    for label, c in [("Nasdaq(v2.1b)", eq_n), ("Gold", eq_g),
                     ("Bond simple", eq_b1), ("Bond v2 (+rate)", eq_b2),
                     ("Intl EFA", eq_e), ("Commod DBC", eq_d)]:
        m = equity_curve_metrics(c)
        print(f"   {label:18s} CAGR={m['cagr']:>7.2%}  Sharpe={m['sharpe']:.2f}  DD={m['max_drawdown']:>7.2%}")

    print("\n[2/4] Sleeve correlations (5x5 with bond v2) ...")
    rets = {"Nasdaq": daily_returns(eq_n), "Gold": daily_returns(eq_g),
            "Bond v2": daily_returns(eq_b2), "Intl": daily_returns(eq_e),
            "Commod": daily_returns(eq_d)}
    corr = pd.DataFrame(rets).corr()
    print(corr.to_string(float_format=lambda x: f"{x:+.3f}"))

    print("\n[3/4] Building ablation combos (InvVol + 2.87x-equivalent leverage) ...")

    ref_n = daily_returns(eq_n)  # reference vol = standalone Nasdaq

    # v2.5 = 3 sleeve baseline (simple bond)
    sleeves_v25 = {"Nasdaq": rets["Nasdaq"], "Gold": rets["Gold"],
                   "Bond_simple": daily_returns(eq_b1)}
    eq_v25_iv, lev25 = combo_invvol_lev_match(sleeves_v25, ref_n)
    eq_v25_iv0 = combine_inv_vol(sleeves_v25, INITIAL, leverage=1.0)

    # v2.6a = bond upgrade
    sleeves_v26a = {"Nasdaq": rets["Nasdaq"], "Gold": rets["Gold"], "Bond_v2": rets["Bond v2"]}
    eq_v26a_iv, lev26a = combo_invvol_lev_match(sleeves_v26a, ref_n)
    eq_v26a_iv0 = combine_inv_vol(sleeves_v26a, INITIAL, leverage=1.0)

    # v2.6b = +EFA (simple bond)
    sleeves_v26b = {"Nasdaq": rets["Nasdaq"], "Gold": rets["Gold"],
                    "Bond_simple": daily_returns(eq_b1), "Intl": rets["Intl"]}
    eq_v26b_iv, lev26b = combo_invvol_lev_match(sleeves_v26b, ref_n)
    eq_v26b_iv0 = combine_inv_vol(sleeves_v26b, INITIAL, leverage=1.0)

    # v2.6c = +DBC (simple bond)
    sleeves_v26c = {"Nasdaq": rets["Nasdaq"], "Gold": rets["Gold"],
                    "Bond_simple": daily_returns(eq_b1), "Commod": rets["Commod"]}
    eq_v26c_iv, lev26c = combo_invvol_lev_match(sleeves_v26c, ref_n)
    eq_v26c_iv0 = combine_inv_vol(sleeves_v26c, INITIAL, leverage=1.0)

    # v2.6 full = bond_v2 + EFA + DBC
    sleeves_v26 = {"Nasdaq": rets["Nasdaq"], "Gold": rets["Gold"],
                   "Bond_v2": rets["Bond v2"], "Intl": rets["Intl"], "Commod": rets["Commod"]}
    eq_v26_iv, lev26 = combo_invvol_lev_match(sleeves_v26, ref_n)
    eq_v26_iv0 = combine_inv_vol(sleeves_v26, INITIAL, leverage=1.0)
    eq_v26_ew = combine_equal_weight(sleeves_v26, INITIAL)

    print(f"   Leverage to match Nasdaq vol: v2.5={lev25:.2f}x  v2.6a={lev26a:.2f}x  "
          f"v2.6b={lev26b:.2f}x  v2.6c={lev26c:.2f}x  v2.6={lev26:.2f}x")

    curves = {
        "Nasdaq (v2.1b)": eq_n,
        "v2.5 InvVol":       eq_v25_iv0,
        "v2.5 InvVol+lev":   eq_v25_iv,
        "v2.6a (bond v2)":   eq_v26a_iv0,
        "v2.6a +lev":        eq_v26a_iv,
        "v2.6b (+EFA)":      eq_v26b_iv0,
        "v2.6b +lev":        eq_v26b_iv,
        "v2.6c (+DBC)":      eq_v26c_iv0,
        "v2.6c +lev":        eq_v26c_iv,
        "v2.6 EW(5)":        eq_v26_ew,
        "v2.6 InvVol(5)":    eq_v26_iv0,
        "v2.6 InvVol+lev":   eq_v26_iv,
        "SPY B&H":           buy_and_hold(master_bt, "SPY", initial=INITIAL),
        "QQQ B&H":           buy_and_hold(master_bt, "QQQ", initial=INITIAL),
    }

    print("\n=== Full window (key rows) ===")
    metrics_full = {k: equity_curve_metrics(v) for k, v in curves.items()}
    print(format_metrics_table(metrics_full).to_string())

    print(f"\n=== Out-of-sample (> {OOS_START}) ===")
    oos_m = {k: equity_curve_metrics(v.loc[v.index > OOS_START]) for k, v in curves.items()}
    print(format_metrics_table(oos_m).to_string())

    print("\n=== Annual returns (selected) ===")
    show_ann = ["Nasdaq (v2.1b)", "v2.5 InvVol", "v2.6 InvVol(5)",
                "v2.6 InvVol+lev", "QQQ B&H"]
    ann_rows = {}
    for name in show_ann:
        c = curves[name]
        y = c.resample("YE").last().pct_change()
        y.iloc[0] = c.resample("YE").last().iloc[0] / c.iloc[0] - 1
        ann_rows[name] = y
    ann_df = pd.DataFrame(ann_rows); ann_df.index = ann_df.index.year
    print(ann_df.map(lambda x: f"{x:+.2%}" if pd.notna(x) else "n/a").to_string())
    ann_df.to_csv(RESULTS / "annual_returns_v26.csv")

    # Plots
    print("\n[4/4] Saving plots ...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    show = ["Nasdaq (v2.1b)", "v2.5 InvVol+lev", "v2.6 InvVol+lev",
            "v2.6 InvVol(5)", "QQQ B&H"]
    for n in show:
        ax1.plot(curves[n].index, curves[n].values, label=n, lw=1.3)
    ax1.set_yscale("log"); ax1.set_ylabel("Equity (log)")
    ax1.set_title("v2.6 deepened diversification (bond v2 + EFA + DBC)")
    ax1.legend(loc="best"); ax1.grid(True, alpha=0.3)
    for n in show:
        c = curves[n]; dd = c / c.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.22, label=n)
    ax2.set_ylabel("Drawdown"); ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax2.grid(True, alpha=0.3); ax2.set_xlabel("Date")
    plt.tight_layout()
    p1 = RESULTS / "v26_equity_comparison.png"
    plt.savefig(p1, dpi=130); plt.close()

    # Correlation matrix
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns))); ax.set_xticklabels(corr.columns, rotation=30)
    ax.set_yticks(range(len(corr.index))); ax.set_yticklabels(corr.index)
    for i in range(len(corr.index)):
        for j in range(len(corr.columns)):
            ax.text(j, i, f"{corr.iloc[i,j]:+.2f}", ha="center", va="center", color="black", fontsize=9)
    ax.set_title("Daily-return correlation: 5 sleeves")
    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    p2 = RESULTS / "v26_correlation.png"
    plt.savefig(p2, dpi=130); plt.close()

    # Bond comparison
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(eq_b1.index, eq_b1.values, label=f"Bond simple (Sharpe {equity_curve_metrics(eq_b1)['sharpe']:.2f})", lw=1.3)
    ax.plot(eq_b2.index, eq_b2.values, label=f"Bond v2 +rate (Sharpe {equity_curve_metrics(eq_b2)['sharpe']:.2f})", lw=1.3)
    ax.set_yscale("log"); ax.set_ylabel("Equity (log)")
    ax.set_title("Bond sleeve: simple vs +rate-signal upgrade")
    ax.legend(loc="best"); ax.grid(True, alpha=0.3)
    plt.tight_layout()
    p3 = RESULTS / "v26_bond_upgrade.png"
    plt.savefig(p3, dpi=130); plt.close()

    format_metrics_table(metrics_full).to_csv(RESULTS / "metrics_summary_v26.csv")
    eq_v26_iv.to_csv(RESULTS / "equity_curve_v26_invvol_lev.csv")
    eq_v26_iv0.to_csv(RESULTS / "equity_curve_v26_invvol.csv")
    corr.to_csv(RESULTS / "v26_correlation.csv")

    def _safe(v):
        import datetime
        try:
            if pd.isna(v): return None
        except (TypeError, ValueError): pass
        if isinstance(v, (datetime.date, datetime.datetime)): return str(v)
        try: return float(v)
        except (TypeError, ValueError): return str(v)

    (REPORTS / "summary_v26.json").write_text(json.dumps({
        "window": {"start": str(master_bt.index.min().date()),
                   "end": str(master_bt.index.max().date())},
        "correlations": corr.to_dict(),
        "leverage_matched": {"v2.5": float(lev25), "v2.6a": float(lev26a),
                              "v2.6b": float(lev26b), "v2.6c": float(lev26c),
                              "v2.6": float(lev26)},
        "metrics_full": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in metrics_full.items()},
        "out_of_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in oos_m.items()},
    }, indent=2, default=str))
    print(f"\nSaved: {p1}\n       {p2}\n       {p3}")


if __name__ == "__main__":
    main()
