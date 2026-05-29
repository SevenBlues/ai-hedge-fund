"""
v2.4 — tail-hedge overlay on v2.1b.

Builds the v2.1b equity curve, then overlays:
  * modelled rolling QQQ put hedges (BS priced from real QQQ/VXN/IRX),
    swept across annual budget x moneyness x skew assumption
  * a real VIXY ETF hedge as an independent cross-check

All hedged curves are compared to unhedged v2.1b on full-window and
on the two worst drawdown years (2018, 2022) specifically.
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
from hedge_overlay import (PutHedgeConfig, VixyHedgeConfig,
                            run_put_hedge, run_vixy_hedge)
from strategy_v22 import StrategyV22Config, build_signals_v22, target_weights_v22

PROJECT = Path(__file__).resolve().parent.parent
RESULTS = PROJECT / "results"
REPORTS = PROJECT / "reports"

START = "2018-05-24"
END = "2026-05-23"
OOS_START = "2023-01-01"


def year_return(eq: pd.Series, year: int) -> float:
    s = eq.loc[f"{year}-01-01":f"{year}-12-31"]
    if len(s) < 2:
        return float("nan")
    return s.iloc[-1] / s.iloc[0] - 1.0


def main() -> None:
    print("[1/4] Loading data & building v2.1b ...")
    raw = load_all(start="2017-01-01", end=END, force=False)
    master_full = build_master_frame(raw)
    mask = (master_full.index >= pd.Timestamp(START)) & (master_full.index <= pd.Timestamp(END))
    master_bt = master_full.loc[mask]

    cfg_s = StrategyV22Config(use_credit_signal=True, use_extreme_bull=False)
    sig = build_signals_v22(master_full, cfg_s)
    tgt = target_weights_v22(sig, master_full, cfg_s).loc[mask]
    res = run_backtest_v22(master_bt, tgt, BacktestV22Config(use_atr_stop=False))
    eq_base = res.equity
    strat_returns = eq_base.pct_change().fillna(0.0)
    print(f"   v2.1b final=${eq_base.iloc[-1]:,.0f}  Sharpe={equity_curve_metrics(eq_base)['sharpe']:.2f}")

    print("\n[2/4] Put-hedge sweep (BS priced from real QQQ/VXN/IRX) ...")
    sweep = []
    curves_hedge = {}
    for budget in [0.01, 0.02, 0.03]:
        for otm in [0.05, 0.10]:
            for skew in [1.0, 1.3]:
                cfg_h = PutHedgeConfig(annual_budget=budget, otm_pct=otm, skew_mult=skew,
                                       initial_capital=eq_base.iloc[0])
                hedged, diag = run_put_hedge(strat_returns, master_bt, cfg_h)
                m = equity_curve_metrics(hedged)
                total_prem = diag["premium_paid"].sum()
                total_payoff = diag["payoff_recv"].sum()
                row = {
                    "budget": budget, "otm": otm, "skew": skew,
                    "cagr": m["cagr"], "sharpe": m["sharpe"],
                    "max_dd": m["max_drawdown"], "calmar": m["calmar"],
                    "prem_total": total_prem, "payoff_total": total_payoff,
                    "net_cost": total_prem - total_payoff,
                    "dd2018": year_return(hedged, 2018),
                    "dd2022": year_return(hedged, 2022),
                }
                sweep.append(row)
                key = f"put b{int(budget*100)}/otm{int(otm*100)}/skew{skew}"
                curves_hedge[key] = hedged
    sweep_df = pd.DataFrame(sweep)
    print(sweep_df.to_string(index=False,
          formatters={"cagr": "{:.2%}".format, "sharpe": "{:.2f}".format,
                      "max_dd": "{:.2%}".format, "calmar": "{:.2f}".format,
                      "prem_total": "{:,.0f}".format, "payoff_total": "{:,.0f}".format,
                      "net_cost": "{:,.0f}".format,
                      "dd2018": "{:.2%}".format, "dd2022": "{:.2%}".format}))
    sweep_df.to_csv(RESULTS / "v24_put_sweep.csv", index=False)

    print("\n[3/4] Real VIXY hedge cross-check ...")
    vixy_curves = {}
    for w in [0.02, 0.03, 0.05]:
        cfg_v = VixyHedgeConfig(target_weight=w, initial_capital=eq_base.iloc[0])
        vixy_curves[f"vixy {int(w*100)}%"] = run_vixy_hedge(strat_returns, master_bt, cfg_v)
    vixy_metrics = {k: equity_curve_metrics(v) for k, v in vixy_curves.items()}
    print(format_metrics_table({"v2.1b (unhedged)": equity_curve_metrics(eq_base), **vixy_metrics}).to_string())

    # Representative hedged curve for headline comparison: 2% budget, 5% OTM, 1.3 skew
    rep_key = "put b2/otm5/skew1.3"
    rep = curves_hedge[rep_key]

    print("\n=== Headline: v2.1b vs representative put-hedge (2% budget, 5% OTM, 1.3x skew) ===")
    headline = {
        "v2.1b (unhedged)": equity_curve_metrics(eq_base),
        f"+ put hedge [{rep_key}]": equity_curve_metrics(rep),
        "+ VIXY 3%": equity_curve_metrics(vixy_curves["vixy 3%"]),
        "SPY B&H": equity_curve_metrics(buy_and_hold(master_bt, "SPY")),
    }
    print(format_metrics_table(headline).to_string())

    print("\n=== Worst-year protection (2018 partial, 2022 full) ===")
    for label, c in [("v2.1b", eq_base), (f"put[{rep_key}]", rep), ("VIXY 3%", vixy_curves["vixy 3%"])]:
        print(f"   {label:22s}  2018={year_return(c,2018):+.2%}  2022={year_return(c,2022):+.2%}")

    print("\n[4/4] Saving plots ...")
    # Equity comparison
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    show = {
        "v2.1b (unhedged)": eq_base,
        "+ put 2%/5%/1.3skew": rep,
        "+ put 3%/10%/1.3skew": curves_hedge["put b3/otm10/skew1.3"],
        "+ VIXY 3%": vixy_curves["vixy 3%"],
    }
    for name, c in show.items():
        ax1.plot(c.index, c.values, label=name, lw=1.3)
    ax1.set_yscale("log"); ax1.set_ylabel("Equity (log)")
    ax1.set_title("v2.4 tail-hedge overlay on v2.1b")
    ax1.legend(loc="best"); ax1.grid(True, alpha=0.3)
    for name, c in show.items():
        dd = c / c.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.25, label=name)
    ax2.set_ylabel("Drawdown")
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax2.grid(True, alpha=0.3); ax2.set_xlabel("Date")
    plt.tight_layout()
    p1 = RESULTS / "v24_equity_comparison.png"
    plt.savefig(p1, dpi=130); plt.close()

    # Sweep heat: sharpe & max_dd vs budget for each (otm,skew)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for (otm, skew), grp in sweep_df.groupby(["otm", "skew"]):
        lbl = f"otm{int(otm*100)}/skew{skew}"
        axes[0].plot(grp["budget"] * 100, grp["sharpe"], marker="o", label=lbl)
        axes[1].plot(grp["budget"] * 100, grp["max_dd"] * 100, marker="o", label=lbl)
    axes[0].axhline(equity_curve_metrics(eq_base)["sharpe"], color="black", ls="--", lw=0.8, label="unhedged")
    axes[0].set_xlabel("Annual budget (%)"); axes[0].set_ylabel("Sharpe"); axes[0].legend(fontsize=7); axes[0].grid(alpha=0.3)
    axes[1].axhline(equity_curve_metrics(eq_base)["max_drawdown"] * 100, color="black", ls="--", lw=0.8, label="unhedged")
    axes[1].set_xlabel("Annual budget (%)"); axes[1].set_ylabel("Max DD (%)"); axes[1].legend(fontsize=7); axes[1].grid(alpha=0.3)
    plt.tight_layout()
    p2 = RESULTS / "v24_sweep.png"
    plt.savefig(p2, dpi=130); plt.close()

    rep.to_csv(RESULTS / "equity_curve_v24_puthedge.csv")
    vixy_curves["vixy 3%"].to_csv(RESULTS / "equity_curve_v24_vixy.csv")

    def _safe(v):
        import datetime
        try:
            if pd.isna(v): return None
        except (TypeError, ValueError): pass
        if isinstance(v, (datetime.date, datetime.datetime)): return str(v)
        try: return float(v)
        except (TypeError, ValueError): return str(v)

    (REPORTS / "summary_v24.json").write_text(json.dumps({
        "window": {"start": str(master_bt.index.min().date()),
                   "end": str(master_bt.index.max().date())},
        "headline": {k: {kk: _safe(vv) for kk, vv in v.items()} for k, v in headline.items()},
        "put_sweep": sweep_df.to_dict(orient="records"),
    }, indent=2, default=str))
    print(f"\nSaved: {p1}\n       {p2}")


if __name__ == "__main__":
    main()
