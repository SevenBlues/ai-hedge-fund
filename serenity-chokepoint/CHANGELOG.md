# Changelog

All notable changes to the **Serenity Chokepoint Engine** are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/); versions
follow [SemVer](https://semver.org/). This is an educational reproduction —
bundled data are illustrative placeholders, and nothing here is financial advice.

## Upgrading

No breaking changes across the 0.x line — every release is additive (new
commands and modules; existing commands keep working). To upgrade:

```bash
pip install -U serenity-chokepoint
serenity version          # should print 0.9.0
serenity --help           # see all subcommands
```

Runs fully offline; only `--live` and the validation/backtest commands touch the
network (Yahoo Finance, no API key).

---

## [0.9.0] — 2026-06-07 — "Bring your own ticker"

**Added**
- `serenity proxy <TICKER>` — honest, market-observable chokepoint **triage for
  any ticker**, not just the curated universe. Scores the one pillar that is
  mechanically screenable (information asymmetry = small cap + low institutional
  ownership + thin coverage) and explicitly lists the four *structural* pillars
  that need human research (76/100 of the score), refusing to fabricate them.
  Triage verdicts: `✅ FITS THE PROFILE` / `🟡 BORDERLINE` / `🔴 ALREADY DISCOVERED`.
- `SOCIAL_DRAFTS.md` — launch copy (X / 公众号 / 小红书) themed on self-falsification.

**Changed**
- `serenity thesis <TICKER>` for non-curated names now shows the proxy
  information-asymmetry pillar + a "still unknown" structural checklist and a
  triage verdict, instead of a dead-end `n/a`.

**Why it matters:** closed the biggest usability gap — you can now point the tool
at your own watchlist and get an honest "is this worth researching?" answer.

## [0.8.0] — 2026-06-07 — Validation, documented

**Added**
- `VALIDATION.md` — the full statistical writeup: the three evidence lines, the
  audit scorecard, every number, and how the from-scratch statistics are verified
  against SciPy to ~1e-11.
- README "is the signal statistically significant?" section with the scorecard
  and a link to `VALIDATION.md`.

## [0.7.0] — 2026-06-07 — One-command self-check

**Added**
- `serenity audit` — runs all three self-falsification tests (OOS walk-forward,
  factor significance, structural score) and rolls them into a single **evidence
  scorecard** + honest overall grade (`MODERATE` / `WEAK·SUGGESTIVE` /
  `INSUFFICIENT`). Network-failure robust.

## [0.6.0] — 2026-06-07 — Test the framework's own claim

**Added**
- `serenity validate-structural` — cross-sectional test of whether the chokepoint
  **score itself** explains returns, and crucially whether it survives
  **controlling for momentum** (raw OLS/Spearman, momentum baseline, and an
  orthogonalized partial regression). From-scratch OLS verified against
  `scipy.linregress`.

## [0.5.0] — 2026-06-07 — Statistical significance (the honest layer)

**Added**
- `serenity validate-factor` — cross-sectional Information Coefficient (Spearman,
  point-in-time), IC-IR, t-stat/p-value, and a tercile long-short with naïve and
  **Newey-West (HAC)** t-stats.
- `serenity validate-factor --zoo` — a battery of 8 point-in-time factors run
  through the same pipeline with **Bonferroni** multiple-testing correction.
- t-distribution p-values, OLS, Spearman and Newey-West **implemented from
  scratch (no SciPy dependency)** and validated against SciPy to ~1e-11.

**Honest finding (published, not hidden):** the headline +143.9% OOS return is
mostly momentum / sector beta — the factor's IC is not significant (p≈0.54) and
no factor survives the multiple-testing bar. Overall audit grade: WEAK/SUGGESTIVE.

## [0.4.0] — One-page thesis

**Added**
- `serenity thesis <TICKER>` — fuses the three lenses (structural **moat** ×
  growth **timing** × red-team **risk**) into a single verdict
  (`🎯 PRIME SETUP` / `⏳ POSITIONED EARLY` / `⛔ FAILS VALIDATION` / …).
- `PROMOTION_KIT.md`, `GITHUB_OPTIMIZATION.md`; PyPI badge + install line.

## [0.3.0] — Growth / ramp-inflection lens

**Added**
- `serenity growth <TICKER>` (and `--pool`) — scores the **volume-ramp
  inflection** (revenue acceleration + gross-margin turn), not generic growth.

**Changed**
- `serenity scan` refocused and clearly relabelled as a **momentum radar**
  (explicitly *not* the chokepoint method).

## [0.2.0] — Live radar

**Added**
- `serenity scan` — live full-market momentum ranking over a broad universe
  (or your own `--tickers`), to surface candidates worth researching.

## [0.1.0] — Initial engine

**Added**
- Core **Chokepoint Score** (six weighted pillars) + asymmetric-odds engine
  (win-probability, upside/downside, Kelly-capped sizing).
- NetworkX supply-chain dependency graph + topological chokepoints; demand model.
- Adversarial **red-team** (9 attack vectors) + Monte-Carlo P(EV>0).
- `serenity pool` — the certainty-gated, return-maximising high-conviction pool.
- In-sample backtest + event study; **genuine out-of-sample walk-forward** with
  regime analysis and rolling-fold robustness.
- Live-data layer (Yahoo Finance), offline fallback, installable `serenity` CLI,
  offline test suite, and `REPRODUCE.md`.

[0.9.0]: https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
[0.8.0]: https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
[0.7.0]: https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
[0.6.0]: https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
[0.5.0]: https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
[0.4.0]: https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
[0.3.0]: https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
[0.2.0]: https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
[0.1.0]: https://github.com/SevenBlues/ai-hedge-fund/tree/main/serenity-chokepoint
