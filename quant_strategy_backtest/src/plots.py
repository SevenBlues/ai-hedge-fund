"""
Plot helpers for the backtest report.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RESULTS = Path(__file__).resolve().parent.parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


def plot_equity_curves(curves: dict[str, pd.Series], title: str, fname: str) -> Path:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1]})
    for name, eq in curves.items():
        ax1.plot(eq.index, eq.values, label=name, linewidth=1.4)
    ax1.set_yscale("log")
    ax1.set_title(title)
    ax1.set_ylabel("Equity (log)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="best")

    for name, eq in curves.items():
        dd = eq / eq.cummax() - 1.0
        ax2.fill_between(dd.index, dd.values, 0, alpha=0.3, label=name)
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel("Date")
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))

    out = RESULTS / fname
    plt.tight_layout()
    plt.savefig(out, dpi=130)
    plt.close()
    return out


def plot_annual_returns(curves: dict[str, pd.Series], fname: str) -> Path:
    rows = []
    for name, eq in curves.items():
        ann = eq.resample("YE").last().pct_change().dropna()
        for d, v in ann.items():
            rows.append({"year": d.year, "strategy": name, "return": v})
    df = pd.DataFrame(rows)
    pivot = df.pivot(index="year", columns="strategy", values="return")
    ax = pivot.plot(kind="bar", figsize=(12, 5))
    ax.set_title("Annual returns")
    ax.set_ylabel("Return")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.axhline(0, color="black", lw=0.6)
    ax.grid(True, alpha=0.3, axis="y")
    out = RESULTS / fname
    plt.tight_layout()
    plt.savefig(out, dpi=130)
    plt.close()
    return out


def plot_score_and_weights(signals: pd.DataFrame, weights: pd.DataFrame, master: pd.DataFrame, fname: str) -> Path:
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    ax0 = axes[0]
    ax0.plot(master.index, master["spy_close"] / master["spy_close"].iloc[0],
             color="black", label="SPY (rebased)", lw=1.0)
    ax0.plot(master.index, master["tqqq_close"] / master["tqqq_close"].iloc[0],
             color="C1", label="TQQQ (rebased)", lw=1.0, alpha=0.7)
    ax0.set_yscale("log")
    ax0.set_ylabel("Price (rebased)")
    ax0.legend(loc="best")
    ax0.grid(True, alpha=0.3)

    ax1 = axes[1]
    ax1.plot(signals.index, signals["composite"], color="C2", lw=0.8)
    ax1.set_ylabel("Composite score 0-6")
    ax1.set_ylim(-0.5, 6.5)
    ax1.grid(True, alpha=0.3)

    ax2 = axes[2]
    ax2.stackplot(weights.index, weights["w_tqqq"], weights["w_spy"], weights["w_cash"],
                  labels=["TQQQ", "SPY", "Cash"], colors=["C3", "C0", "lightgray"])
    ax2.set_ylim(0, 1)
    ax2.set_ylabel("Actual weights")
    ax2.legend(loc="upper left")

    out = RESULTS / fname
    plt.tight_layout()
    plt.savefig(out, dpi=130)
    plt.close()
    return out
