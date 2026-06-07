"""
Serenity-style growth analysis (成长性分析).

This is the project's analytical heart applied to GROWTH. It is NOT a generic
"high revenue growth = good" screen. Serenity's thesis monetises a very specific
moment: the **volume-ramp inflection** — when a qualified chokepoint supplier
goes from sampling to mass production and the economics flip (revenue
accelerates AND gross margin turns up AND operating losses collapse). That
inflection, bought before the Street re-rates it, is where the asymmetric return
lives.

So the Growth Score rewards, in order of Serenity-relevance:
  1. Revenue ACCELERATION (is YoY growth speeding up? — the ramp starting)
  2. Margin INFLECTION (gross margin rising + operating losses shrinking →
     operating leverage as volume scales)
  3. Revenue growth level (TTM YoY)
  4. Reinvestment / moat (R&D intensity)
  5. Growth-adjusted valuation (venture-style: growth vs the multiple, not TTM P/S)

Data: Yahoo Finance (free, no API key). Needs network. Educational; not advice.

Design mirrors the line-item → sub-score → signal pattern of virattt/ai-hedge-fund's
growth agents (Cathie Wood / Peter Lynch), but re-centred on the ramp inflection.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class GrowthProfile:
    ticker: str
    ok: bool
    growth_score: float = 0.0           # 0..100
    ramp_stage: str = ""                # human verdict
    rev_growth_yoy: float | None = None # TTM YoY
    rev_acceleration: float | None = None  # recent YoY minus older YoY (pts, fraction)
    gross_margin_now: float | None = None
    gross_margin_trend: float | None = None  # pts change over ~4 quarters
    op_margin_now: float | None = None
    op_margin_trend: float | None = None
    rd_intensity: float | None = None
    peg: float | None = None
    ev_sales: float | None = None
    subscores: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    error: str | None = None


def _row(df, *names):
    """Return a list of floats (most-recent-first) for the first matching row name."""
    if df is None or getattr(df, "empty", True):
        return []
    for n in names:
        if n in df.index:
            return [float(v) if v == v else None for v in df.loc[n].values]
    return []


def _ttm(vals, start=0):
    """Sum of 4 quarters from index `start`, or None if missing."""
    chunk = vals[start:start + 4]
    if len(chunk) < 4 or any(v is None for v in chunk):
        return None
    return sum(chunk)


def analyze_growth(ticker: str) -> GrowthProfile:
    try:
        import yfinance as yf
    except Exception as e:
        return GrowthProfile(ticker, ok=False, error=f"yfinance unavailable: {e}")

    # map non-US / proxy tickers to their Yahoo symbol (SIVE -> SIVE.ST, etc.)
    try:
        from serenity_chokepoint.live_data import YAHOO_SYMBOL
        symbol = YAHOO_SYMBOL.get(ticker, ticker)
    except Exception:
        symbol = ticker
    if symbol is None:
        return GrowthProfile(ticker, ok=False, error="no public listing")

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
        q = t.quarterly_income_stmt
    except Exception as e:
        return GrowthProfile(ticker, ok=False, error=f"{type(e).__name__}: {str(e)[:120]}")

    rev = _row(q, "Total Revenue", "TotalRevenue")
    gp = _row(q, "Gross Profit", "GrossProfit")
    oi = _row(q, "Operating Income", "OperatingIncome", "Operating Income Or Loss")
    rd = _row(q, "Research And Development", "ResearchAndDevelopment")

    p = GrowthProfile(ticker, ok=True)
    notes = p.notes
    sub: dict[str, float] = {}

    # --- 1. Revenue growth (TTM YoY) ---
    g_yoy = None
    ttm0, ttm1 = _ttm(rev, 0), _ttm(rev, 4)
    if ttm0 and ttm1 and ttm1 > 0:
        g_yoy = ttm0 / ttm1 - 1.0
    elif info.get("revenueGrowth") is not None:
        g_yoy = info["revenueGrowth"]
        notes.append("YoY from .info (insufficient quarters for TTM)")
    p.rev_growth_yoy = g_yoy
    sub["revenue_growth"] = _clip((g_yoy or 0) / 0.50)  # 50% YoY -> full marks

    # --- 2. Revenue acceleration (single-Q YoY now vs ~2 quarters earlier) ---
    accel = None
    if len(rev) >= 6 and all(rev[i] is not None for i in (0, 1, 4, 5)) and rev[4] and rev[5]:
        yoy_now = rev[0] / rev[4] - 1.0
        yoy_prev = rev[1] / rev[5] - 1.0
        accel = yoy_now - yoy_prev
    p.rev_acceleration = accel
    sub["acceleration"] = _clip(0.5 + (accel or 0) / 0.20)  # +20pts accel -> full

    # --- 3. Margin inflection (gross margin up + operating losses collapsing) ---
    gm_now = gm_old = om_now = om_old = None
    if rev and rev[0] and gp and gp[0] is not None:
        gm_now = gp[0] / rev[0]
    if len(rev) >= 5 and rev[4] and len(gp) >= 5 and gp[4] is not None:
        gm_old = gp[4] / rev[4]
    if rev and rev[0] and oi and oi[0] is not None:
        om_now = oi[0] / rev[0]
    if len(rev) >= 5 and rev[4] and len(oi) >= 5 and oi[4] is not None:
        om_old = oi[4] / rev[4]
    p.gross_margin_now = gm_now
    p.gross_margin_trend = (gm_now - gm_old) if (gm_now is not None and gm_old is not None) else None
    p.op_margin_now = om_now
    p.op_margin_trend = (om_now - om_old) if (om_now is not None and om_old is not None) else None

    gm_score = _clip(0.5 + (p.gross_margin_trend or 0) / 0.10)       # +10pts GM -> full
    om_score = _clip(0.5 + (p.op_margin_trend or 0) / 0.15)          # +15pts OM -> full
    sub["margin_inflection"] = 0.5 * gm_score + 0.5 * om_score

    # --- 4. Reinvestment / moat (R&D intensity) ---
    rd_int = None
    if rev and rev[0] and rd and rd[0] is not None:
        rd_int = rd[0] / rev[0]
    elif info.get("totalRevenue") and info.get("researchAndDevelopment"):
        rd_int = info["researchAndDevelopment"] / info["totalRevenue"]
    p.rd_intensity = rd_int
    sub["reinvestment"] = _clip((rd_int or 0) / 0.15)               # 15% R&D -> full

    # --- 5. Growth-adjusted valuation (venture-style, not TTM P/S) ---
    peg = info.get("pegRatio")
    ev_sales = info.get("enterpriseToRevenue") or info.get("priceToSalesTrailing12Months")
    p.peg = peg
    p.ev_sales = ev_sales
    # cheaper growth -> higher. EV/Sales divided by growth% (lower is better).
    val_score = 0.5
    if ev_sales and g_yoy and g_yoy > 0:
        ev_sales_to_growth = ev_sales / (g_yoy * 100)   # e.g. 58 / 39 = 1.5
        val_score = _clip(1.0 - (ev_sales_to_growth - 0.5) / 2.0)  # 0.5->1.0, 2.5->0.0
    elif peg and peg > 0:
        val_score = _clip(1.0 - (peg - 1.0) / 3.0)      # PEG 1 -> 0.75, 4 -> 0
    sub["growth_valuation"] = val_score

    # --- composite ---
    weights = {
        "acceleration": 25,
        "margin_inflection": 25,
        "revenue_growth": 22,
        "reinvestment": 13,
        "growth_valuation": 15,
    }
    score = sum(sub.get(k, 0) * w for k, w in weights.items())
    p.subscores = {k: round(sub.get(k, 0), 3) for k in weights}
    p.growth_score = round(score, 1)

    # --- ramp-stage verdict ---
    p.ramp_stage = _classify(p)

    # readable notes
    if g_yoy is not None:
        notes.append(f"TTM revenue YoY {g_yoy*100:+.0f}%")
    if accel is not None:
        notes.append(f"growth {'accelerating' if accel > 0.02 else 'decelerating' if accel < -0.02 else 'steady'} ({accel*100:+.0f}pts)")
    if p.gross_margin_trend is not None:
        notes.append(f"gross margin {gm_now*100:.0f}% ({p.gross_margin_trend*100:+.0f}pts)")
    if p.op_margin_trend is not None:
        notes.append(f"op margin {om_now*100:+.0f}% ({p.op_margin_trend*100:+.0f}pts)")
    if rd_int is not None:
        notes.append(f"R&D {rd_int*100:.0f}% of rev")
    return p


def _classify(p: GrowthProfile) -> str:
    g = p.rev_growth_yoy or 0
    a = p.rev_acceleration
    accel = a if a is not None else 0.0
    margin_turn = (p.gross_margin_trend or 0) > 0.03 and (p.op_margin_trend or 0) > 0.03
    strong_margin = (p.gross_margin_trend or 0) > 0.05 and (p.op_margin_trend or 0) > 0.05
    if g <= 0:
        return "🔻 CONTRACTING"
    # The Serenity sweet spot: volume ramp flipping the economics.
    if accel > 0.03 and margin_turn:
        return "🚀 EARLY RAMP (accelerating + margins turning)"
    if strong_margin and g > 0.20:
        return "🚀 EARLY RAMP (margin inflection)"
    if accel > 0.03:
        return "📈 ACCELERATING"
    if g > 0.30 and (p.op_margin_now or -1) > 0:
        return "💪 SCALING (high growth, profitable)"
    if g > 0.20:
        return "🟢 GROWING (steady)"
    if accel < -0.03:
        return "🟠 DECELERATING"
    return "⚪ MATURING"


def text_report(ticker: str) -> str:
    p = analyze_growth(ticker)
    out = ["=" * 80, f"SERENITY GROWTH ANALYSIS — {ticker.upper()} (ramp-inflection lens)", "=" * 80]
    if not p.ok:
        return "\n".join(out + [f"[growth] {p.error}"])
    out.append(f"  GROWTH SCORE : {p.growth_score:.1f}/100      stage: {p.ramp_stage}")
    out.append("  sub-scores (0-1):")
    labels = {"acceleration": "revenue acceleration", "margin_inflection": "margin inflection",
              "revenue_growth": "revenue growth (YoY)", "reinvestment": "reinvestment (R&D)",
              "growth_valuation": "growth-adj. valuation"}
    for k, lab in labels.items():
        bar = "█" * int(round(p.subscores.get(k, 0) * 20))
        out.append(f"     {lab:<24} {p.subscores.get(k,0):.2f}  {bar}")
    out.append("  signals: " + "; ".join(p.notes))
    if p.peg is not None or p.ev_sales is not None:
        out.append(f"  valuation: EV/Sales {p.ev_sales}  PEG {p.peg}")
    out.append("-" * 80)
    out.append("Serenity reads the INFLECTION (ramp + margin turn), not just trailing growth.")
    out.append("Confirm against the chokepoint moat (`serenity validate`). Not financial advice.")
    out.append("=" * 80)
    return "\n".join(out)


def pool_growth_table() -> str:
    """Growth score for every name in the curated chokepoint pool — the structural
    moat (chokepoint) × the ramp trajectory (growth) is the full Serenity thesis."""
    from serenity_chokepoint.chokepoint_data import get_universe

    names = [n for n in get_universe() if n.market_cap_b > 0]
    out = ["=" * 80, "CHOKEPOINT POOL — GROWTH / RAMP TABLE (live)", "=" * 80,
           f"{'TICKER':<7}{'GROWTH':>7}  STAGE"]
    out.append("-" * 80)
    rows = []
    for n in names:
        p = analyze_growth(n.ticker)
        if p.ok:
            rows.append((p.growth_score, n.ticker, p.ramp_stage))
        else:
            rows.append((-1, n.ticker, f"(no data: {p.error})"))
    for score, tkr, stage in sorted(rows, reverse=True):
        s = f"{score:.0f}" if score >= 0 else "  ?"
        out.append(f"{tkr:<7}{s:>7}  {stage}")
    out.append("-" * 80)
    out.append("High growth-score + high chokepoint-score = the ideal Serenity setup.")
    out.append("=" * 80)
    return "\n".join(out)
