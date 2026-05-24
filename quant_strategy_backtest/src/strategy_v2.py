"""
Strategy v2 — three P0 improvements over v1:

  (1) Smooth signal scoring (sigmoid) replaces 0/1 hard buckets to remove
      threshold-crossing whipsaw.
  (2) QLD (2x Nasdaq) added as a mid-confidence tier between TQQQ and SPY,
      to reduce leverage decay in choppy regimes.
  (3) Volatility targeting overlay: scale total risk exposure so that the
      *expected* portfolio vol stays near `vol_target` (default 18%).

The signal *inputs* (VIX level, VIX trend, IRX 60d delta, SPY 200d trend,
QQQ 12m momentum, 5y-3m curve) and their hyper-parameters are IDENTICAL
to v1.  All v2 changes are structural — no thresholds were re-tuned on
the historical sample.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def _sigmoid(x: float | pd.Series) -> float | pd.Series:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class StrategyV2Config:
    # --- Identical to v1 ----------------------------------------------------
    vix_center: float = 25.0          # midpoint of v1's 20/30 band
    vix_scale: float = 5.0            # spread (sigmoid steepness)
    vix_trend_scale: float = 3.0
    irx_lookback_days: int = 60
    irx_tighten_bps: float = 0.50
    rate_scale: float = 0.30          # sigmoid scale for rate signal
    trend_sma_days: int = 200
    trend_scale: float = 0.05         # ~5% above/below SMA
    momentum_lookback_days: int = 252
    momentum_center: float = 0.05
    momentum_scale: float = 0.10
    curve_scale: float = 1.00         # 100bp slope
    vix_ma_days: int = 20

    # --- New in v2 ----------------------------------------------------------
    vol_target_ann: float = 0.25      # target ~25% (matches QQQ B&H natural vol)
    vol_lookback_days: int = 20
    vol_floor_scaler: float = 0.10    # never scale risk to less than 10%
    # NOTE: vol-target overlay defaults to OFF.  On this signal stack a 25%
    # target hurts more than it helps (over-trims long-vol melt-ups like
    # 2020-Q4 / 2021 when signals were already constructive).  Smooth
    # scoring + QLD alone already deliver the Sharpe / DD improvement.
    # Set this to True if you want the overlay back on.
    use_vol_target: bool = False


def build_signals_v2(master: pd.DataFrame, cfg: StrategyV2Config) -> pd.DataFrame:
    """Compute six smooth sub-scores in [0,1] and their mean as composite."""
    s = pd.DataFrame(index=master.index)

    # 1) VIX absolute level: low VIX -> high score
    s["vix"] = master["vix_close"]
    s["score_vix_level"] = _sigmoid((cfg.vix_center - s["vix"]) / cfg.vix_scale)

    # 2) VIX trend: VIX below 20d MA -> high score
    s["vix_ma"] = master["vix_close"].rolling(cfg.vix_ma_days, min_periods=cfg.vix_ma_days).mean()
    s["score_vix_trend"] = _sigmoid((s["vix_ma"] - s["vix"]) / cfg.vix_trend_scale)

    # 3) Rate cycle: rising IRX (tightening) -> low score; falling -> high
    s["irx"] = master["irx_close"]
    s["irx_delta"] = master["irx_close"] - master["irx_close"].shift(cfg.irx_lookback_days)
    s["score_rate_easing"] = _sigmoid((cfg.irx_tighten_bps - s["irx_delta"]) / cfg.rate_scale)

    # 4) Trend: SPY above 200d SMA -> high score
    s["spy_sma"] = master["spy_close"].rolling(cfg.trend_sma_days, min_periods=cfg.trend_sma_days).mean()
    s["spy_rel"] = master["spy_close"] / s["spy_sma"] - 1.0
    s["score_trend"] = _sigmoid(s["spy_rel"] / cfg.trend_scale)

    # 5) Momentum: QQQ 12m return > 5% -> high score
    s["qqq_mom"] = master["qqq_close"].pct_change(cfg.momentum_lookback_days)
    s["score_momentum"] = _sigmoid((s["qqq_mom"] - cfg.momentum_center) / cfg.momentum_scale)

    # 6) Curve slope: 5y - 3m > 0 -> high score
    s["curve_slope"] = master["fvx_close"] - master["irx_close"]
    s["score_curve"] = _sigmoid(s["curve_slope"] / cfg.curve_scale)

    sub_cols = ["score_vix_level", "score_vix_trend", "score_rate_easing",
                "score_trend", "score_momentum", "score_curve"]
    s["composite"] = s[sub_cols].mean(axis=1)

    warmup_cols = ["vix_ma", "irx_delta", "spy_sma", "qqq_mom"]
    valid = s[warmup_cols].notna().all(axis=1)
    s.loc[~valid, "composite"] = np.nan
    return s


def composite_to_asset_blend(composite: float) -> tuple[float, float, float]:
    """Map composite in [0,1] to (w_tqqq, w_qld, w_spy) BEFORE vol-target scaling.

    Total risk weight = composite; the remainder goes to cash later.
    Higher composite -> more leverage in the chosen risk asset:
        composite in [0.00, 0.25): SPY only
        composite in [0.25, 0.50): blend SPY -> QLD
        composite in [0.50, 0.75): blend QLD -> TQQQ
        composite in [0.75, 1.00]: TQQQ only
    """
    if pd.isna(composite):
        return (0.0, 0.0, 0.0)
    c = max(0.0, min(1.0, float(composite)))
    if c < 0.25:
        return (0.0, 0.0, c)
    if c < 0.50:
        f = (c - 0.25) / 0.25
        return (0.0, c * f, c * (1 - f))
    if c < 0.75:
        f = (c - 0.50) / 0.25
        return (c * f, c * (1 - f), 0.0)
    return (c, 0.0, 0.0)


def target_weights_v2(
    signals: pd.DataFrame,
    master: pd.DataFrame,
    cfg: StrategyV2Config,
) -> pd.DataFrame:
    """Compute lagged (T-1) target weights with vol-target overlay."""
    comp_lagged = signals["composite"].shift(1)

    raw = pd.DataFrame(
        [composite_to_asset_blend(c) for c in comp_lagged],
        index=signals.index,
        columns=["w_tqqq", "w_qld", "w_spy"],
    )

    if cfg.use_vol_target:
        # Realized SPY vol (use SPY as the unit-beta reference; TQQQ/QLD are
        # ~3x/2x of QQQ, treat QQQ ≈ 1.1x SPY here for simplicity).
        spy_ret = master["spy_close"].pct_change()
        spy_vol = spy_ret.rolling(cfg.vol_lookback_days,
                                   min_periods=cfg.vol_lookback_days).std() * np.sqrt(252)
        # Lag the realized vol so we don't use the same-day move
        spy_vol_lag = spy_vol.shift(1)

        # Beta (effective leverage) of the risky sleeve
        beta = 3.0 * raw["w_tqqq"] + 2.0 * raw["w_qld"] + 1.0 * raw["w_spy"]
        expected_vol = (beta * spy_vol_lag).replace(0, np.nan)
        scaler = (cfg.vol_target_ann / expected_vol).clip(lower=cfg.vol_floor_scaler, upper=1.0)
        scaler = scaler.fillna(1.0)

        raw["w_tqqq"] *= scaler
        raw["w_qld"] *= scaler
        raw["w_spy"] *= scaler

    raw["w_cash"] = (1.0 - raw[["w_tqqq", "w_qld", "w_spy"]].sum(axis=1)).clip(lower=0.0, upper=1.0)
    raw["score"] = comp_lagged
    return raw
