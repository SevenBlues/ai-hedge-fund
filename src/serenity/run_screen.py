"""
CLI entry point for the Serenity Chokepoint Engine.

Examples
--------
    poetry run python -m src.serenity.run_screen
    poetry run python -m src.serenity.run_screen --live --adversarial
    poetry run python -m src.serenity.run_screen --top 10 --sort odds_ratio
    poetry run python -m src.serenity.run_screen --live --adversarial --survivors-only \
        --png out/report.png --json out/scores.json
    poetry run python -m src.serenity.run_screen --adversarial --llm   # real multi-LLM red-team
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os

from src.serenity.adversarial import llm_redteam, redteam_node_full
from src.serenity.chokepoint_data import get_universe
from src.serenity.demand_model import summary_text
from src.serenity.report import adversarial_report, render_png, text_report
from src.serenity.scoring import rank, score_universe
from src.serenity.supply_chain import ascii_layers


def main() -> None:
    ap = argparse.ArgumentParser(description="Serenity Chokepoint Engine — AI supply-chain high-odds screen")
    ap.add_argument("--top", type=int, default=15, help="rows to show")
    ap.add_argument("--sort", default="expected_value",
                    choices=["expected_value", "odds_ratio", "chokepoint_score", "kelly_weight"])
    ap.add_argument("--live", action="store_true", help="refresh market-derived fields from Yahoo Finance")
    ap.add_argument("--adversarial", action="store_true", help="run Step-3 red/blue-team validation")
    ap.add_argument("--survivors-only", action="store_true", help="restrict final book to adversarial survivors")
    ap.add_argument("--llm", action="store_true", help="also run the real multi-LLM devil's advocate (needs API keys)")
    ap.add_argument("--png", default=None, help="path to write the visual report PNG")
    ap.add_argument("--json", default=None, help="path to dump full scores as JSON")
    ap.add_argument("--no-graph", action="store_true", help="skip the textual layer map")
    args = ap.parse_args()

    # ---- data source: curated or live ---------------------------------------
    nodes = get_universe()
    if args.live:
        from src.serenity.live_data import enrich_universe
        print("[live] fetching from Yahoo Finance ...")
        nodes, rep = enrich_universe(nodes)
        if rep["live"]:
            print(f"[live] refreshed {len(rep['refreshed'])} tickers")
            for tkr, ch in rep["changelog"].items():
                print(f"       {tkr}: {'; '.join(ch)}")
            if rep["errors"]:
                print(f"[live] no live data for: {', '.join(rep['errors'])} (kept curated)")
        else:
            print("[live] no network/yfinance — falling back to curated data")
        print()

    scores = score_universe(nodes)
    node_map = {n.ticker: n for n in nodes}

    if not args.no_graph:
        print(ascii_layers(nodes))
        print()
        print(summary_text())
        print()

    # ---- base ranking -------------------------------------------------------
    if args.sort == "expected_value":
        print(text_report(scores, top=args.top))
    else:
        ranked = rank(scores, by=args.sort)[: args.top]
        print(f"\nRanked by {args.sort}:")
        for i, s in enumerate(ranked, 1):
            print(f"{i:>2} {s.ticker:<7} CP={s.chokepoint_score:>5.1f} odds={s.odds_ratio:>5.1f} "
                  f"E[V]={s.expected_value:>+5.2f} kelly={s.kelly_weight*100:>4.1f}%  {', '.join(s.flags)}")

    # ---- adversarial validation --------------------------------------------
    survivors: set[str] = set()
    if args.adversarial:
        print()
        print(adversarial_report(nodes, top=args.top))
        survivors = {n.ticker for n in nodes if n.market_cap_b > 0 and redteam_node_full(n).survives}

        if args.survivors_only:
            print(f"\n[survivors-only] high-conviction book limited to: {', '.join(sorted(survivors)) or 'none'}")

        if args.llm:
            print("\n[llm] polling multi-model devil's advocate on top survivors ...")
            for tkr in sorted(survivors)[:3] or [s.ticker for s in rank(scores)[:3]]:
                res = llm_redteam(node_map[tkr])
                print(f"  {tkr}: consensus_survives={res.get('consensus_survives')} "
                      f"{('('+res['note']+')') if res.get('note') else ''}")

    # ---- artifacts ----------------------------------------------------------
    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        payload = []
        for s in scores:
            row = dataclasses.asdict(s)
            if args.adversarial and s.ticker in node_map:
                r = redteam_node_full(node_map[s.ticker])
                if r:
                    row["adversarial"] = {
                        "resilience": r.resilience, "adversarial_ev": r.adversarial_ev,
                        "survives": r.survives, "prob_positive_ev": r.mc_prob_positive_ev,
                        "top_objection": r.top_objection, "critical_flags": r.critical_flags,
                    }
            payload.append(row)
        with open(args.json, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\n[json] wrote {args.json}")

    if args.png:
        os.makedirs(os.path.dirname(args.png) or ".", exist_ok=True)
        path = render_png(args.png, nodes=nodes)
        print(f"[png]  wrote {path}")


if __name__ == "__main__":
    main()
