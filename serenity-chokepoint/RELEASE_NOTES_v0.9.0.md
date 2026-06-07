# Serenity Chokepoint Engine v0.9.0 — Release Notes

> Paste the section below into the GitHub Release body at
> <https://github.com/SevenBlues/ai-hedge-fund/releases/new>
> (tag: `serenity-v0.9.0`, target: `main`, title: `Serenity Chokepoint Engine v0.9.0`).

---

A reproducible, auditable method for finding AI supply-chain chokepoints.
Educational reproduction — bundled data are illustrative placeholders; **not financial advice**.

    pip install -U serenity-chokepoint
    serenity audit

### ✨ Highlights

**The method**
- 6-pillar Chokepoint Score + asymmetric-odds engine, NetworkX supply-chain graph, demand model
- Adversarial red-team + Monte-Carlo; certainty-gated, return-maximising `serenity pool`
- `serenity scan` (momentum radar), `serenity growth` (ramp-inflection), `serenity thesis` (moat × timing × risk)

**Statistical self-falsification — the honest layer**
- `serenity validate-factor` (+ `--zoo`): IC, t-stats, p-values, Newey-West long-short, Bonferroni-corrected factor battery
- `serenity validate-structural`: does the chokepoint score beat momentum?
- `serenity audit`: rolls all three tests into one evidence scorecard + verdict
- **Honest finding (published, not hidden):** the +143.9% OOS return is mostly momentum / sector beta; the factor IC is not significant (p≈0.54); overall grade **WEAK/SUGGESTIVE**. Full writeup in `VALIDATION.md`.
- All statistics implemented from scratch, verified against SciPy to ~1e-11

**Usability**
- `serenity proxy <TICKER>`: honest market-observable triage for ANY ticker (not just the curated universe)

### 📦 Notes
- 23 network-free tests; runs fully offline (`--live` is the only network touch)
- No breaking changes across the 0.x line — see [CHANGELOG.md](CHANGELOG.md)

⚠️ Educational; **not financial advice**.
