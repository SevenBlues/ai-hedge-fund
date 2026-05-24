"""
Strategy v2.1 — incremental improvements over v2.

Two targeted fixes for v2's documented weaknesses:

(A) EXTREME-BULL TIER EXPANSION
    v2's composite_to_asset_blend caps the risky weight at `composite`,
    so even at composite=0.85 the strategy keeps 15% cash that drags
    bull-market returns (the 2021 +0.2% pain). v2.1 expands the top
    tier so composite in [0.75, 0.85] is *linearly* mapped to a
    [0.75, 1.00] TQQQ weight, reaching 100% TQQQ at composite=0.85.

(B) CREDIT-SPREAD RISK SIGNAL
    Add a seventh sub-score from HYG/IEF (high-yield bond price /
    long Treasury price). Credit stress widens spreads — HYG falls
    while IEF rallies — so HYG/IEF turning down is an early risk-off
    signal that historically leads VIX by weeks. The score is a
    sigmoid on the 60d % change of this ratio.

Both knobs use round, principled values; the credit threshold is 0
(parity) and the extreme threshold is 0.85 (the natural ceiling of
the average-of-six composite when one signal is mildly bearish).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy_v2 import StrategyV2Config, _sigmoid


@dataclass
class StrategyV21Config(StrategyV2Config):
    # (A) Extreme-bull tier
    extreme_bull_threshold: float = 0.85    # composite at which we reach 100% TQQQ
    use_extreme_bull: bool = True

    # (B) Credit spread signal
    use_credit_signal: bool = True
    credit_lookback_days: int = 60
    credit_scale: float = 0.03              # 3% sigmoid scale for 60d HYG/IEF change


def build_signals_v21(master: pd.DataFrame, cfg: StrategyV21Config) -> pd.DataFrame:
    """Compute v2's six sub-scores plus an optional credit-spread score."""
    s = pd.DataFrame(index=master.index)

    s["vix"] = master["vix_close"]
    s["score_vix_level"] = _sigmoid((cfg.vix_center - s["vix"]) / cfg.vix_scale)

    s["vix_ma"] = master["vix_close"].rolling(cfg.vix_ma_days, min_periods=cfg.vix_ma_days).mean()
    s["score_vix_trend"] = _sigmoid((s["vix_ma"] - s["vix"]) / cfg.vix_trend_scale)

    s["irx"] = master["irx_close"]
    s["irx_delta"] = master["irx_close"] - master["irx_close"].shift(cfg.irx_lookback_days)
    s["score_rate_easing"] = _sigmoid((cfg.irx_tighten_bps - s["irx_delta"]) / cfg.rate_scale)

    s["spy_sma"] = master["spy_close"].rolling(cfg.trend_sma_days, min_periods=cfg.trend_sma_days).mean()
    s["spy_rel"] = master["spy_close"] / s["spy_sma"] - 1.0
    s["score_trend"] = _sigmoid(s["spy_rel"] / cfg.trend_scale)

    s["qqq_mom"] = master["qqq_close"].pct_change(cfg.momentum_lookback_days)
    s["score_momentum"] = _sigmoid((s["qqq_mom"] - cfg.momentum_center) / cfg.momentum_scale)

    s["curve_slope"] = master["fvx_close"] - master["irx_close"]
    s["score_curve"] = _sigmoid(s["curve_slope"] / cfg.curve_scale)

    sub_cols = ["score_vix_level", "score_vix_trend", "score_rate_easing",
                "score_trend", "score_momentum", "score_curve"]

    if cfg.use_credit_signal and "hyg_close" in master.columns and "ief_close" in master.columns:
        ratio = master["hyg_close"] / master["ief_close"]
        s["credit_ratio"] = ratio
        s["credit_chg_60d"] = ratio.pct_change(cfg.credit_lookback_days)
        s["score_credit"] = _sigmoid(s["credit_chg_60d"] / cfg.credit_scale)
        sub_cols = sub_cols + ["score_credit"]

    s["composite"] = s[sub_cols].mean(axis=1)

    warmup_cols = ["vix_ma", "irx_delta", "spy_sma", "qqq_mom"]
    if cfg.use_credit_signal:
        warmup_cols = warmup_cols + ["credit_chg_60d"]
    valid = s[warmup_cols].notna().all(axis=1)
    s.loc[~valid, "composite"] = np.nan
    return s


def composite_to_asset_blend_v21(composite: float, cfg: StrategyV21Config) -> tuple[float, float, float]:
    """v2 blend, but the top tier is expanded to reach 100% TQQQ at composite=ext.

    composite < 0.25         : SPY only           (w_spy = composite)
    0.25 <= composite < 0.50 : SPY -> QLD blend
    0.50 <= composite < 0.75 : QLD -> TQQQ blend
    0.75 <= composite < ext  : TQQQ, linearly grows from 0.75 to 1.00
    composite >= ext         : 100% TQQQ
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

    if not cfg.use_extreme_bull:
        return (c, 0.0, 0.0)
    ext = max(cfg.extreme_bull_threshold, 0.75 + 1e-6)
    if c >= ext:
        return (1.0, 0.0, 0.0)
    tqqq = 0.75 + (c - 0.75) * (1.0 - 0.75) / (ext - 0.75)
    return (min(tqqq, 1.0), 0.0, 0.0)


def target_weights_v21(
    signals: pd.DataFrame,
    master: pd.DataFrame,
    cfg: StrategyV21Config,
) -> pd.DataFrame:
    """Same vol-target overlay as v2 (default off); blend uses v2.1 mapping."""
    comp_lagged = signals["composite"].shift(1)

    raw = pd.DataFrame(
        [composite_to_asset_blend_v21(c, cfg) for c in comp_lagged],
        index=signals.index,
        columns=["w_tqqq", "w_qld", "w_spy"],
    )

    if cfg.use_vol_target:
        spy_ret = master["spy_close"].pct_change()
        spy_vol = spy_ret.rolling(cfg.vol_lookback_days,
                                   min_periods=cfg.vol_lookback_days).std() * np.sqrt(252)
        spy_vol_lag = spy_vol.shift(1)
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
