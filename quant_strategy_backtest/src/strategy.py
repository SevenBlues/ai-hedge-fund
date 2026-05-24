"""
Strategy signal construction. STRICT no look-ahead: every feature used to
decide position on date T is built from data available no later than T-1
close, and the trade then executes at T's open.

Composite score (0..6) controls the 6-level position allocation between
TQQQ (offensive 3x Nasdaq), SPY (defensive S&P 500), and cash.

Signal components:
  1. VIX absolute level   (low fear is bullish)
  2. VIX vs. its 20d MA   (falling vol regime)
  3. 13w T-bill 60d delta (rate cycle / Fed policy proxy)
  4. SPY trend filter     (price vs 200d SMA)
  5. QQQ 12m momentum     (252d total return)
  6. Yield curve slope    (5y - 13w; positive slope = risk-on regime)

Default thresholds are deliberately simple, round numbers (20, 30, 0, 0, 5%)
that have appeared widely in published research for ~15+ years, to limit
the chance of in-sample overfitting.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class StrategyConfig:
    vix_low: float = 20.0
    vix_high: float = 30.0
    irx_lookback_days: int = 60
    irx_tighten_bps: float = 0.50          # +50bps over 60d = tightening
    momentum_lookback_days: int = 252
    momentum_threshold: float = 0.05       # 5% trailing 12m return
    trend_sma_days: int = 200
    vix_ma_days: int = 20

    # 6-level weight mapping (TQQQ, SPY, cash) keyed by composite score
    weight_table: dict[int, tuple[float, float, float]] = None

    def __post_init__(self) -> None:
        if self.weight_table is None:
            self.weight_table = {
                6: (1.00, 0.00, 0.00),  # very bullish
                5: (0.80, 0.20, 0.00),  # bullish
                4: (0.50, 0.50, 0.00),  # constructive
                3: (0.20, 0.80, 0.00),  # neutral
                2: (0.00, 0.70, 0.30),  # cautious
                1: (0.00, 0.40, 0.60),  # bearish
                0: (0.00, 0.00, 1.00),  # very bearish (full cash)
            }


def build_signals(master: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """Compute every feature with point-in-time correctness.

    All rolling/shift operations use only data up to and including row T.
    Caller is responsible for shifting the resulting signal by one day
    before turning it into a trade decision.
    """
    s = pd.DataFrame(index=master.index)

    # --- Macro signals --------------------------------------------------
    s["vix"] = master["vix_close"]
    s["vix_ma"] = master["vix_close"].rolling(cfg.vix_ma_days, min_periods=cfg.vix_ma_days).mean()

    s["irx"] = master["irx_close"]
    s["irx_delta"] = master["irx_close"] - master["irx_close"].shift(cfg.irx_lookback_days)

    s["curve_slope"] = master["fvx_close"] - master["irx_close"]

    # --- Price-based signals (use Nasdaq-100 itself, NOT TQQQ, for the
    #     12m momentum / trend filter: TQQQ has only ~14y of history and
    #     its compounded leveraged path is noisier) -----------------------
    s["spy_sma"] = master["spy_close"].rolling(cfg.trend_sma_days, min_periods=cfg.trend_sma_days).mean()
    s["spy_above_sma"] = (master["spy_close"] > s["spy_sma"]).astype(int)

    s["qqq_mom"] = master["qqq_close"].pct_change(cfg.momentum_lookback_days)

    # --- Sub-scores (each 0 or 1, vix_level is 0/1/2) -------------------
    vix_score = pd.Series(0, index=s.index, dtype=int)
    vix_score = vix_score.where(s["vix"] >= cfg.vix_high, other=2)             # vix < high
    vix_score = vix_score.where(s["vix"] < cfg.vix_high, other=0)              # default 0 if >= high
    # second pass: between low and high => 1
    mid_mask = (s["vix"] >= cfg.vix_low) & (s["vix"] < cfg.vix_high)
    vix_score[mid_mask] = 1
    high_mask = s["vix"] >= cfg.vix_high
    vix_score[high_mask] = 0
    low_mask = s["vix"] < cfg.vix_low
    vix_score[low_mask] = 2
    s["score_vix_level"] = vix_score                                           # 0..2

    s["score_vix_trend"] = (s["vix"] < s["vix_ma"]).astype(int)                # 0..1
    s["score_rate_easing"] = (s["irx_delta"] < cfg.irx_tighten_bps).astype(int)
    s["score_trend"] = s["spy_above_sma"]                                      # 0..1
    s["score_momentum"] = (s["qqq_mom"] > cfg.momentum_threshold).astype(int)
    s["score_curve"] = (s["curve_slope"] > 0).astype(int)                      # 0..1

    s["composite"] = (
        s["score_vix_level"]
        + s["score_vix_trend"]
        + s["score_rate_easing"]
        + s["score_trend"]
        + s["score_momentum"]
        + s["score_curve"]
    ).clip(lower=0, upper=6)

    # Cleanly nullify rows where any input was still warming up
    warmup_cols = ["vix_ma", "irx_delta", "spy_sma", "qqq_mom"]
    valid = s[warmup_cols].notna().all(axis=1)
    s.loc[~valid, "composite"] = np.nan

    return s


def score_to_weights(score: float, cfg: StrategyConfig) -> tuple[float, float, float]:
    if pd.isna(score):
        return (0.0, 0.0, 1.0)  # full cash during warmup
    return cfg.weight_table[int(score)]


def target_weights_frame(signals: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    """Return target (w_tqqq, w_spy, w_cash) for each date.

    The score on day T-1 is used to set the target weight that will be
    *traded into* at the open of day T.  We therefore SHIFT the score by
    one day before the lookup.
    """
    score_lagged = signals["composite"].shift(1)
    weights = pd.DataFrame(
        [score_to_weights(s, cfg) for s in score_lagged],
        index=signals.index,
        columns=["w_tqqq", "w_spy", "w_cash"],
    )
    weights["score"] = score_lagged
    return weights
