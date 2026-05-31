"""
Simple single-asset sleeve: trend + 12m momentum, asset vs cash.

Used in v2.5 to build orthogonal Gold and Long-Bond sleeves alongside
the existing v2.1b Nasdaq sleeve, then combine.

The same recipe is applied UNTUNED to every asset (200d SMA, 252d
momentum, sigmoid smoothing) -- this is the classic time-series-
momentum filter from Moskowitz/Pedersen 2012, with no per-asset
optimisation, so each sleeve carries minimal overfitting risk.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy_v2 import _sigmoid


@dataclass
class SimpleSleeveConfig:
    label: str
    asset_open_col: str
    asset_close_col: str
    sma_days: int = 200
    momentum_days: int = 252
    trend_scale: float = 0.05
    momentum_scale: float = 0.15


def build_simple_signals(master: pd.DataFrame, cfg: SimpleSleeveConfig) -> pd.DataFrame:
    """Two universal sub-scores (trend, momentum) -> mean composite in [0,1]."""
    s = pd.DataFrame(index=master.index)
    price = master[cfg.asset_close_col]
    sma = price.rolling(cfg.sma_days, min_periods=cfg.sma_days).mean()
    s["rel"] = price / sma - 1.0
    s["trend_score"] = _sigmoid(s["rel"] / cfg.trend_scale)
    s["mom"] = price.pct_change(cfg.momentum_days)
    s["mom_score"] = _sigmoid(s["mom"] / cfg.momentum_scale)
    s["composite"] = s[["trend_score", "mom_score"]].mean(axis=1)
    valid = sma.notna() & s["mom"].notna()
    s.loc[~valid, "composite"] = np.nan
    return s


def target_weights_simple(signals: pd.DataFrame, cfg: SimpleSleeveConfig) -> pd.DataFrame:
    """target_asset = lagged composite, cash = 1 - that."""
    comp = signals["composite"].shift(1)
    w_asset = comp.fillna(0.0).clip(lower=0.0, upper=1.0)
    return pd.DataFrame({"w_asset": w_asset, "w_cash": 1.0 - w_asset, "score": comp},
                         index=signals.index)
