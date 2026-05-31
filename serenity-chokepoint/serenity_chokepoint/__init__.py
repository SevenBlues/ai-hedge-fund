"""
Serenity Chokepoint Engine
==========================

A transparent, auditable reproduction of the AI supply-chain "Chokepoint Theory"
investment framework: reverse-engineer the AI-compute supply chain, find the
physically irreplaceable, supply-concentrated, hard-to-qualify, still-undiscovered
bottlenecks the hyperscaler buildout must depend on, and build a high-conviction
stock pool that maximises return given an as-certain-as-possible win rate.

⚠️ Educational reproduction of a publicly-described framework. The curated data
are illustrative placeholder estimates — NOT real signals, NOT investment advice,
and NOT affiliated with or endorsed by Serenity (@aleabitoreddit).

Modules
-------
- chokepoint_data : curated universe of supply-chain nodes + attributes
- scoring         : the Chokepoint Score (0-100) + asymmetric-odds engine
- supply_chain    : NetworkX dependency graph + structural-chokepoint detection
- demand_model    : AI-compute -> optical-interconnect demand projection
- adversarial     : Step-3 red/blue-team validation + Monte-Carlo
- live_data       : Yahoo Finance refresh of market-derived fields
- backtest / oos_backtest : in-sample + out-of-sample validation
- pool            : the product — certainty-gated, return-maximising stock pool
- cli             : the `serenity` command-line interface
"""

__version__ = "0.4.0"

from serenity_chokepoint.scoring import ChokepointScore, score_universe  # noqa: F401
from serenity_chokepoint.pool import brief, select_pool  # noqa: F401
