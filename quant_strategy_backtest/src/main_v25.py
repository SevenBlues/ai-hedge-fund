"""
v2.5 -- multi-asset diversification.

Three sleeves run independently:
  N : Nasdaq  -- the existing v2.1b (TQQQ/QLD/SPY/cash + 7 macro signals)
  G : Gold    -- GLD vs cash, generic trend + 12m momentum
  B : LongBd  -- TLT vs cash, generic trend + 12m momentum

Sleeves combined into portfolios via three protocols:
  EW          : 1/3, 1/3, 1/3, monthly rebalance
  InvVol      : weights inversely proportional to 60d realised vol
  InvVol+lev  : same, then constant levered to match v2.1b's standalone
                vol (a fair "same-risk-budget" comparison)

Notes on overfitting: the Gold and LongBd sleeves use identical
hyperparameters (200d SMA, 252d momentum, sigmoid scales 0.05/0.15) --
no per-asset tuning. This is the classic time-series-momentum recipe
from Moskowitz/Pedersen 2012 used unchanged on each asset.
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
from strategy_simple import SimpleSleeveConfig, build_simple_signals, target_weights_simple
from strategy_v22 import StrategyV22Config, build_signals_v22, target_weights_v22

PROJECT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT / "results"
REPORTS = PROJECT / "reports"

START = "2018-05-24"
END = "2026-05-23"
OOS_START = "2023-01-01"


def build_sleeve(master_full, mask, cfg_sleeve: SimpleSleeveConfig) -> pd.Series:
    signals = build_simple_signals(master_full, cfg_sleeve)
    target = target_weights_simple(signals, cfg_sleeve).loc[mask]
    master_bt = master_full.loc[mask]
    return run_backtest_simple(master_bt, target,
                                 cfg_sleeve.asset_open_col, cfg_sleeve.asset_close_col,
                                 BacktestSimpleConfig())


def daily_returns(eq: pd.Series) -> pd.Series:
    return eq.pct_change().fillna(0.0)


def combine_equal_weight(returns: dict[str, pd.Series], initial: float,
                          rebal_days: int = 21) -> pd.Series:
    """1/N weights, rebalanced every `rebal_days` trading days."""
    idx = next(iter(returns.values())).index
    n_assets = len(returns)
    R = pd.DataFrame(returns).reindex(idx).fillna(0.0).values
    eq = np.zeros(len(idx))
    sleeves = np.full(n_assets, initial / n_assets)
    eq[0] = initial
    for t in range(1, len(idx)):
        sleeves = sleeves * (1.0 + R[t])
        total = sleeves.sum()
        if t % rebal_days == 0:
            sleeves = np.full(n_assets, total / n_assets)
        eq[t] = total
    return pd.Series(eq, index=idx, name="EW")


def combine_inv_vol(returns: dict[str, pd.Series], initial: float,
                     vol_lookback: int = 60, rebal_days: int = 21,
                     leverage: float = 1.0) -> pd.Series:
    """Inverse-vol weights, rebalanced periodically, optional constant leverage."""
    idx = next(iter(returns.values())).index
    R_df = pd.DataFrame(returns).reindex(idx).fillna(0.0)
    rolling_vol = R_df.rolling(vol_lookback, min_periods=vol_lookback).std() * np.sqrt(252)

    R = R_df.values
    n_assets = R.shape[1]
    eq = np.zeros(len(idx))
    w = np.full(n_assets, 1.0 / n_assets)
    sleeves = (initial * w)
    eq[0] = initial
    for t in range(1, len(idx)):
        sleeves = sleeves * (1.0 + R[t] * leverage)
        total = sleeves.sum()
        if t % rebal_days == 0 and not rolling_vol.iloc[t].isna().any():
            inv = 1.0 / rolling_vol.iloc[t].values
            w = inv / inv.sum()
            sleeves = total * w
        eq[t] = total
    return pd.Series(eq, index=idx, name="InvVol")


def main() -> None:
    print("[1/4] Loading data & building sleeves ...")
    raw = load_all(start="2017-01-01", end=END, force=False)
    master_full = build_master_frame(raw)
    mask = (master_full.index >= pd.Timestamp(START)) & (master_full.index <= pd.Timestamp(END))
    master_bt = master_full.loc[mask]
    print(f"   Window: {master_bt.index.min().date()} -> {master_bt.index.max().date()} ({len(master_bt)} bars)")
    initial = 100_000.0

    # Nasdaq sleeve = v2.1b
    cfg_v21 = StrategyV22Config(use_credit_signal=True, use_extreme_bull=False)
    sig_n = build_signals_v22(master_full, cfg_v21)
    tgt_n = target_weights_v22(sig_n, master_full, cfg_v21).loc[mask]
    res_n = run_backtest_v22(master_bt, tgt_n, BacktestV22Config(use_atr_stop=False))
    eq_n = res_n.equity * (initial / res_n.equity.iloc[0])
    print(f"   Nasdaq (v2.1b)  final=${eq_n.iloc[-1]:>11,.0f}  Sharpe={equity_curve_metrics(eq_n)['sharpe']:.2f}")

    # Gold sleeve
    cfg_g = SimpleSleeveConfig(label="Gold", asset_open_col="gld_open", asset_close_col="gld_close")
    eq_g = build_sleeve(master_full, mask, cfg_g)
    eq_g = eq_g * (initial / eq_g.iloc[0])
    print(f"   Gold sleeve     final=${eq_g.iloc[-1]:>11,.0f}  Sharpe={equity_curve_metrics(eq_g)['sharpe']:.2f}")

    # Bond sleeve
    cfg_b = SimpleSleeveConfig(label="LongBond", asset_open_col="tlt_open", asset_close_col="tlt_close")
    eq_b = build_sleeve(master_full, mask, cfg_b)
    eq_b = eq_b * (initial / eq_b.iloc[0])
    print(f"   Bond sleeve     final=${eq_b.iloc[-1]:>11,.0f}  Sharpe={equity_curve_metrics(eq_b)['sharpe']:.2f}")

    # Correlations (the diversification thesis stands or falls here)
    print("\n[2/4] Sleeve return correlation (key for diversification thesis) ...")
    ret_n = daily_returns(eq_n)
    ret_g = daily_returns(eq_g)
    ret_b = daily_returns(eq_b)
    corr_df = pd.DataFrame({"Nasdaq": ret_n, "Gold": ret_g, "Bond": ret_b}).corr()
    print(corr_df.to_string(float_format=lambda x: f"{x:+.3f}"))

    # Combinations
    print("\n[3/4] Combining sleeves ...")
    returns = {"Nasdaq": ret_n, "Gold": ret_g, "Bond": ret_b}
    eq_ew = combine_equal_weight(returns, initial)

    eq_iv = combine_inv_vol(returns, initial, leverage=1.0)

    # Compute the leverage needed for InvVol to match v2.1b's standalone vol
    iv_vol = daily_returns(eq_iv).std() * np.sqrt(252)
    target_vol = ret_n.std() * np.sqrt(252)
    lev = target_vol / iv_vol if iv_vol > 0 else 1.0
    print(f"   InvVol vol={iv_vol:.2%}, v2.1b vol={target_vol:.2%}, leverage applied={lev:.2f}x")
    eq_iv_lev = combine_inv_vol(returns, initial, leverage=lev)

    bh_spy = buy_and_hold(master_bt, "SPY", initial=initial)
    bh_qqq = buy_and_hold(master_bt, "QQQ", initial=initial)

    curves = {
        "Nasdaq sleeve (v2.1b)": eq_n,
        "Gold sleeve": eq_g,
        "Bond sleeve": eq_b,
        "EW combo (1/3, 1/3, 1/3)": eq_ew,
        "InvVol combo": eq_iv,
        f"InvVol+lev {lev:.2f}x": eq_iv_lev,
        "SPY B&H": bh_spy,
        "QQQ B&H": bh_qqq,
    }

    print("\n=== Full window ===")
    metrics_full = {k: equity_curve_metrics(v) for k, v in curves.items()}
    print(format_metrics_table(metrics_full).to_string())

    print(f"\n=== In-sample (<= {OOS_START}) ===")
    in_m = {k: equity_curve_metrics(v.loc[v.index <= OOS_START]) for k, v in curves.items()}
    print(format_metrics_table(in_m).to_string())

    print(f"\n=== Out-of-sample (> {OOS_START}) ===")
    oos_m = {k: equity_curve_metrics(v.loc[v.index > OOS_START]) for k, v in curves.items()}
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
    ann_df.to_csv(RESULTS / "annual_returns_v25.csv")

    # Plots
    print("\n[4/4] Saving plots ...")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    show = ["Nasdaq sleeve (v2.1b)", "Gold sleeve", "Bond sleeve",
            "EW combo (1/3, 1/3, 1/3)", f"InvVol+lev {lev:.2f}x", "QQQ B&H"]
    for n in show:
        ax1.plot(curves[n].index, curves[n].values, label=n, lw=1.3)
    ax1.set_yscale("log"); ax1.set_ylabel("Equity (log)")
    ax1.set_title("v2.5 multi-asset diversification")
    ax1.legend(loc="best"); ax1.grid(True, alpha=0.3)
    for n in show:
        c = curves[n]; dd = c / c.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.22, label=n)
    ax2.set_ylabel("Drawdown")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax2.grid(True, alpha=0.3); ax2.set_xlabel("Date")
    plt.tight_layout()
    p1 = RESULTS / "v25_equity_comparison.png"
    plt.savefig(p1, dpi=130); plt.close()

    # Correlation heatmap
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(corr_df.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr_df.columns))); ax.set_xticklabels(corr_df.columns)
    ax.set_yticks(range(len(corr_df.index))); ax.set_yticklabels(corr_df.index)
    for i in range(len(corr_df.index)):
        for j in range(len(corr_df.columns)):
            ax.text(j, i, f"{corr_df.iloc[i,j]:+.2f}", ha="center", va="center", color="black")
    ax.set_title("Daily-return correlation between sleeves")
    plt.colorbar(im, ax=ax)
    plt.tight_layout()
    p2 = RESULTS / "v25_correlation.png"
    plt.savefig(p2, dpi=130); plt.close()

    fig, ax = plt.subplots(figsize=(13, 5))
    ann_plot = ann_df[show]
    ann_plot.plot(kind="bar", ax=ax)
    ax.set_title("Annual returns")
    ax.set_ylabel("Return"); ax.axhline(0, color="black", lw=0.6)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    p3 = RESULTS / "v25_annual_returns.png"
    plt.savefig(p3, dpi=130); plt.close()

    eq_n.to_csv(RESULTS / "equity_curve_v25_nasdaq.csv")
    eq_g.to_csv(RESULTS / "equity_curve_v25_gold.csv")
    eq_b.to_csv(RESULTS / "equity_curve_v25_bond.csv")
    eq_ew.to_csv(RESULTS / "equity_curve_v25_ew.csv")
    eq_iv_lev.to_csv(RESULTS / "equity_curve_v25_invvol_lev.csv")
    format_metrics_table(metrics_full).to_csv(RESULTS / "metrics_summary_v25.csv")
    corr_df.to_csv(RESULTS / "v25_correlation.csv")

    def _safe(v):
        import datetime
        try:
            if pd.isna(v): return None
        except (TypeError, ValueError): pass
        if isinstance(v, (datetime.date, datetime.datetime)): return str(v)
        try: return float(v)
        except (TypeError, ValueError): return str(v)
    (REPORTS / "summary_v25.json").write_text(json.dumps({
        "window": {"start": str(master_bt.index.min().date()),
                   "end": str(master_bt.index.max().date())},
        "correlations": corr_df.to_dict(),
        "leverage": float(lev),
        "metrics_full": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in metrics_full.items()},
        "in_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in in_m.items()},
        "out_of_sample": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in oos_m.items()},
    }, indent=2, default=str))
    print(f"\nSaved: {p1}\n       {p2}\n       {p3}")


if __name__ == "__main__":
    main()
