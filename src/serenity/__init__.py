"""
Serenity Chokepoint Engine
==========================

A quantitative reproduction of the "Chokepoint Theory" investment framework
popularised by the trader Serenity (@aleabitoreddit): reverse-engineer the AI
compute supply chain layer by layer, find the physically irreplaceable,
supply-concentrated, hard-to-qualify "screws" that the hyperscaler buildout
*must* depend on, and go long the ones the market has not priced yet.

This package is self-contained and runs fully offline on a curated, sourced
candidate universe (``chokepoint_data.py``). It does NOT constitute investment
advice — it is an educational reproduction of a publicly-described framework.

Modules
-------
- chokepoint_data : curated universe of supply-chain nodes + attributes
- scoring         : the Chokepoint Score (0-100) + asymmetric-odds engine
- supply_chain    : NetworkX dependency graph + structural-chokepoint detection
- demand_model    : AI-compute -> optical-interconnect demand projection
- report          : ranked screen + matplotlib visual report
- run_screen      : CLI entry point
"""

from src.serenity.scoring import score_universe, ChokepointScore  # noqa: F401
