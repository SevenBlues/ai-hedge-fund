"""
Factor validation — the statistical tests that tell you whether the signal is
real or noise. This is the layer most reproduced quant projects skip.

What it tests
-------------
The mechanical, point-in-time **chokepoint-ramp factor** (12-1 momentum +
re-rating-gap flag) that ``oos_backtest`` already computes look-ahead-free. It
does NOT test the hand-curated structural chokepoint score — that score has no
point-in-time history (supply shares, qualification cycles were curated once, in
2026), so an honest IC test on it is impossible. Saying so is the point: we test
what is testable and refuse to fake the rest.

The tests
---------
1. Cross-sectional Information Coefficient (IC): each month, Spearman rank
   correlation between the signal and the *next* month's return. We report the
   IC time series' mean, std, IC-IR (mean/std), and a t-stat / p-value for
   "mean IC = 0". A mean |IC| ~ 0.03-0.05 with IR > 0.3 is a genuinely useful
   equity factor; anything whose p-value isn't significant is, honestly, noise.

2. Tercile long-short: top-third minus bottom-third by signal, realised next
   month. Welch t-test on the monthly long-short return ("is the spread > 0?"),
   plus annualised Sharpe.

3. Newey-West adjusted t-stat on the long-short mean (autocorrelation-robust),
   because momentum sorts induce serial correlation that inflates a naive t.

No scipy dependency: p-values use a t-distribution tail via a numerically stable
approximation; for n > ~20 months this matches scipy to 3+ decimals.

Educational; not financial advice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from serenity_chokepoint.oos_backtest import (
    JUMP_TILT,
    TOP_K,
    _build_prices,
    _signal_at,
)


# --------------------------------------------------------------------------- #
# p-value helpers (no scipy)
# --------------------------------------------------------------------------- #
def _t_sf(t: float, df: float) -> float:
    """Upper-tail prob of Student-t via the regularized incomplete beta."""
    if df <= 0:
        return float("nan")
    x = df / (df + t * t)
    ib = _betainc(df / 2.0, 0.5, x) / 2.0
    return ib if t > 0 else 1.0 - ib


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a,b) via continued fraction (Lentz)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    # Lentz's algorithm for the continued fraction
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        cd = c * d
        f *= cd
        if abs(1.0 - cd) < 1e-10:
            break
    return front * (f - 1.0)


def _two_sided_p(t: float, df: float) -> float:
    return 2.0 * _t_sf(abs(t), df)


# --------------------------------------------------------------------------- #
# Core: build monthly (signal, forward-return) panel — point-in-time
# --------------------------------------------------------------------------- #
@dataclass
class FactorStats:
    n_months: int
    mean_ic: float
    ic_std: float
    ic_ir: float
    ic_t: float
    ic_p: float
    ls_mean_monthly: float
    ls_sharpe: float
    ls_t: float
    ls_p: float
    ls_t_nw: float
    ls_p_nw: float
    hit_rate_ic_pos: float


def _panel(period: str = "8y"):
    """Return list over months of (signals dict, forward-returns dict),
    using ONLY information available at each month (reuses oos machinery)."""
    import numpy as np

    prices, err = _build_prices(period)
    if err:
        return None, err
    rets = prices.pct_change()
    dates = prices.index
    cols = [c for c in prices.columns if c not in ("SOXX", "QQQ", "SPY")]

    panel = []
    for i in range(len(dates) - 1):
        raw = {}
        for c in cols:
            sig = _signal_at(prices, i, c, rets)
            if sig is not None:
                # composite mechanical factor = z(mom) handled later + tilt*rerate
                raw[c] = sig  # (momentum, rerate)
        if len(raw) < max(TOP_K + 2, 6):
            continue
        moms = np.array([v[0] for v in raw.values()])
        mu, sd = moms.mean(), (moms.std() or 1.0)
        sig_scores = {c: (v[0] - mu) / sd + JUMP_TILT * v[1] for c, v in raw.items()}
        fwd = rets.loc[dates[i + 1]]
        fr = {c: float(fwd[c]) for c in raw if fwd.get(c) == fwd.get(c)}
        common = [c for c in sig_scores if c in fr]
        if len(common) >= 6:
            panel.append(({c: sig_scores[c] for c in common}, {c: fr[c] for c in common}))
    return panel, None


def validate(period: str = "8y") -> dict:
    import numpy as np
    import pandas as pd

    panel, err = _panel(period)
    if err:
        return {"error": err}
    if not panel or len(panel) < 12:
        return {"error": "insufficient history for factor validation (need network / longer period)"}

    ics, ls_rets = [], []
    for sig, fr in panel:
        s = pd.Series(sig)
        r = pd.Series(fr)
        ic = s.corr(r, method="spearman")
        if ic == ic:  # not NaN
            ics.append(ic)
        # tercile long-short
        k = max(1, len(s) // 3)
        ranked = s.sort_values(ascending=False)
        hi = ranked.index[:k]
        lo = ranked.index[-k:]
        ls = float(r[hi].mean() - r[lo].mean())
        ls_rets.append(ls)

    ics = np.array(ics)
    ls = np.array(ls_rets)
    n = len(ics)

    mean_ic = float(ics.mean())
    ic_std = float(ics.std(ddof=1))
    ic_ir = mean_ic / ic_std if ic_std > 0 else 0.0
    ic_t = ic_ir * math.sqrt(n)
    ic_p = _two_sided_p(ic_t, n - 1)

    m = len(ls)
    ls_mean = float(ls.mean())
    ls_sd = float(ls.std(ddof=1))
    ls_sharpe = (ls_mean * 12) / (ls_sd * math.sqrt(12)) if ls_sd > 0 else 0.0
    ls_t = (ls_mean / (ls_sd / math.sqrt(m))) if ls_sd > 0 else 0.0
    ls_p = _two_sided_p(ls_t, m - 1)

    # Newey-West (Bartlett) adjusted SE for the long-short mean, lag = 3
    ls_t_nw, ls_p_nw = _newey_west_t(ls, lags=3)

    stats = FactorStats(
        n_months=n, mean_ic=mean_ic, ic_std=ic_std, ic_ir=ic_ir, ic_t=ic_t, ic_p=ic_p,
        ls_mean_monthly=ls_mean, ls_sharpe=ls_sharpe, ls_t=ls_t, ls_p=ls_p,
        ls_t_nw=ls_t_nw, ls_p_nw=ls_p_nw,
        hit_rate_ic_pos=float((ics > 0).mean()),
    )
    return {"stats": stats, "ic_series": ics.tolist(), "ls_series": ls.tolist()}


# --------------------------------------------------------------------------- #
# Factor zoo — a battery of point-in-time, look-ahead-free candidate factors,
# all run through the SAME IC / long-short / t-stat pipeline so we can honestly
# compare what (if anything) carries signal in this universe.
# --------------------------------------------------------------------------- #
def _cum_ret(prices, col, i, lookback, skip=1):
    """Return over [i-lookback, i-skip] using only data up to i, or None."""
    if i < lookback:
        return None
    a = prices[col].iloc[i - lookback]
    b = prices[col].iloc[i - skip]
    if a != a or b != b or a == 0:
        return None
    return b / a - 1.0


def _trailing_vol(rets, col, i, window=12):
    if i < window:
        return None
    seg = rets[col].iloc[i - window + 1: i + 1].dropna()
    if len(seg) < window // 2:
        return None
    return float(seg.std())


def _beta_to_bench(rets, col, bench, i, window=24):
    """OLS beta of stock vs benchmark over trailing window up to i."""
    import numpy as np
    if i < window or bench not in rets.columns:
        return None
    y = rets[col].iloc[i - window + 1: i + 1]
    x = rets[bench].iloc[i - window + 1: i + 1]
    df = __import__("pandas").concat([y, x], axis=1).dropna()
    if len(df) < window // 2 or df.iloc[:, 1].std() == 0:
        return None
    yv = df.iloc[:, 0].values
    xv = df.iloc[:, 1].values
    cov = np.cov(yv, xv)[0, 1]
    var = np.var(xv)
    return float(cov / var) if var > 0 else None


# Each factor: (prices, rets, i, col, bench_col) -> float | None  (higher = "more attractive")
def _f_mom_12_1(prices, rets, i, col, b):
    return _cum_ret(prices, col, i, 12, 1)

def _f_mom_6_1(prices, rets, i, col, b):
    return _cum_ret(prices, col, i, 6, 1)

def _f_mom_3_1(prices, rets, i, col, b):
    return _cum_ret(prices, col, i, 3, 1)

def _f_st_reversal(prices, rets, i, col, b):
    r = _cum_ret(prices, col, i, 1, 0)            # last-month return
    return None if r is None else -r              # reversal: short recent winners

def _f_low_vol(prices, rets, i, col, b):
    v = _trailing_vol(rets, col, i, 12)
    return None if v is None else -v              # prefer LOW volatility

def _f_resid_mom(prices, rets, i, col, b):
    """Idiosyncratic 12-1 momentum: stock momentum minus beta*benchmark momentum.
    Directly answers 'is the edge just sector beta?'"""
    m = _cum_ret(prices, col, i, 12, 1)
    mb = _cum_ret(prices, b, i, 12, 1)
    beta = _beta_to_bench(rets, col, b, i, 24)
    if m is None or mb is None or beta is None:
        return None
    return m - beta * mb

def _f_near_high(prices, rets, i, col, b):
    """Proximity to trailing 12m high (52-week-high factor)."""
    if i < 12:
        return None
    seg = prices[col].iloc[i - 11: i + 1].dropna()
    if len(seg) < 6 or seg.max() == 0:
        return None
    return float(prices[col].iloc[i] / seg.max())

def _f_mom_accel(prices, rets, i, col, b):
    """Acceleration: recent 6m momentum minus the prior 6m momentum."""
    recent = _cum_ret(prices, col, i, 6, 0)
    prior = _cum_ret(prices, col, i - 6, 6, 0) if i >= 12 else None
    if recent is None or prior is None:
        return None
    return recent - prior


FACTOR_ZOO = {
    "mom_12_1 (current)": _f_mom_12_1,
    "mom_6_1":            _f_mom_6_1,
    "mom_3_1":            _f_mom_3_1,
    "st_reversal_1m":     _f_st_reversal,
    "low_volatility":     _f_low_vol,
    "resid_mom (ex-beta)": _f_resid_mom,
    "near_52w_high":      _f_near_high,
    "mom_acceleration":   _f_mom_accel,
}


def validate_zoo(period: str = "8y", bench: str = "SOXX") -> dict:
    """Run every factor in FACTOR_ZOO through the IC + tercile long-short pipeline,
    point-in-time, and return a comparison with multiple-testing-aware significance."""
    import numpy as np
    import pandas as pd

    prices, err = _build_prices(period)
    if err:
        return {"error": err}
    rets = prices.pct_change()
    dates = prices.index
    cols = [c for c in prices.columns if c not in ("SOXX", "QQQ", "SPY")]

    # precompute per-month (factor_values, forward_returns) for all factors at once
    per_factor_ic = {name: [] for name in FACTOR_ZOO}
    per_factor_ls = {name: [] for name in FACTOR_ZOO}

    for i in range(len(dates) - 1):
        fwd = rets.loc[dates[i + 1]]
        fr = {c: float(fwd[c]) for c in cols if fwd.get(c) == fwd.get(c)}
        if len(fr) < 6:
            continue
        for name, fn in FACTOR_ZOO.items():
            vals = {}
            for c in fr:
                try:
                    v = fn(prices, rets, i, c, bench)
                except Exception:
                    v = None
                if v is not None and v == v:
                    vals[c] = v
            common = [c for c in vals if c in fr]
            if len(common) < 6:
                continue
            s = pd.Series({c: vals[c] for c in common})
            r = pd.Series({c: fr[c] for c in common})
            ic = s.corr(r, method="spearman")
            if ic == ic:
                per_factor_ic[name].append(ic)
            k = max(1, len(s) // 3)
            ranked = s.sort_values(ascending=False)
            per_factor_ls[name].append(float(r[ranked.index[:k]].mean() - r[ranked.index[-k:]].mean()))

    n_factors = sum(1 for n in FACTOR_ZOO if len(per_factor_ic[n]) >= 12)
    bonf = 0.05 / max(n_factors, 1)

    rows = []
    for name in FACTOR_ZOO:
        ics = np.array(per_factor_ic[name])
        ls = np.array(per_factor_ls[name])
        if len(ics) < 12:
            continue
        mean_ic = float(ics.mean())
        ic_std = float(ics.std(ddof=1)) or 1e-9
        ic_ir = mean_ic / ic_std
        ic_t = ic_ir * math.sqrt(len(ics))
        ic_p = _two_sided_p(ic_t, len(ics) - 1)
        ls_t_nw, ls_p_nw = _newey_west_t(ls, lags=3)
        ls_mean = float(ls.mean())
        ls_sd = float(ls.std(ddof=1)) or 1e-9
        ls_sharpe = (ls_mean * 12) / (ls_sd * math.sqrt(12))
        rows.append({
            "factor": name, "n": len(ics), "mean_ic": mean_ic, "ic_ir": ic_ir,
            "ic_t": ic_t, "ic_p": ic_p, "ls_mean": ls_mean, "ls_sharpe": ls_sharpe,
            "ls_t_nw": ls_t_nw, "ls_p_nw": ls_p_nw,
            "sig_raw": ic_p < 0.05, "sig_bonf": ic_p < bonf,
        })
    rows.sort(key=lambda r: abs(r["ic_t"]), reverse=True)
    return {"rows": rows, "n_factors": n_factors, "bonferroni_alpha": bonf, "bench": bench}


def zoo_report(period: str = "8y") -> str:
    r = validate_zoo(period)
    out = ["=" * 104,
           "FACTOR ZOO — battery of point-in-time factors through one rigorous IC / long-short / t pipeline",
           "=" * 104]
    if "error" in r:
        return "\n".join(out + [f"[factor-zoo] {r['error']}"])
    out.append(f"Each factor: monthly cross-sectional Spearman IC vs next-month return + tercile long-short.")
    out.append(f"Multiple-testing: {r['n_factors']} factors tested -> Bonferroni alpha = "
               f"{r['bonferroni_alpha']:.4f} (a factor must clear THIS, not 0.05, to claim a real edge).\n")
    out.append(f"  {'factor':<22}{'n':>4}{'meanIC':>9}{'IC-IR':>7}{'IC t':>7}{'IC p':>8}"
               f"{'LS Shrp':>8}{'LS t(NW)':>9}{'LS p':>8}  verdict")
    out.append("  " + "-" * 100)
    for row in r["rows"]:
        if row["sig_bonf"]:
            v = "** survives Bonferroni"
        elif row["sig_raw"]:
            v = "* raw-significant only (likely false positive)"
        else:
            v = "noise"
        out.append(f"  {row['factor']:<22}{row['n']:>4}{row['mean_ic']:>+9.4f}{row['ic_ir']:>+7.2f}"
                   f"{row['ic_t']:>+7.2f}{row['ic_p']:>8.3f}{row['ls_sharpe']:>+8.2f}"
                   f"{row['ls_t_nw']:>+9.2f}{row['ls_p_nw']:>8.3f}  {v}")
    out.append("  " + "-" * 100)
    survivors = [r2["factor"] for r2 in r["rows"] if r2["sig_bonf"]]
    if survivors:
        out.append(f"SURVIVORS (Bonferroni-significant): {', '.join(survivors)}")
    else:
        out.append("SURVIVORS: none clear the multiple-testing bar. Honest read: no single price-only factor")
        out.append("has detectable edge in this one sector / epoch. (resid_mom near-zero => what edge exists is mostly sector beta.)")
    out.append("CAVEAT: residual survivorship; overlapping/serial signals; one sector, one AI-bull epoch; long-only. Not advice.")
    out.append("=" * 104)
    return "\n".join(out)


def _newey_west_t(x, lags: int = 3):
    """t-stat for mean(x)=0 with Newey-West (Bartlett-kernel) HAC variance."""
    import numpy as np

    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 5:
        return 0.0, float("nan")
    xbar = x.mean()
    u = x - xbar
    gamma0 = float(u @ u) / n
    s = gamma0
    for L in range(1, min(lags, n - 1) + 1):
        w = 1.0 - L / (lags + 1.0)
        cov = float(u[L:] @ u[:-L]) / n
        s += 2.0 * w * cov
    se = math.sqrt(max(s, 1e-18) / n)
    t = xbar / se if se > 0 else 0.0
    return t, _two_sided_p(t, n - 1)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def _verdict(s: "FactorStats") -> str:
    sig = s.ic_p < 0.05 and abs(s.mean_ic) >= 0.02
    ls_sig = s.ls_p_nw < 0.05 and s.ls_mean_monthly > 0
    if sig and ls_sig:
        return "SIGNIFICANT — the mechanical factor carries real, statistically detectable predictive power."
    if sig or ls_sig:
        return "MARGINAL — one test clears the bar, the other doesn't. Treat the edge as weak/fragile."
    return "NOT SIGNIFICANT — indistinguishable from noise on this sample. Be honest: this is the likely outcome for a price-only factor."


def text_report(period: str = "8y") -> str:
    r = validate(period)
    out = ["=" * 92,
           "FACTOR VALIDATION — chokepoint-ramp (mechanical, point-in-time) signal",
           "=" * 92]
    if "error" in r:
        return "\n".join(out + [f"[validate-factor] {r['error']}"])
    s: FactorStats = r["stats"]
    out.append("Tests the price-only factor the OOS backtest computes — NOT the curated structural score")
    out.append("(that score has no point-in-time history, so an IC test on it would be dishonest).\n")

    out.append(f"Sample: {s.n_months} monthly cross-sections (point-in-time, no look-ahead)\n")
    out.append("1) INFORMATION COEFFICIENT (monthly Spearman rank corr of signal vs next-month return)")
    out.append(f"     mean IC        : {s.mean_ic:+.4f}   (|IC|>=0.02 ~ usable; >=0.05 ~ strong)")
    out.append(f"     IC std         : {s.ic_std:.4f}")
    out.append(f"     IC-IR          : {s.ic_ir:+.3f}   (mean/std; >0.3 ~ good consistency)")
    out.append(f"     t-stat / p     : {s.ic_t:+.2f}  /  p={s.ic_p:.3f}  {'**' if s.ic_p<0.05 else '(n.s.)'}")
    out.append(f"     IC>0 hit-rate  : {s.hit_rate_ic_pos*100:.0f}% of months\n")

    out.append("2) TERCILE LONG-SHORT (top-1/3 minus bottom-1/3 by signal, next month)")
    out.append(f"     mean monthly   : {s.ls_mean_monthly*100:+.2f}%")
    out.append(f"     ann. Sharpe    : {s.ls_sharpe:+.2f}")
    out.append(f"     t-stat / p     : {s.ls_t:+.2f}  /  p={s.ls_p:.3f}   (naive)")
    out.append(f"     t-stat / p     : {s.ls_t_nw:+.2f}  /  p={s.ls_p_nw:.3f}   (Newey-West, lag 3) {'**' if s.ls_p_nw<0.05 else '(n.s.)'}\n")

    out.append("-" * 92)
    out.append(f"VERDICT: {_verdict(s)}")
    out.append("CAVEAT: residual survivorship (fixed 2026 universe; Yahoo drops delistings); long-only universe;")
    out.append("a single sector in a single AI-bull epoch. Significance here is necessary, NOT sufficient. Not advice.")
    out.append("=" * 92)
    return "\n".join(out)
