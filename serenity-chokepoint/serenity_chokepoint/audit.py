"""
``serenity audit`` — the one-command methodology self-check.

Runs every self-falsification test the engine has and rolls them into a single
evidence scorecard plus an honest overall verdict. The point of this command is
not to flatter the strategy; it is to show, in one place, exactly how much
quantitative support the chokepoint thesis actually has — and to state plainly
where the evidence is weak or impossible to obtain.

Three independent lines of evidence:

  1. OUT-OF-SAMPLE walk-forward (oos_backtest): does the mechanical, point-in-time
     factor beat sector beta (SOXX) on a held-out test window?
  2. FACTOR significance (factor_validation): is the signal's Information
     Coefficient / long-short spread statistically distinguishable from noise —
     and does ANY factor in the battery survive multiple-testing correction?
  3. STRUCTURAL score (structural_validation): does the chokepoint score itself
     explain returns beyond momentum, in the (small, in-sample) cross-section?

Each dimension is graded PASS / WEAK / FAIL with one line of reasoning, then an
overall verdict states the honest evidence grade. Educational; not advice.
"""

from __future__ import annotations


def _grade(flag_pass: bool, flag_weak: bool) -> str:
    return "PASS" if flag_pass else ("WEAK" if flag_weak else "FAIL")


def run_audit(period_oos: str = "8y", period_struct: str = "2y") -> dict:
    """Gather all three evidence lines; each entry is robust to network failure."""
    results = {}

    # 1) OOS walk-forward
    try:
        from serenity_chokepoint import oos_backtest as oos
        wf = oos.walk_forward(period=period_oos)
        if "error" in wf:
            results["oos"] = {"error": wf["error"]}
        else:
            t = wf["test"]
            strat = t["strategy"]
            bench = t.get("SOXX") or t.get("equal_weight")
            beats_sharpe = strat.sharpe > bench.sharpe
            beats_cagr = strat.cagr > bench.cagr
            results["oos"] = {
                "test_sharpe": strat.sharpe, "bench_sharpe": bench.sharpe,
                "test_cagr": strat.cagr, "bench_cagr": bench.cagr,
                "n": strat.n_months, "split": wf["split_date"],
                "pass": beats_sharpe and beats_cagr,
                "weak": beats_sharpe or beats_cagr,
            }
    except Exception as e:  # pragma: no cover
        results["oos"] = {"error": str(e)}

    # 2) Factor significance + zoo
    try:
        from serenity_chokepoint import factor_validation as fv
        v = fv.validate(period=period_oos)
        if "error" in v:
            results["factor"] = {"error": v["error"]}
        else:
            s = v["stats"]
            ic_sig = s.ic_p < 0.05 and abs(s.mean_ic) >= 0.02
            ls_sig = s.ls_p_nw < 0.05 and s.ls_mean_monthly > 0
            zoo = fv.validate_zoo(period=period_oos)
            survivors = [r["factor"] for r in zoo.get("rows", []) if r.get("sig_bonf")] if "error" not in zoo else []
            best = zoo["rows"][0] if ("error" not in zoo and zoo["rows"]) else None
            results["factor"] = {
                "mean_ic": s.mean_ic, "ic_p": s.ic_p, "ic_ir": s.ic_ir,
                "ls_sharpe": s.ls_sharpe, "ls_p_nw": s.ls_p_nw, "n": s.n_months,
                "survivors": survivors,
                "best_factor": best["factor"] if best else None,
                "best_ic": best["mean_ic"] if best else None,
                "best_p": best["ic_p"] if best else None,
                "bonferroni": zoo.get("bonferroni_alpha") if "error" not in zoo else None,
                "pass": bool(survivors) or (ic_sig and ls_sig),
                "weak": ic_sig or ls_sig or bool(survivors),
            }
    except Exception as e:  # pragma: no cover
        results["factor"] = {"error": str(e)}

    # 3) Structural score, momentum-controlled
    try:
        from serenity_chokepoint import structural_validation as sv
        r = sv.validate_structural(period=period_struct)
        if "error" in r:
            results["structural"] = {"error": r["error"]}
        else:
            raw, ctl = r["raw"], r["controlled"]
            raw_pos = raw.spearman_ic > 0 and raw.slope > 0
            ctl_holds = ctl.slope_t > 0 and ctl.spearman_ic > 0.1
            results["structural"] = {
                "n": r["n"], "raw_ic": raw.spearman_ic, "raw_p": raw.slope_p,
                "ctl_ic": ctl.spearman_ic, "ctl_t": ctl.slope_t, "ctl_p": ctl.slope_p,
                "pass": raw_pos and ctl_holds,
                "weak": raw_pos,
            }
    except Exception as e:  # pragma: no cover
        results["structural"] = {"error": str(e)}

    return results


def _overall(scores: list[str]) -> tuple[str, str]:
    """Map the three grades to an honest evidence grade + sentence."""
    npass = scores.count("PASS")
    nweak = scores.count("WEAK")
    nfail = scores.count("FAIL")
    if npass >= 2:
        grade = "MODERATE"
        msg = ("Multiple independent tests give the factor the benefit of the doubt. Still one sector, "
               "one epoch, residual survivorship — treat as encouraging, not established.")
    elif npass + nweak >= 2 and nfail <= 1:
        grade = "WEAK / SUGGESTIVE"
        msg = ("The signal shows up directionally but rarely clears a strict significance bar. Most of the "
               "observable return is explained by momentum / sector beta; an independent structural edge is "
               "plausible but NOT statistically demonstrated on this data.")
    else:
        grade = "INSUFFICIENT"
        msg = ("On this universe and epoch the quantifiable evidence does not distinguish the factor from "
               "noise. The structural thesis may still be true — it simply cannot be proven with the data "
               "available (the score has no point-in-time history). Honesty > a flattering number.")
    return grade, msg


def text_report(period_oos: str = "8y", period_struct: str = "2y") -> str:
    r = run_audit(period_oos, period_struct)
    W = 96
    out = ["=" * W,
           "SERENITY METHODOLOGY AUDIT — three independent self-falsification tests, one scorecard",
           "=" * W,
           "Honest by design: this command tries to BREAK the thesis, not sell it.\n"]

    grades = []

    # 1) OOS
    o = r.get("oos", {})
    out.append("1) OUT-OF-SAMPLE WALK-FORWARD  (mechanical point-in-time factor vs SOXX, held-out test)")
    if "error" in o:
        out.append(f"     unavailable: {o['error']}")
        grades.append("N/A")
    else:
        g = _grade(o["pass"], o["weak"])
        grades.append(g)
        out.append(f"     test window: {o['n']} mo after {o['split']}")
        out.append(f"     Sharpe  factor {o['test_sharpe']:+.2f}  vs  SOXX {o['bench_sharpe']:+.2f}")
        out.append(f"     CAGR    factor {o['test_cagr']*100:+.1f}%  vs  SOXX {o['bench_cagr']*100:+.1f}%")
        out.append(f"     -> [{g}] {'beats sector beta OOS' if g=='PASS' else ('beats on one metric only' if g=='WEAK' else 'does not beat sector beta OOS')}")
    out.append("")

    # 2) Factor significance
    f = r.get("factor", {})
    out.append("2) FACTOR SIGNIFICANCE  (IC + long-short t-stats; battery with Bonferroni correction)")
    if "error" in f:
        out.append(f"     unavailable: {f['error']}")
        grades.append("N/A")
    else:
        g = _grade(f["pass"], f["weak"])
        grades.append(g)
        out.append(f"     mean IC {f['mean_ic']:+.4f} (p={f['ic_p']:.3f}), IC-IR {f['ic_ir']:+.2f}; "
                   f"L/S Sharpe {f['ls_sharpe']:+.2f} (NW p={f['ls_p_nw']:.3f}), n={f['n']}")
        if f.get("best_factor"):
            out.append(f"     strongest of {len(f.get('survivors', [])) or 'the'} battery: {f['best_factor']} "
                       f"(IC {f['best_ic']:+.4f}, p={f['best_p']:.3f}; Bonferroni α={f['bonferroni']:.4f})")
        surv = f.get("survivors") or []
        out.append(f"     survivors of multiple-testing: {', '.join(surv) if surv else 'none'}")
        out.append(f"     -> [{g}] {'statistically significant' if g=='PASS' else ('marginal / one test only' if g=='WEAK' else 'indistinguishable from noise')}")
    out.append("")

    # 3) Structural score
    s = r.get("structural", {})
    out.append("3) STRUCTURAL SCORE vs RETURNS  (cross-section; does it beat momentum? in-sample, small-N)")
    if "error" in s:
        out.append(f"     unavailable: {s['error']}")
        grades.append("N/A")
    else:
        g = _grade(s["pass"], s["weak"])
        grades.append(g)
        out.append(f"     N={s['n']}  raw Spearman IC {s['raw_ic']:+.3f} (p={s['raw_p']:.3f})")
        out.append(f"     after removing momentum: partial IC {s['ctl_ic']:+.3f}, slope t={s['ctl_t']:+.2f} (p={s['ctl_p']:.3f})")
        out.append(f"     -> [{g}] {'adds edge beyond momentum' if g=='PASS' else ('tracks returns but mostly momentum' if g=='WEAK' else 'no relationship even in-sample')}")
    out.append("")

    # Scorecard + verdict
    real = [g for g in grades if g != "N/A"]
    out.append("-" * W)
    out.append(f"   SCORECARD:  OOS={grades[0]}   |   Factor-significance={grades[1]}   |   Structural={grades[2]}")
    if real:
        grade, msg = _overall(real)
        out.append(f"\n   OVERALL EVIDENCE GRADE: {grade}")
        out.append(f"   {msg}")
    else:
        out.append("\n   OVERALL: no test could run (offline). Re-run with network for the real audit.")
    out.append("\n   WHAT THIS DOES NOT SAY: a low grade is not proof the thesis is wrong. The structural")
    out.append("   score has no point-in-time history, so it CANNOT be tested out-of-sample without")
    out.append("   fabricating data — we refuse to. We test what is testable and report it straight.")
    out.append("   CAVEAT: residual survivorship; one sector; one AI-bull epoch; long-only. NOT advice.")
    out.append("=" * W)
    return "\n".join(out)
