"""
Serenity Chokepoint agent.

A first-class analyst for the AI hedge-fund graph that scores each requested
ticker through the Serenity "Chokepoint Theory" lens (see ``src.serenity``):
reverse-engineer the AI compute supply chain and go long the physically
irreplaceable, supply-concentrated, hard-to-qualify, still-undiscovered
bottlenecks with asymmetric payoff.

For tickers already in the curated chokepoint universe we use the structural
chokepoint attributes directly. For any other ticker we fall back to live
fundamentals (small cap + high margin + high R&D + concentrated revenue as a
rough chokepoint proxy) so the agent still produces a signal on arbitrary
names. An LLM then writes the thesis narrative in Serenity's voice, exactly
like the other persona agents.
"""

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing_extensions import Literal
import json

from src.graph.state import AgentState, show_agent_reasoning
from src.serenity.chokepoint_data import by_ticker
from src.serenity.scoring import score_node, ChokepointScore
from src.tools.api import get_financial_metrics, get_market_cap, search_line_items
from src.utils.llm import call_llm
from src.utils.progress import progress


class SerenityChokepointSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def _proxy_score_from_fundamentals(ticker: str, end_date: str) -> tuple[dict, str]:
    """Build a rough chokepoint proxy for tickers outside the curated universe.

    Uses live fundamentals as stand-ins: small market cap (undiscovered), high
    gross margin (pricing power / scarce supply), heavy R&D (technical moat).
    Returns (analysis_dict, signal).
    """
    metrics = get_financial_metrics(ticker, end_date, period="ttm", limit=1)
    market_cap = get_market_cap(ticker, end_date)
    line_items = search_line_items(
        ticker,
        ["revenue", "gross_margin", "research_and_development", "operating_margin"],
        end_date, period="ttm", limit=1,
    )

    score = 0.0
    details: list[str] = []
    li = line_items[0] if line_items else None

    if market_cap and market_cap < 5e9:
        score += 30
        details.append(f"Small cap (~${market_cap/1e9:.1f}B) — information-asymmetry zone")
    elif market_cap and market_cap < 20e9:
        score += 12
        details.append(f"Mid cap (~${market_cap/1e9:.1f}B) — partly discovered")

    gm = getattr(li, "gross_margin", None) if li else None
    if gm and gm > 0.55:
        score += 25
        details.append(f"High gross margin {gm*100:.0f}% — scarce supply / pricing power")
    elif gm and gm > 0.40:
        score += 12
        details.append(f"Decent gross margin {gm*100:.0f}%")

    rev = getattr(li, "revenue", None) if li else None
    rnd = getattr(li, "research_and_development", None) if li else None
    if rev and rnd and rev > 0 and (rnd / rev) > 0.15:
        score += 25
        details.append(f"R&D intensity {100*rnd/rev:.0f}% — deep technical moat")
    elif rev and rnd and rev > 0 and (rnd / rev) > 0.08:
        score += 12
        details.append(f"R&D intensity {100*rnd/rev:.0f}%")

    if not details:
        details.append("Insufficient data — not identifiable as a chokepoint from fundamentals")

    signal = "bullish" if score >= 60 else "bearish" if score <= 25 else "neutral"
    return {
        "in_universe": False,
        "chokepoint_score": round(score, 1),
        "signal": signal,
        "details": "; ".join(details),
    }, signal


def _universe_analysis(cp: ChokepointScore) -> tuple[dict, str]:
    if cp.chokepoint_score >= 65 and cp.expected_value > 0.3:
        signal = "bullish"
    elif cp.chokepoint_score < 45 or cp.expected_value <= 0:
        signal = "bearish"
    else:
        signal = "neutral"
    return {
        "in_universe": True,
        "name": cp.name,
        "layer": cp.layer,
        "chokepoint_score": cp.chokepoint_score,
        "pillars": cp.pillars,
        "win_prob": cp.win_prob,
        "upside_mult": cp.upside_mult,
        "downside_loss": cp.downside_loss,
        "odds_ratio": cp.odds_ratio,
        "expected_value": cp.expected_value,
        "kelly_weight": cp.kelly_weight,
        "flags": cp.flags,
        "thesis": cp.thesis,
        "signal": signal,
    }, signal


def serenity_chokepoint_agent(state: AgentState):
    """Analyze stocks using Serenity's Chokepoint Theory and LLM reasoning."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    universe = by_ticker()
    analysis_data: dict[str, dict] = {}
    serenity_output: dict[str, dict] = {}

    for ticker in tickers:
        progress.update_status("serenity_chokepoint_agent", ticker, "Mapping supply-chain position")
        if ticker in universe:
            cp = score_node(universe[ticker])
            analysis, _ = _universe_analysis(cp)
        else:
            progress.update_status("serenity_chokepoint_agent", ticker, "No curated node — proxying from fundamentals")
            try:
                analysis, _ = _proxy_score_from_fundamentals(ticker, end_date)
            except Exception as e:  # network / data failure — stay neutral
                analysis = {"in_universe": False, "chokepoint_score": 0.0, "signal": "neutral", "details": f"data error: {e}"}

        analysis_data[ticker] = analysis

        progress.update_status("serenity_chokepoint_agent", ticker, "Writing chokepoint thesis")
        output = _generate_output(
            ticker=ticker,
            analysis=analysis,
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
        )
        serenity_output[ticker] = {"signal": output.signal, "confidence": output.confidence, "reasoning": output.reasoning}
        progress.update_status("serenity_chokepoint_agent", ticker, "Done")

    message = HumanMessage(content=json.dumps(serenity_output), name="serenity_chokepoint_agent")

    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(serenity_output, "Serenity Chokepoint Agent")

    state["data"]["analyst_signals"]["serenity_chokepoint_agent"] = serenity_output
    progress.update_status("serenity_chokepoint_agent", None, "Done")
    return {"messages": [message], "data": state["data"]}


def _generate_output(ticker: str, analysis: dict, model_name: str, model_provider: str) -> SerenityChokepointSignal:
    template = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are Serenity, an AI/semiconductor supply-chain "chokepoint" analyst. Your edge:

                1. Don't buy the obvious "tuna" (NVIDIA, TSMC). Hunt the "shiso leaf" — the small, irreplaceable
                   nodes the entire hyperscaler buildout MUST flow through (the Strait-of-Hormuz analogy).
                2. A real chokepoint is physically irreplaceable, supply-concentrated (top-3 > 70%), guarded by a
                   12-24 month qualification cycle, and still undiscovered (small cap, low institutional ownership).
                3. Demand elasticity (AI compute 50-100% CAGR) vastly outruns supply elasticity at the choke.
                4. Value venture-style on 2027+ volume ramp and M&A optionality, NOT trailing P/S.
                5. Asymmetry over certainty: go long high-odds bets (big upside multiple vs bounded downside),
                   size with deep-fractional Kelly, hold until volume ramp validates. DYOR; not 100% win rate.

                Be specific about WHICH supply-chain layer the company sits in and WHY it is (or is not) a choke.
                Reference the structural scores provided. Speak with conviction but acknowledge the key risk
                (dilution, tech-path CPO-vs-pluggable, liquidity).""",
            ),
            (
                "human",
                """Based on this chokepoint analysis, give a Serenity-style signal for {ticker}.

                Analysis:
                {analysis}

                Return JSON exactly:
                {{
                  "signal": "bullish/bearish/neutral",
                  "confidence": float (0-100),
                  "reasoning": "string"
                }}""",
            ),
        ]
    )

    prompt = template.invoke({"analysis": json.dumps(analysis, indent=2), "ticker": ticker})

    def default():
        return SerenityChokepointSignal(signal="neutral", confidence=0.0, reasoning="Error in analysis, defaulting to neutral")

    return call_llm(
        prompt=prompt,
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=SerenityChokepointSignal,
        agent_name="serenity_chokepoint_agent",
        default_factory=default,
    )
