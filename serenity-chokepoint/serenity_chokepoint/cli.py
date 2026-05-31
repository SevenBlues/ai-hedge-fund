"""
``serenity`` — command-line interface for the Serenity Chokepoint Engine.

Verb-based subcommands (like git / claude):

    serenity pool                 # the product: the high-conviction stock pool
    serenity pool --live          # tighten the pool with live market data
    serenity scan                 # live full-market radar over a broad universe
    serenity scan --tickers NVDA,AXTI,SIVE   # scan your own list
    serenity growth AXTI          # growth / ramp-inflection analysis of a ticker
    serenity growth --pool        # growth table across the curated pool
    serenity thesis AXTI          # one-page full thesis: moat × timing × risk
    serenity validate AXTI        # deep-dive one ticker: score + red-team
    serenity screen --full        # full analytical screen (table + supply map)
    serenity supply-chain         # the 7-layer map + structural chokepoints
    serenity backtest             # in-sample backtest + factor + event study
    serenity backtest --oos       # genuine out-of-sample walk-forward + robustness
    serenity report --png out.png # write the 4-panel visual report
    serenity version
"""

from __future__ import annotations

import argparse
import sys


def _enrich(live: bool):
    from serenity_chokepoint.chokepoint_data import get_universe
    nodes = get_universe()
    if live:
        from serenity_chokepoint.live_data import enrich_universe
        print("[live] fetching from Yahoo Finance ...", file=sys.stderr)
        nodes, rep = enrich_universe(nodes)
        if not rep["live"]:
            print("[live] no network/yfinance — using curated data", file=sys.stderr)
    return nodes


def cmd_pool(args):
    from serenity_chokepoint.pool import brief
    print(brief(nodes=_enrich(args.live)))


def cmd_scan(args):
    from serenity_chokepoint.scanner import text_report
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None
    print(text_report(tickers=tickers, period=args.period, top=args.top))


def cmd_growth(args):
    from serenity_chokepoint.growth import text_report, pool_growth_table
    if args.pool:
        print(pool_growth_table())
    elif args.ticker:
        print(text_report(args.ticker))
    else:
        print("usage: serenity growth <TICKER>   |   serenity growth --pool")
        return 1


def cmd_thesis(args):
    from serenity_chokepoint.thesis import thesis_report
    print(thesis_report(args.ticker))


def cmd_validate(args):
    from serenity_chokepoint.chokepoint_data import by_ticker
    from serenity_chokepoint.scoring import score_node
    from serenity_chokepoint.adversarial import redteam_node_full

    nodes = {n.ticker: n for n in _enrich(args.live)}
    t = args.ticker.upper()
    if t not in nodes:
        print(f"'{t}' is not in the curated universe. Known: {', '.join(sorted(nodes))}")
        return 1
    n = nodes[t]
    cp = score_node(n)
    red = redteam_node_full(n)
    print(f"\n{t} — {n.name}   (layer {n.layer})")
    print(f"  thesis : {n.thesis}")
    print(f"  Chokepoint score : {cp.chokepoint_score:.1f}/100   flags: {', '.join(cp.flags) or '—'}")
    print("  pillars:")
    for k, v in cp.pillars.items():
        print(f"     {k:<22} {v:.2f}")
    print(f"  Odds   : win {cp.win_prob*100:.0f}%  upside {cp.upside_mult:.1f}x  downside {cp.downside_loss*100:.0f}%  "
          f"odds {cp.odds_ratio:.1f}  E[V] {cp.expected_value:+.2f}")
    print(f"  Red-team: resilience {red.resilience:.2f}  P(EV>0) {(red.mc_prob_positive_ev or 0)*100:.0f}%  "
          f"survives={red.survives}")
    print(f"  Top objection: {red.top_objection}")
    print("  (passes certainty gate -> eligible for the pool)" if red.survives and cp.win_prob >= 0.6
          and cp.chokepoint_score >= 60 else "  (does NOT clear the certainty gate)")
    return 0


def cmd_screen(args):
    from serenity_chokepoint.scoring import score_universe, rank
    from serenity_chokepoint.report import text_report, adversarial_report
    from serenity_chokepoint.supply_chain import ascii_layers
    from serenity_chokepoint.demand_model import summary_text

    nodes = _enrich(args.live)
    if args.full:
        print(ascii_layers(nodes)); print(); print(summary_text()); print()
    print(text_report(score_universe(nodes), top=args.top))
    if args.adversarial:
        print(); print(adversarial_report(nodes, top=args.top))


def cmd_supply_chain(args):
    from serenity_chokepoint.supply_chain import ascii_layers, build_graph, structural_chokepoints
    nodes = _enrich(args.live)
    print(ascii_layers(nodes)); print()
    central = structural_chokepoints(build_graph(nodes))
    print("Structural chokepoints (graph topology):")
    for tkr, m in sorted(central.items(), key=lambda kv: kv[1]["criticality"], reverse=True)[:8]:
        print(f"  {tkr:<8} criticality={m['criticality']:.3f}  dependents={m['dependents']}  "
              f"betweenness={m['betweenness']:.3f}")


def cmd_backtest(args):
    if args.oos:
        from serenity_chokepoint import oos_backtest as oos
        print(oos.text_report(period=args.period))
        print(); print(oos.robustness_report(period=args.period))
        if args.png:
            oos.render_png(args.png.replace(".png", "_oos.png"), period=args.period)
            oos.render_robust_png(args.png.replace(".png", "_robust.png"), period=args.period)
            print(f"[png] wrote {args.png.replace('.png', '_oos.png')} and _robust.png")
    else:
        from serenity_chokepoint import backtest as bt
        print(bt.text_report(period=args.period, live=args.live))
        if args.png and bt.render_png(args.png, period=args.period, live=args.live):
            print(f"[png] wrote {args.png}")


def cmd_report(args):
    from serenity_chokepoint.report import render_png
    path = render_png(args.png, nodes=_enrich(args.live))
    print(f"[png] wrote {path}")


def cmd_version(args):
    from serenity_chokepoint import __version__
    print(f"serenity-chokepoint {__version__}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="serenity",
        description="Serenity Chokepoint Engine — find AI supply-chain bottleneck stocks. NOT financial advice.",
    )
    sub = p.add_subparsers(dest="cmd")

    def add_live(sp):
        sp.add_argument("--live", action="store_true", help="refresh market data from Yahoo Finance")

    sp = sub.add_parser("pool", help="print the high-conviction stock pool (default product)")
    add_live(sp); sp.set_defaults(func=cmd_pool)

    sp = sub.add_parser("scan", help="live full-market radar over a broad universe (changes daily)")
    sp.add_argument("--tickers", default=None, help="comma-separated custom universe (default: broad AI supply chain)")
    sp.add_argument("--period", default="2y"); sp.add_argument("--top", type=int, default=25)
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("thesis", help="one-page full thesis: moat × timing × risk")
    sp.add_argument("ticker"); sp.set_defaults(func=cmd_thesis)

    sp = sub.add_parser("growth", help="Serenity growth/ramp-inflection analysis of a ticker (or --pool)")
    sp.add_argument("ticker", nargs="?", default=None)
    sp.add_argument("--pool", action="store_true", help="growth table for the whole curated pool")
    sp.set_defaults(func=cmd_growth)

    sp = sub.add_parser("validate", help="deep-dive one ticker (score + adversarial red-team)")
    sp.add_argument("ticker"); add_live(sp); sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("screen", help="full analytical screen table")
    add_live(sp); sp.add_argument("--full", action="store_true"); sp.add_argument("--adversarial", action="store_true")
    sp.add_argument("--top", type=int, default=15); sp.set_defaults(func=cmd_screen)

    sp = sub.add_parser("supply-chain", help="7-layer map + structural chokepoints")
    add_live(sp); sp.set_defaults(func=cmd_supply_chain)

    sp = sub.add_parser("backtest", help="validate the factor on real price history")
    add_live(sp); sp.add_argument("--oos", action="store_true", help="genuine out-of-sample walk-forward")
    sp.add_argument("--period", default="2y"); sp.add_argument("--png", default=None); sp.set_defaults(func=cmd_backtest)

    sp = sub.add_parser("report", help="write the 4-panel visual report PNG")
    add_live(sp); sp.add_argument("--png", default="serenity_report.png"); sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("version", help="print version"); sp.set_defaults(func=cmd_version)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        # default to the product
        from serenity_chokepoint.pool import brief
        print(brief())
        print("\n(tip: `serenity pool --live`, `serenity validate AXTI`, `serenity --help`)")
        return 0
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
