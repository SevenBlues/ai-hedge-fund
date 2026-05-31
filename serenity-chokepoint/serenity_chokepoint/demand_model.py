"""
AI-compute -> optical-interconnect demand projection (framework Step 1/4).

A deliberately simple, transparent model of the demand tsunami that drives the
whole thesis: as AI clusters scale, the number of high-speed optical lanes
(and therefore lasers, InP substrate area, test inserts, ...) grows *faster*
than raw FLOPs, because scale-out networking and the shift from pluggables to
co-packaged optics raise optical intensity per unit of compute.

We project installed optical interconnect "lanes" and the implied laser/
substrate pull, then compare it to a supplier-capacity growth path to size the
demand-vs-supply gap that the chokepoint thesis monetises.

No external data needed; assumptions are explicit and easily overridden.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DemandAssumptions:
    base_year: int = 2026
    horizon: int = 4                     # project to base_year + horizon
    compute_cagr: float = 0.65           # AI accelerator FLOPs CAGR
    optical_intensity_cagr: float = 0.20 # extra optical lanes per FLOP (CPO shift)
    capacity_cagr: float = 0.22          # chokepoint supplier capacity CAGR
    base_optical_index: float = 100.0    # arbitrary 2026 = 100 demand index


def project(assump: DemandAssumptions | None = None) -> dict:
    """Return year-by-year optical-demand vs capacity index and the cumulative gap."""
    a = assump or DemandAssumptions()
    # optical demand grows at (1+compute)*(1+intensity) - 1 effectively
    demand_cagr = (1 + a.compute_cagr) * (1 + a.optical_intensity_cagr) - 1

    rows = []
    demand = a.base_optical_index
    capacity = a.base_optical_index
    for i in range(a.horizon + 1):
        year = a.base_year + i
        if i > 0:
            demand *= (1 + demand_cagr)
            capacity *= (1 + a.capacity_cagr)
        gap = demand - capacity
        rows.append(
            {
                "year": year,
                "demand_index": round(demand, 1),
                "capacity_index": round(capacity, 1),
                "shortfall_pct": round(100 * gap / capacity, 1),
            }
        )
    return {
        "demand_cagr": round(demand_cagr, 4),
        "capacity_cagr": a.capacity_cagr,
        "rows": rows,
        "terminal_shortfall_pct": rows[-1]["shortfall_pct"],
    }


def summary_text(proj: dict | None = None) -> str:
    p = proj or project()
    lines = [
        f"Optical-demand CAGR (compute x CPO intensity): {p['demand_cagr']*100:.1f}%  "
        f"vs supplier capacity CAGR {p['capacity_cagr']*100:.1f}%",
        f"{'Year':<6}{'Demand':>10}{'Capacity':>10}{'Shortfall':>12}",
    ]
    for r in p["rows"]:
        lines.append(f"{r['year']:<6}{r['demand_index']:>10}{r['capacity_index']:>10}{r['shortfall_pct']:>11}%")
    lines.append(
        f"=> By {p['rows'][-1]['year']} optical demand outruns chokepoint capacity by "
        f"{p['terminal_shortfall_pct']:.0f}% — the structural shortage the thesis monetises."
    )
    return "\n".join(lines)
