"""
Structural-score validation — does the *chokepoint score itself* explain
returns, and does it survive controlling for momentum?

This stays inside Serenity's framework: instead of hunting generic price
factors, it interrogates the one thing the framework actually claims — that a
higher structural chokepoint score should map to better risk-adjusted outcomes.

THE HONEST CONSTRAINT (stated, not hidden)
------------------------------------------
The chokepoint score has NO point-in-time history: supply shares, qualification
cycles, irreplaceability were hand-curated once (≈2026). So a walk-forward /
out-of-sample IC test on it is impossible without fabricating history. We refuse
to fake that. What we CAN do honestly is a **single cross-section** test:

  for the curated, investable universe, regress realized trailing return on the
  chokepoint score, and — the key question — on the score AFTER orthogonalizing
  out momentum. If the score only "works" because high-score names also have
  high momentum, the structural edge is an illusion. If it adds explanatory
  power beyond momentum, that's the first quantitative point in its favour.

This is a small-N, in-sample, descriptive test. It is suggestive, NOT proof.
The report says so plainly. Educational; not financial advice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from serenity_chokepoint.scoring import score_universe
from serenity_chokepoint.chokepoint_data import get_universe
from serenity_chokepoint.factor_validation import _two_sided_p


@dataclass
class Regression:
    n: int
    slope: float
    intercept: float
    r_squared: float
    slope_t: float
    slope_p: float
    spearman_ic: float


def _ols(x, y) -> Regression:
    """Simple OLS y = a + b x with t-stat on the slope, plus Spearman IC."""
    import numpy as np

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    xbar, ybar = x.mean(), y.mean()
    sxx = float(((x - xbar) ** 2).sum())
    if sxx == 0 or n < 3:
        return Regression(n, 0, ybar, 0, 0, float("nan"), 0)
    b = float(((x - xbar) * (y - ybar)).sum() / sxx)
    a = float(ybar - b * xbar)
    yhat = a + b * x
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - ybar) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    # standard error of slope
    dof = n - 2
    s2 = ss_res / dof if dof > 0 else float("nan")
    se_b = math.sqrt(s2 / sxx) if (s2 == s2 and sxx > 0) else float("nan")
    t = b / se_b if (se_b and se_b > 0) else 0.0
    p = _two_sided_p(t, dof) if dof > 0 else float("nan")
    ic = _spearman(x, y)
    return Regression(n, b, a, r2, t, p, ic)


def _spearman(x, y) -> float:
    import numpy as np

    def rank(v):
        order = np.argsort(v)
        r = np.empty(len(v), dtype=float)
        r[order] = np.arange(len(v), dtype=float)
        # average ties
        _, inv, counts = np.unique(v, return_inverse=True, return_counts=True)
        return r
    rx = _rankdata(np.asarray(x, float))
    ry = _rankdata(np.asarray(y, float))
    return float(np.corrcoef(rx, ry)[0, 1]) if len(rx) > 1 else 0.0


def _rankdata(a):
    import numpy as np
    order = a.argsort()
    ranks = np.empty(len(a), float)
    ranks[order] = np.arange(1, len(a) + 1)
    # average ties
    vals, inv, counts = np.unique(a, return_inverse=True, return_counts=True)
    cum = np.cumsum(counts)
    start = cum - counts
    avg = (start + cum - 1) / 2.0 + 1  # 1-based average rank per group
    return avg[inv]


def _residualize(target, control):
    """Return residuals of target after regressing out control (orthogonalize)."""
    import numpy as np
    reg = _ols(control, target)
    control = np.asarray(control, float)
    target = np.asarray(target, float)
    return target - (reg.intercept + reg.slope * control)


def validate_structural(period: str = "2y") -> dict:
    """Cross-sectional test of chokepoint score vs realized return, raw and
    momentum-controlled, over the curated investable universe."""
    import numpy as np
    from serenity_chokepoint.backtest import fetch_history

    scores = [s for s in score_universe(get_universe()) if s.investable]
    tickers = [s.ticker for s in scores]
    if len(tickers) < 5:
        return {"error": "too few investable curated names to test"}

    hist = fetch_history(tickers, period=period, interval="1d")
    if "_error" in hist:
        return {"error": hist["_error"]}

    SKIP = 21          # ~1 month of trading days (avoid short-term reversal)
    LOOK = 252         # ~12 months
    cp, ret, mom, names = [], [], [], []
    for s in scores:
        ser = hist.get(s.ticker)
        if ser is None:
            continue
        ser = ser.dropna()
        if len(ser) < 60:
            continue
        total_ret = float(ser.iloc[-1] / ser.iloc[0] - 1.0)       # realized return over window
        # momentum control = 12-1 in trading days (skip last ~month), as much as available
        n = len(ser)
        look = min(LOOK, n - SKIP - 1)
        if look < 20:
            continue
        m = float(ser.iloc[-1 - SKIP] / ser.iloc[-1 - SKIP - look] - 1.0)
        cp.append(s.chokepoint_score)
        ret.append(total_ret)
        mom.append(m)
        names.append(s.ticker)

    if len(cp) < 5:
        return {"error": "insufficient price history for the curated names"}

    cp = np.array(cp); ret = np.array(ret); mom = np.array(mom)

    raw = _ols(cp, ret)                                  # return ~ chokepoint
    mom_reg = _ols(mom, ret)                             # return ~ momentum (baseline)
    # orthogonalize: does chokepoint explain the part of return momentum can't?
    ret_resid = _residualize(ret, mom)                   # return with momentum removed
    cp_resid = _residualize(cp, mom)                     # chokepoint with momentum removed
    controlled = _ols(cp_resid, ret_resid)               # partial relationship

    return {
        "n": len(cp), "names": names,
        "raw": raw, "momentum": mom_reg, "controlled": controlled,
        "cp": cp.tolist(), "ret": ret.tolist(), "mom": mom.tolist(),
        "period": period,
    }


def text_report(period: str = "2y") -> str:
    r = validate_structural(period)
    out = ["=" * 92,
           "STRUCTURAL-SCORE VALIDATION — does the chokepoint score explain returns?",
           "=" * 92]
    if "error" in r:
        return "\n".join(out + [f"[validate-structural] {r['error']}"])

    out.append("Single CROSS-SECTION over the curated investable universe (in-sample, small-N, descriptive).")
    out.append("The structural score has no point-in-time history, so this is suggestive — NOT an OOS proof.\n")
    out.append(f"N = {r['n']} curated names | realized return window = {r['period']}\n")

    raw: Regression = r["raw"]
    mom: Regression = r["momentum"]
    ctl: Regression = r["controlled"]

    out.append("1) RAW: realized_return ~ chokepoint_score")
    out.append(f"     Spearman IC : {raw.spearman_ic:+.3f}")
    out.append(f"     slope       : {raw.slope:+.4f}  (return per score-point)")
    out.append(f"     R²          : {raw.r_squared:.3f}")
    out.append(f"     slope t / p : {raw.slope_t:+.2f} / p={raw.slope_p:.3f}  {'**' if raw.slope_p<0.05 else '(n.s.)'}\n")

    out.append("2) BASELINE: realized_return ~ momentum (how much is just momentum?)")
    out.append(f"     R²          : {mom.r_squared:.3f}   slope t / p: {mom.slope_t:+.2f} / p={mom.slope_p:.3f}\n")

    out.append("3) KEY TEST: (return ⟂ momentum) ~ (chokepoint ⟂ momentum)")
    out.append("   i.e. does the score explain returns AFTER removing momentum?")
    out.append(f"     partial Spearman IC : {ctl.spearman_ic:+.3f}")
    out.append(f"     slope t / p         : {ctl.slope_t:+.2f} / p={ctl.slope_p:.3f}  {'**' if ctl.slope_p<0.05 else '(n.s.)'}\n")

    out.append("-" * 92)
    out.append(f"VERDICT: {_verdict(raw, ctl)}")
    out.append("CAVEAT: N≈a dozen, single in-sample cross-section, curated (survivorship) universe, one epoch.")
    out.append("This can SUGGEST the score tracks outcomes; it cannot PROVE predictive power. Not advice.")
    out.append("=" * 92)
    return "\n".join(out)


def _verdict(raw: Regression, ctl: Regression) -> str:
    raw_pos = raw.slope > 0 and raw.spearman_ic > 0
    ctl_holds = ctl.slope_t > 0 and ctl.spearman_ic > 0.1
    if not raw_pos:
        return ("the chokepoint score does NOT track realized returns even in-sample — "
                "the framework's central claim isn't visible in this cross-section.")
    if raw_pos and ctl_holds:
        return ("the score tracks returns AND retains a positive relationship after removing momentum — "
                "the first (weak, in-sample) quantitative point that the structural edge is more than momentum.")
    return ("the score tracks returns, but the relationship LARGELY DISAPPEARS once momentum is removed — "
            "honest read: most of the apparent structural edge in this sample is momentum in disguise.")
