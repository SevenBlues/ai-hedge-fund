# 🔬 VALIDATION — does the signal survive statistics?

> **TL;DR.** The eye-catching out-of-sample backtest (+143.9% CAGR, beats SOXX) is
> real, but when we put the *factor* through proper significance tests, **most of
> that return is momentum / sector beta, not a statistically demonstrable
> structural edge.** We built the tests that prove this and we run them against
> ourselves. One command — `serenity audit` — grades the whole thing.
>
> This page exists because a backtest curve is the *easiest* thing to fake and the
> *least* informative thing to show. Significance testing is the part most
> reproductions skip. We don't.

```bash
serenity audit                  # all three tests → one scorecard + honest verdict
serenity validate-factor        # IC / t-stat / p-value on the factor
serenity validate-factor --zoo  # a battery of factors + multiple-testing correction
serenity validate-structural    # does the chokepoint SCORE beat momentum?
```

---

## The honest constraint, stated up front

The structural **chokepoint score** (supply shares, qualification cycles,
irreplaceability) was hand-curated **once**, in ≈2026. It has **no point-in-time
history**. That means an honest out-of-sample / walk-forward IC test *on the score
itself* is **impossible without fabricating history** — and we refuse to do that.

So we split the question in two:

- **What IS testable** look-ahead-free: the *mechanical* price-only factor (12-1
  momentum + a re-rating-gap flag) that the OOS backtest already computes
  point-in-time. We hammer it with IC and long-short t-stats.
- **What is only suggestible**: the structural score, tested on a single
  in-sample cross-section, controlling for momentum. Descriptive, not proof — and
  the report says so.

We test what is testable, and we are explicit about the rest. That refusal to
overclaim *is* the methodology.

---

## Three independent lines of evidence

### 1️⃣ Out-of-sample walk-forward — **PASS**

Does the mechanical, point-in-time factor beat the semiconductor sector (SOXX) on
a held-out test window it never saw during rule design?

| Window | Factor CAGR | SOXX CAGR | Factor Sharpe | SOXX Sharpe |
|---|--:|--:|--:|--:|
| Out-of-sample (≈2023→) | **+143.9%** | +54.1% | **+1.95** | +1.40 |

✅ On both return *and* risk-adjusted return, the factor beats sector beta
out-of-sample. (Full method, regimes, and rolling folds: `serenity backtest --oos`.)

### 2️⃣ Factor significance — **FAIL**

A backtest curve isn't significance. The real question: is the factor's
predictive power **distinguishable from luck**? We compute, point-in-time:

- **Information Coefficient (IC):** monthly cross-sectional Spearman rank
  correlation between signal and *next* month's return.
- **Long-short:** top-tercile minus bottom-tercile, with a naïve *and* a
  **Newey-West (HAC, lag 3)** t-stat (momentum sorts are autocorrelated; a naïve t
  flatters itself).

| Metric | Value | Verdict |
|---|--:|---|
| mean IC | +0.0145 | below the ~0.02 "usable" line |
| IC-IR (mean/std) | +0.07 | far below the ~0.3 "consistent" line |
| IC t-stat / p | +0.61 / **p = 0.54** | **not significant** |
| long-short Sharpe | +0.38 | looks like *something*… |
| long-short t / p (Newey-West) | +0.98 / **p = 0.33** | …but **indistinguishable from noise** |
| sample | 82 monthly cross-sections | — |

❌ Over 82 months in this universe, the price-only factor has **no statistically
detectable** edge. The IC is *directionally* positive (positive in 61% of months)
but the noise swamps it. This is the honest — and frankly *expected* — outcome for
a single-sector momentum factor.

#### The factor battery (`--zoo`) + multiple-testing correction

We then test **8** point-in-time factors through the same pipeline. Testing many
factors inflates false positives, so we apply a **Bonferroni** correction
(α = 0.05 / 8 = **0.0063** — a factor must clear *that*, not 0.05).

| factor | mean IC | IC p | L/S Sharpe | verdict |
|---|--:|--:|--:|---|
| **resid_mom (ex-beta)** | **+0.048** | 0.058 | +0.88 | strongest, but only raw-significant |
| near_52w_high | +0.035 | 0.167 | +0.71 | noise |
| mom_12_1 (the OOS signal) | +0.018 | 0.434 | +0.49 | noise |
| low_volatility | −0.012 | 0.647 | −1.15 | noise |
| *(4 more: 6-1/3-1 momentum, 1m reversal, acceleration)* | ≈0 | n.s. | — | noise |

🟡 **No factor survives the multiple-testing bar.** The most interesting result is
that **residual momentum (with sector beta removed) is the *strongest* factor** —
which tells you the apparent edge is *mostly sector beta*, and what little
idiosyncratic signal exists doesn't reach significance on this sample.

### 3️⃣ Structural score vs returns — **WEAK**

Now the framework's own central claim: does a higher **chokepoint score** map to
better returns — and crucially, does it survive **controlling for momentum**?

| Test | Result | Reading |
|---|--:|---|
| **raw:** return ~ chokepoint score | Spearman IC **+0.44**, p ≈ 0.07 | the score *does* track returns |
| **baseline:** return ~ momentum | R² ≈ **0.78**, p < 0.001 | …but momentum alone explains most of it |
| **key test:** (return ⟂ mom) ~ (score ⟂ mom) | partial IC +0.05, t ≈ **−0.15**, p ≈ 0.90 | once momentum is removed, **the score's edge vanishes** |

🟡 In this small (N ≈ 14), in-sample cross-section, the chokepoint score tracks
returns — but **almost entirely because high-score names are also high-momentum
names.** Orthogonalize momentum out and there's nothing left to measure. *(This is
suggestive, not proof; N is tiny and the score has no point-in-time history.)*

---

## The scorecard (`serenity audit`)

```
   SCORECARD:  OOS=PASS   |   Factor-significance=FAIL   |   Structural=WEAK

   OVERALL EVIDENCE GRADE: WEAK / SUGGESTIVE
   The signal shows up directionally but rarely clears a strict significance
   bar. Most of the observable return is explained by momentum / sector beta;
   an independent structural edge is plausible but NOT statistically
   demonstrated on this data.
```

The three lines are not contradictory — they *resolve* the tension a single
backtest hides:

> The +143.9% OOS return is real, but it is **mostly momentum and sector beta.**
> An independent, quantifiable structural alpha is **plausible but not
> statistically demonstrated** on one sector, in one AI-bull epoch, with a
> survivorship-tinged universe.

### What a low grade does **not** say

A `WEAK / SUGGESTIVE` grade is **not** proof the chokepoint thesis is wrong. It
means the *quantifiable evidence available to us* cannot separate the structural
edge from momentum. The score has no point-in-time history, so it cannot be tested
out-of-sample without fabricating data — and **honesty beats a flattering
number.** The structural logic may well be right; this data simply can't prove it.

---

## How the statistics are computed (and verified)

We deliberately keep the package dependency-light: **no SciPy**. All the
statistics are implemented from scratch and **validated against SciPy to ~1e-11**:

- **t-distribution p-values** — via a regularized incomplete-beta function
  (Lentz's continued fraction). Matches `scipy.stats.t.sf` to ~1e-11.
- **OLS** (slope, intercept, R², slope t, p) — matches `scipy.stats.linregress`
  exactly.
- **Spearman IC** with proper tie-averaged ranks — matches `scipy.stats.spearmanr`
  and `scipy.stats.rankdata`.
- **Newey-West / HAC** variance with a Bartlett kernel for the long-short t-stat,
  because momentum sorts induce serial correlation a naïve t ignores.
- The point-in-time signal machinery is **reused from `oos_backtest`**, so no
  look-ahead is re-introduced.

These checks ship as unit tests (`pytest -q`).

---

## Limitations (the ones that matter here)

- **Residual survivorship.** The universe is drawn in 2026 and Yahoo drops most
  delisted names — so the sample tilts toward survivors.
- **One sector, one epoch.** Everything here is AI-hardware / semis during a
  historic compute buildout. Significance found (or not) here may not generalize.
- **Long-only.** The long-short is illustrative; the strategy itself is long-only.
- **Small N for the structural test.** N ≈ 14 curated names is too few for strong
  cross-sectional inference; treat it as a sanity check, not a study.
- **No point-in-time structural data.** The single biggest limitation — and the
  reason we *cannot* OOS-test the score itself. Fixing this would require a
  historical archive of supply shares / qualification status, which doesn't exist
  publicly.

---

## Reproduce

```bash
pip install serenity-chokepoint
serenity audit                 # the full scorecard (needs network for prices)
serenity validate-factor --zoo # the factor battery
pytest -q                      # the offline tests, incl. the stats-vs-reference checks
```

**Educational reproduction — NOT financial advice.** See the [README](README.md)
disclaimer.
