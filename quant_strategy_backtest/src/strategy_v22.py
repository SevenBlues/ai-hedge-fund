"""
Strategy v2.2 — three further-fix candidates on top of v2.1b (credit signal).

Three independent toggles for clean ablation:

(C) DXY (US Dollar Index) sub-score
    USD strength tends to pressure US equities (multinational earnings
    + EM dollar funding stress). 60d % change of UUP (USD-bullish
    ETF, a clean DXY proxy on NYSE calendar), inverted via sigmoid:
    strong USD -> low score.

(D) min-aggregation risk veto
    composite_final = min(composite_mean, min_signal + 0.3)
    -- if the worst single signal is < 0.3, the composite is capped
    -- at min_signal + 0.3, forcing a defensive stance no matter how
    -- bullish the average is. Implements "any-one-veto" risk control.

(E) ATR-based dynamic stop (handled in backtest_v22.py)
    Replaces the fixed -12% hard stop with -k * ATR_pct(20).
    The strategy module just builds the ATR series; the engine
    consumes it.

Defaults: all three OFF, so v2.2 with no toggles = v2.1b.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy_v21 import StrategyV21Config, _sigmoid


@dataclass
class StrategyV22Config(StrategyV21Config):
    # (C) DXY / USD-strength signal
    use_dxy_signal: bool = False
    dxy_lookback_days: int = 60
    dxy_scale: float = 0.03                # 3% sigmoid scale

    # (D) min-aggregation veto
    use_min_veto: bool = False
    veto_buffer: float = 0.30              # cap = min_signal + buffer

    # (E) ATR-based dynamic stop (read by backtest engine)
    use_atr_stop: bool = False
    atr_k: float = 3.0                     # stop = -k * ATR_pct
    atr_lookback_days: int = 20


def build_signals_v22(master: pd.DataFrame, cfg: StrategyV22Config) -> pd.DataFrame:
    """v2.1 signals + optional DXY sub-score, with optional min-veto applied
    AFTER the mean composite is formed."""
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

    # (B) credit -- inherited from v2.1
    if cfg.use_credit_signal and "hyg_close" in master.columns and "ief_close" in master.columns:
        ratio = master["hyg_close"] / master["ief_close"]
        s["credit_chg_60d"] = ratio.pct_change(cfg.credit_lookback_days)
        s["score_credit"] = _sigmoid(s["credit_chg_60d"] / cfg.credit_scale)
        sub_cols = sub_cols + ["score_credit"]

    # (C) DXY -- new in v2.2
    if cfg.use_dxy_signal and "uup_close" in master.columns:
        s["uup_chg_60d"] = master["uup_close"].pct_change(cfg.dxy_lookback_days)
        # USD strength = negative for equities -> negate
        s["score_dxy"] = _sigmoid(-s["uup_chg_60d"] / cfg.dxy_scale)
        sub_cols = sub_cols + ["score_dxy"]

    # Mean composite of all active sub-scores
    s["composite_mean"] = s[sub_cols].mean(axis=1)

    # (D) min-veto -- cap composite by worst single signal
    if cfg.use_min_veto:
        s["min_signal"] = s[sub_cols].min(axis=1)
        s["composite"] = np.minimum(s["composite_mean"], s["min_signal"] + cfg.veto_buffer)
    else:
        s["composite"] = s["composite_mean"]

    # (E) ATR series (for engine consumption, not used here)
    s["tqqq_ret"] = master["tqqq_close"].pct_change()
    s["atr_pct"] = s["tqqq_ret"].abs().rolling(cfg.atr_lookback_days,
                                                 min_periods=cfg.atr_lookback_days).mean()

    warmup_cols = ["vix_ma", "irx_delta", "spy_sma", "qqq_mom"]
    if cfg.use_credit_signal: warmup_cols.append("credit_chg_60d")
    if cfg.use_dxy_signal: warmup_cols.append("uup_chg_60d")
    valid = s[warmup_cols].notna().all(axis=1)
    s.loc[~valid, "composite"] = np.nan
    return s


def target_weights_v22(
    signals: pd.DataFrame,
    master: pd.DataFrame,
    cfg: StrategyV22Config,
) -> pd.DataFrame:
    """Reuses v2.1's blend map; carries forward the ATR series."""
    from strategy_v21 import composite_to_asset_blend_v21

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
    # Carry ATR for the engine (lagged so engine never peeks)
    raw["atr_pct_lag"] = signals["atr_pct"].shift(1)
    return raw
