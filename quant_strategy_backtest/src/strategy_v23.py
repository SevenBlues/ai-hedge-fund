"""
Strategy v2.3 — microstructure features derived from daily OHLC.

These are ORTHOGONAL to v2's macro/trend signals (VIX, rates, momentum,
credit, curve): they capture short-term supply/demand from the shape of
the daily bar, not the macro regime. All are 8-year backtestable from
free daily data (no true intraday feed needed).

Three toggles for clean ablation (computed on QQQ, the underlying —
less noisy than the leveraged TQQQ):

(F) CLOSE STRENGTH  (Close Location Value, smoothed)
    clv = ((C-L) - (H-C)) / (H-L)   in [-1, +1]
    +1 = closed on the high (buyers in control), -1 = closed on the low.
    10d mean -> sigmoid. Accumulation vs distribution.

(G) OVERNIGHT GAP MOMENTUM
    gap = open / prev_close - 1
    Cumulative 10d gap. Persistent positive overnight drift is a known
    institutional-accumulation footprint; persistent down-gaps = stress.

(H) RANGE-EXPANSION RISK
    range = (H-L)/C ; ratio = mean(range,5d) / mean(range,60d)
    Short-term range >> long-term range => volatility expanding => risk-off.
    Score is high when range is CONTRACTING.

Defaults: all OFF, so v2.3 with no toggles == v2.1b.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy_v22 import StrategyV22Config, build_signals_v22, _sigmoid


@dataclass
class StrategyV23Config(StrategyV22Config):
    # (F) Close strength
    use_clv_signal: bool = False
    clv_lookback_days: int = 10
    clv_scale: float = 0.30

    # (G) Overnight gap momentum
    use_gap_signal: bool = False
    gap_lookback_days: int = 10
    gap_scale: float = 0.02

    # (H) Range expansion
    use_range_signal: bool = False
    range_short_days: int = 5
    range_long_days: int = 60
    range_scale: float = 0.20


def _add_microstructure_scores(s: pd.DataFrame, master: pd.DataFrame,
                                cfg: StrategyV23Config) -> list[str]:
    """Append enabled microstructure sub-scores to s; return their column names."""
    cols: list[str] = []
    H, L, C, O = master["qqq_high"], master["qqq_low"], master["qqq_close"], master["qqq_open"]
    rng = (H - L).replace(0, np.nan)

    if cfg.use_clv_signal:
        clv = ((C - L) - (H - C)) / rng           # in [-1, 1]
        s["clv_10d"] = clv.rolling(cfg.clv_lookback_days,
                                    min_periods=cfg.clv_lookback_days).mean()
        s["score_clv"] = _sigmoid(s["clv_10d"] / cfg.clv_scale)
        cols.append("score_clv")

    if cfg.use_gap_signal:
        gap = O / C.shift(1) - 1.0
        s["gap_cum_10d"] = gap.rolling(cfg.gap_lookback_days,
                                        min_periods=cfg.gap_lookback_days).sum()
        s["score_gap"] = _sigmoid(s["gap_cum_10d"] / cfg.gap_scale)
        cols.append("score_gap")

    if cfg.use_range_signal:
        rel_range = rng / C
        short = rel_range.rolling(cfg.range_short_days, min_periods=cfg.range_short_days).mean()
        long = rel_range.rolling(cfg.range_long_days, min_periods=cfg.range_long_days).mean()
        s["range_ratio"] = short / long
        # contracting range (ratio < 1) -> high score (risk-on)
        s["score_range"] = _sigmoid((1.0 - s["range_ratio"]) / cfg.range_scale)
        cols.append("score_range")

    return cols


def build_signals_v23(master: pd.DataFrame, cfg: StrategyV23Config) -> pd.DataFrame:
    """v2.2 signals + optional microstructure sub-scores.

    Re-derives the v2.2 composite from scratch so the microstructure
    scores enter the SAME mean (and optional min-veto) as the macro
    signals, keeping a single unified composite.
    """
    # Start from v2.2 signal frame (includes credit/dxy/min-veto handling,
    # but its composite only averages the macro+credit+dxy scores).
    s = build_signals_v22(master, cfg)

    micro_cols = _add_microstructure_scores(s, master, cfg)
    if not micro_cols:
        return s   # nothing added; identical to v2.2

    # Rebuild the sub-score list and composite to include microstructure.
    base_cols = ["score_vix_level", "score_vix_trend", "score_rate_easing",
                 "score_trend", "score_momentum", "score_curve"]
    if cfg.use_credit_signal and "score_credit" in s.columns:
        base_cols.append("score_credit")
    if cfg.use_dxy_signal and "score_dxy" in s.columns:
        base_cols.append("score_dxy")
    all_cols = base_cols + micro_cols

    s["composite_mean"] = s[all_cols].mean(axis=1)
    if cfg.use_min_veto:
        s["min_signal"] = s[all_cols].min(axis=1)
        s["composite"] = np.minimum(s["composite_mean"], s["min_signal"] + cfg.veto_buffer)
    else:
        s["composite"] = s["composite_mean"]

    # Warmup: invalidate rows where any enabled feature is still NaN
    warmup = ["vix_ma", "irx_delta", "spy_sma", "qqq_mom"]
    if cfg.use_credit_signal: warmup.append("credit_chg_60d")
    if cfg.use_dxy_signal: warmup.append("uup_chg_60d")
    if cfg.use_clv_signal: warmup.append("clv_10d")
    if cfg.use_gap_signal: warmup.append("gap_cum_10d")
    if cfg.use_range_signal: warmup.append("range_ratio")
    valid = s[warmup].notna().all(axis=1)
    s.loc[~valid, "composite"] = np.nan
    return s


def target_weights_v23(signals: pd.DataFrame, master: pd.DataFrame,
                        cfg: StrategyV23Config) -> pd.DataFrame:
    """Identical mechanics to v2.2's target builder."""
    from strategy_v22 import target_weights_v22
    return target_weights_v22(signals, master, cfg)
