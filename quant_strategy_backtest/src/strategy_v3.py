"""
Strategy v3 — single-asset (TQQQ) with regime gate + rebalancing bands.

Concept
-------
The composite regime signal (same six inputs as v2) acts as a binary
"gate": when it is below `gate_threshold`, the strategy is 100% in cash.
When open, the strategy holds TQQQ at a *base* weight and adjusts up/down
in discrete grid steps based on TQQQ's distance from its 20d SMA.

Grid mechanics
--------------
  deviation = TQQQ_close / TQQQ_SMA20 - 1
  bands = round(deviation / band_width)              # e.g. ±0.05 -> ±1 band
  bands = clip(bands, -max_bands, +max_bands)        # cap ±5
  adj = -bands * band_weight_step                    # above SMA -> trim
  target_TQQQ = clip(base + adj, 0, 1)

The minus sign is the "grid" insight: when TQQQ runs above its trend
we shave; when it lags we restore. This is "rebalancing bands", the
safety-tightened cousin of classical grid trading: discrete buckets,
hard ceiling/floor, and gated by regime.

Parameters
----------
All defaults are round, principled numbers:
  base = 60%  (Kelly-style fractional sizing for a 3x asset)
  band_width = 5%, step = 10pp, max ±5 bands -> target spans [10%, 110%]
                                                  clipped to [0%, 100%]
  gate_threshold = 0.50 (mid-scale on the composite)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy_v2 import StrategyV2Config, build_signals_v2


@dataclass
class StrategyV3Config:
    # Regime gate (reuses v2 composite, all v2 sub-signal defaults)
    gate_threshold: float = 0.50

    # Rebalancing band parameters
    base_when_open: float = 0.60
    sma_days: int = 20
    band_width_pct: float = 0.05
    band_weight_step: float = 0.10
    max_bands: int = 5

    # Floor/ceiling on the TQQQ target (post-grid)
    floor: float = 0.00
    ceiling: float = 1.00


def build_signals_v3(master: pd.DataFrame, cfg: StrategyV3Config | None = None) -> pd.DataFrame:
    """Use v2's composite signal as the regime gate."""
    return build_signals_v2(master, StrategyV2Config())


def target_weights_v3(
    signals: pd.DataFrame,
    master: pd.DataFrame,
    cfg: StrategyV3Config,
) -> pd.DataFrame:
    """Produce lagged target weights for (TQQQ, cash) only.

    All inputs used to set day-T weights are SHIFTED by 1 day so we
    only use information available at close[T-1].
    """
    comp_lag = signals["composite"].shift(1)
    gate_open = comp_lag >= cfg.gate_threshold

    sma = master["tqqq_close"].rolling(cfg.sma_days, min_periods=cfg.sma_days).mean()
    sma_lag = sma.shift(1)
    tqqq_lag = master["tqqq_close"].shift(1)
    deviation = tqqq_lag / sma_lag - 1.0

    bands = (deviation / cfg.band_width_pct).round()
    bands = bands.clip(lower=-cfg.max_bands, upper=cfg.max_bands)
    adjustment = -bands * cfg.band_weight_step

    target_tqqq = (cfg.base_when_open + adjustment).clip(lower=cfg.floor, upper=cfg.ceiling)
    target_tqqq = target_tqqq.where(gate_open, other=0.0)
    target_tqqq = target_tqqq.fillna(0.0)   # warmup -> cash

    target_cash = 1.0 - target_tqqq

    return pd.DataFrame({
        "w_tqqq": target_tqqq,
        "w_spy": 0.0,                       # not used (placeholder for v1 engine reuse)
        "w_cash": target_cash,
        "score": comp_lag,
        "deviation": deviation,
        "bands": bands,
        "gate_open": gate_open.astype(int),
    }, index=signals.index)
