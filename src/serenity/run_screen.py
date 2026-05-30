"""
CLI entry point for the Serenity Chokepoint Engine.

Examples
--------
    poetry run python -m src.serenity.run_screen
    poetry run python -m src.serenity.run_screen --top 10 --sort odds_ratio
    poetry run python -m src.serenity.run_screen --png out/report.png --json out/scores.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os

from src.serenity.demand_model import summary_text
from src.serenity.report import render_png, text_report
from src.serenity.scoring import rank, score_universe
from src.serenity.supply_chain import ascii_layers


def main() -> None:
    ap = argparse.ArgumentParser(description="Serenity Chokepoint Engine — AI supply-chain high-odds screen")
    ap.add_argument("--top", type=int, default=15, help="rows to show")
    ap.add_argument("--sort", default="expected_value",
                    choices=["expected_value", "odds_ratio", "chokepoint_score", "kelly_weight"])
    ap.add_argument("--png", default=None, help="path to write the visual report PNG")
    ap.add_argument("--json", default=None, help="path to dump full scores as JSON")
    ap.add_argument("--no-graph", action="store_true", help="skip the textual layer map")
    args = ap.parse_args()

    scores = score_universe()

    if not args.no_graph:
        print(ascii_layers())
        print()
        print(summary_text())
        print()

    # Re-rank by the requested key for the printed table while reusing text_report's body
    if args.sort == "expected_value":
        print(text_report(scores, top=args.top))
    else:
        ranked = rank(scores, by=args.sort)[: args.top]
        print(f"\nRanked by {args.sort}:")
        for i, s in enumerate(ranked, 1):
            print(f"{i:>2} {s.ticker:<7} CP={s.chokepoint_score:>5.1f} odds={s.odds_ratio:>5.1f} "
                  f"E[V]={s.expected_value:>+5.2f} kelly={s.kelly_weight*100:>4.1f}%  {', '.join(s.flags)}")

    if args.json:
        os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
        with open(args.json, "w") as f:
            json.dump([dataclasses.asdict(s) for s in scores], f, indent=2)
        print(f"\n[json] wrote {args.json}")

    if args.png:
        os.makedirs(os.path.dirname(args.png) or ".", exist_ok=True)
        path = render_png(args.png)
        print(f"[png]  wrote {path}")


if __name__ == "__main__":
    main()
