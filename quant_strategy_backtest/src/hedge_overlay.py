"""
Tail-hedge overlays for v2.1b (v2.4 experiment).

Two independent hedge implementations, both running ON TOP of the
v2.1b daily return stream:

(1) MODELLED QQQ PUT OVERLAY  -- run_put_hedge()
    Buys rolling ~1-month OTM QQQ puts. Option prices come from
    Black-Scholes using 100% REAL market inputs on each date:
        spot   = real QQQ close
        IV     = real VXN (Nasdaq 30d implied vol) x skew markup
        r      = real 13w T-bill (^IRX)
        T      = real calendar time to expiry
    No price path is simulated; BS is only the standard transform of
    observed inputs into a fair premium. An OTM skew markup (default
    1.3x) deliberately makes the hedge MORE expensive than flat-VXN
    pricing, biasing the test AGAINST the hedge.

(2) REAL VIXY OVERLAY  -- run_vixy_hedge()
    Allocates a small constant weight to VIXY (VIX short-term futures
    ETF). 100% real traded prices, no option modelling at all. Serves
    as a sanity cross-check on the modelled-put conclusion.

Both return a daily total-equity Series so drawdown/Sharpe are directly
comparable to the unhedged v2.1b curve.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm


# --------------------------------------------------------------------------
# Black-Scholes put (real inputs only)
# --------------------------------------------------------------------------
def bs_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0:
        return max(K - S, 0.0)
    sqrtT = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


@dataclass
class PutHedgeConfig:
    annual_budget: float = 0.02      # target annual premium spend (fraction of equity)
    otm_pct: float = 0.05            # puts struck this far below spot
    tenor_days: int = 21             # ~1 month
    rebuy_days: int = 21             # buy a fresh tranche every month
    skew_mult: float = 1.3           # OTM IV markup over ATM VXN (conservative)
    vix_floor: float = 8.0           # floor IV input
    initial_capital: float = 100_000.0


@dataclass
class VixyHedgeConfig:
    target_weight: float = 0.03      # constant fraction parked in VIXY
    rebalance_days: int = 21         # rebalance monthly back to target
    initial_capital: float = 100_000.0


def run_put_hedge(strat_returns: pd.Series, master_bt: pd.DataFrame,
                  cfg: PutHedgeConfig) -> tuple[pd.Series, pd.DataFrame]:
    """Overlay a rolling QQQ-put hedge on the v2.1b daily-return stream."""
    idx = strat_returns.index
    n = len(idx)
    qqq = master_bt["qqq_close"].reindex(idx).values
    vxn = master_bt["vxn_close"].reindex(idx).values
    irx = master_bt["irx_close"].reindex(idx).values
    r_strat = strat_returns.values

    strat_eq = np.zeros(n)
    put_mtm = np.zeros(n)
    total = np.zeros(n)
    premium_paid = np.zeros(n)
    payoff_recv = np.zeros(n)

    strat_eq[0] = cfg.initial_capital
    total[0] = cfg.initial_capital
    # ~ (252/rebuy_days) tranches per year
    tranches_per_year = 252.0 / cfg.rebuy_days
    budget_per_tranche = cfg.annual_budget / tranches_per_year

    open_pos: list[dict] = []   # each: strike, expiry_i, contracts

    for t in range(1, n):
        strat_eq[t] = strat_eq[t - 1] * (1.0 + r_strat[t])

        # 1) settle expiries first (avoid double counting vs MTM)
        for pos in open_pos[:]:
            if t >= pos["expiry_i"]:
                payoff = pos["contracts"] * max(pos["strike"] - qqq[t], 0.0)
                strat_eq[t] += payoff
                payoff_recv[t] += payoff
                open_pos.remove(pos)

        # 2) buy a fresh tranche on schedule
        if t % cfg.rebuy_days == 0 and not np.isnan(qqq[t]) and not np.isnan(vxn[t]):
            base_equity = strat_eq[t] + sum(
                p["contracts"] * bs_put(qqq[t], p["strike"],
                                        max(p["expiry_i"] - t, 0) / 252.0,
                                        max(irx[t], 0) / 100.0,
                                        max(vxn[t], cfg.vix_floor) / 100.0 * cfg.skew_mult)
                for p in open_pos
            )
            premium = budget_per_tranche * base_equity
            K = qqq[t] * (1.0 - cfg.otm_pct)
            sigma = max(vxn[t], cfg.vix_floor) / 100.0 * cfg.skew_mult
            T = cfg.tenor_days / 252.0
            r = max(irx[t], 0) / 100.0
            price = bs_put(qqq[t], K, T, r, sigma)
            if price > 1e-8:
                contracts = premium / price
                strat_eq[t] -= premium
                premium_paid[t] += premium
                open_pos.append({"strike": K, "expiry_i": t + cfg.tenor_days,
                                 "contracts": contracts})

        # 3) mark open positions to model
        mtm = 0.0
        for pos in open_pos:
            T = max(pos["expiry_i"] - t, 0) / 252.0
            sigma = max(vxn[t], cfg.vix_floor) / 100.0 * cfg.skew_mult
            r = max(irx[t], 0) / 100.0
            mtm += pos["contracts"] * bs_put(qqq[t], pos["strike"], T, r, sigma)
        put_mtm[t] = mtm
        total[t] = strat_eq[t] + put_mtm[t]

    diag = pd.DataFrame({
        "strat_eq": strat_eq, "put_mtm": put_mtm, "total": total,
        "premium_paid": premium_paid, "payoff_recv": payoff_recv,
    }, index=idx)
    return pd.Series(total, index=idx, name="hedged"), diag


def run_vixy_hedge(strat_returns: pd.Series, master_bt: pd.DataFrame,
                   cfg: VixyHedgeConfig) -> pd.Series:
    """Park a constant fraction in real VIXY, rebalanced monthly."""
    idx = strat_returns.index
    n = len(idx)
    vixy = master_bt["vixy_close"].reindex(idx).ffill().values
    r_strat = strat_returns.values

    strat_sleeve = np.zeros(n)
    vixy_sleeve = np.zeros(n)
    total = np.zeros(n)

    strat_sleeve[0] = cfg.initial_capital * (1 - cfg.target_weight)
    vixy_sleeve[0] = cfg.initial_capital * cfg.target_weight
    total[0] = cfg.initial_capital

    for t in range(1, n):
        strat_sleeve[t] = strat_sleeve[t - 1] * (1.0 + r_strat[t])
        vixy_ret = (vixy[t] / vixy[t - 1] - 1.0) if vixy[t - 1] > 0 else 0.0
        vixy_sleeve[t] = vixy_sleeve[t - 1] * (1.0 + vixy_ret)
        total[t] = strat_sleeve[t] + vixy_sleeve[t]

        if t % cfg.rebalance_days == 0 and total[t] > 0:
            vixy_sleeve[t] = total[t] * cfg.target_weight
            strat_sleeve[t] = total[t] * (1 - cfg.target_weight)

    return pd.Series(total, index=idx, name="vixy_hedged")
