"""
Bond-specific sleeve (v2.6 upgrade of the simple TLT sleeve).

The generic trend+momentum recipe failed badly on TLT in 2022 because
the rate-hike regime change happened faster than 200d/252d filters can
react. The fix is to add a rate-cycle signal as a third sub-score:
falling IRX (Fed easing) = bullish for long bonds.

  score_trend = sigmoid((TLT/SMA200 - 1) / 0.05)
  score_mom   = sigmoid(TLT_12m / 0.15)
  score_rate  = sigmoid(-IRX_60d_delta / 0.30)
  composite   = mean(3)

All three sub-scores use parameters IDENTICAL to those already in the
v2.1b strategy (60d IRX lookback, 0.30 sigmoid scale, same trend/mom
widths) -- no per-asset tuning. The rate signal is just the v2.1b
`score_rate_easing` re-purposed for an asset where rate easing is the
PRIMARY driver, not a secondary risk-on indicator.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy_v2 import _sigmoid


@dataclass
class BondSleeveConfig:
    label: str = "BondV2"
    asset_open_col: str = "tlt_open"
    asset_close_col: str = "tlt_close"
    sma_days: int = 200
    momentum_days: int = 252
    trend_scale: float = 0.05
    momentum_scale: float = 0.15
    irx_lookback_days: int = 60
    rate_scale: float = 0.30


def build_bond_signals(master: pd.DataFrame, cfg: BondSleeveConfig) -> pd.DataFrame:
    s = pd.DataFrame(index=master.index)
    price = master[cfg.asset_close_col]
    sma = price.rolling(cfg.sma_days, min_periods=cfg.sma_days).mean()
    s["trend_score"] = _sigmoid((price / sma - 1.0) / cfg.trend_scale)
    s["mom"] = price.pct_change(cfg.momentum_days)
    s["mom_score"] = _sigmoid(s["mom"] / cfg.momentum_scale)
    # Rate cycle: IRX falling (delta < 0) -> bullish for long bonds
    s["irx_delta"] = master["irx_close"] - master["irx_close"].shift(cfg.irx_lookback_days)
    s["rate_score"] = _sigmoid(-s["irx_delta"] / cfg.rate_scale)
    s["composite"] = s[["trend_score", "mom_score", "rate_score"]].mean(axis=1)
    valid = sma.notna() & s["mom"].notna() & s["irx_delta"].notna()
    s.loc[~valid, "composite"] = np.nan
    return s


def target_weights_bond(signals: pd.DataFrame, cfg: BondSleeveConfig) -> pd.DataFrame:
    comp = signals["composite"].shift(1)
    w_asset = comp.fillna(0.0).clip(lower=0.0, upper=1.0)
    return pd.DataFrame({"w_asset": w_asset, "w_cash": 1.0 - w_asset, "score": comp},
                         index=signals.index)
