"""LangGraph Multi-Agent Orchestration Workflow.

Implements Section 18 of the architecture specification:
- Strongly typed ResearchState (TypedDict)
- Parallel execution of SEC Agent, Market Agent, and Research Agent
- Deterministic Quant calculations
- Categorized Risk synthesis
- Mandatory Critic verification with bounded retry loop
- Report compilation & Output Guardrail enforcement
- Granular telemetry and latency recording for LangSmith and MySQL audit tables
"""

from __future__ import annotations

import logging
import operator
import time
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, START, END

from app.config import get_settings
from app.guardrails.input import InputGuardrail
from app.guardrails.output import OutputGuardrail
from app.agents.orchestrator import OrchestratorAgent
from app.agents.sec import SECAgent
from app.agents.market import MarketAgent
from app.agents.research import ResearchAgent
from app.agents.quant import QuantAgent
from app.agents.risk import RiskAgent
from app.agents.critic import CriticAgent
from app.agents.report import ReportAgent

logger = logging.getLogger("investment_swarm.graph")


class ResearchState(TypedDict):
    """Strongly typed state schema flowing through the LangGraph swarm."""

    # Session & Query Context
    session_id: str
    query: str
    ticker: str
    company_name: str
    period: str

    # Guardrail Results
    input_guardrail_result: Dict[str, Any]
    output_guardrail_result: Dict[str, Any]

    # Data Collected
    sec_data: Dict[str, Any]
    market_data: Dict[str, Any]
    research_data: List[Dict[str, Any]]

    # Derived Analytics
    quantitative_metrics: Dict[str, str]
    risks: List[Dict[str, Any]]

    # Evidence & Audit (Annotated with operator.add for parallel node fan-in)
    evidence: Annotated[List[Dict[str, Any]], operator.add]
    critic_result: Dict[str, Any]
    retry_count: int

    # Final Output
    final_report: str
    errors: List[str]
    agent_logs: Annotated[List[Dict[str, Any]], operator.add]


# ==============================================================================
# Graph Node Functions
# ==============================================================================

def input_guardrail_node(state: ResearchState) -> Dict[str, Any]:
    """Inspect and sanitize initial user research request."""
    t0 = time.time()
    query = state.get("query", "")
    result = InputGuardrail.validate_request(query)
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "InputGuardrail",
        "status": "SUCCESS" if result["allowed"] else "BLOCKED",
        "latency_ms": latency,
        "tool_calls": [{"tool": "validate_request", "action": result["action"]}],
        "error_message": result.get("reason") if not result["allowed"] else None,
    }

    return {
        "input_guardrail_result": result,
        "agent_logs": [log_entry],
    }


def orchestrator_node(state: ResearchState) -> Dict[str, Any]:
    """Decompose query, extract ticker symbol and research timeframe, and plan tasks."""
    t0 = time.time()
    query = state.get("query", "")
    plan = OrchestratorAgent.analyze_query(query)
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "OrchestratorAgent",
        "status": "SUCCESS",
        "latency_ms": latency,
        "tool_calls": [{"tool": "analyze_query", "ticker": plan["ticker"]}],
        "error_message": None,
    }

    return {
        "ticker": plan["ticker"],
        "company_name": plan["company_name"],
        "period": plan["period"],
        "agent_logs": [log_entry],
    }


def sec_agent_node(state: ResearchState) -> Dict[str, Any]:
    """Query SEC EDGAR MCP server for filings and GAAP numbers."""
    t0 = time.time()
    ticker = state["ticker"]
    company_name = state.get("company_name", "")
    result = SECAgent.run(ticker=ticker, company_name=company_name)
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "SECAgent",
        "status": result.get("status", "SUCCESS").upper(),
        "latency_ms": latency,
        "tool_calls": [{"tool": "get_company_facts", "cik": result.get("cik")}, {"tool": "get_10k"}],
        "error_message": None,
    }

    return {
        "sec_data": result,
        "evidence": result.get("evidence", []),
        "agent_logs": [log_entry],
    }


def market_agent_node(state: ResearchState) -> Dict[str, Any]:
    """Query Finance MCP server for prices and compute technical indicators."""
    t0 = time.time()
    ticker = state["ticker"]
    period = state.get("period", "12 months")
    result = MarketAgent.run(ticker=ticker, period=period)
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "MarketAgent",
        "status": result.get("status", "SUCCESS").upper(),
        "latency_ms": latency,
        "tool_calls": [{"tool": "get_stock_price"}, {"tool": "get_historical_prices"}],
        "error_message": None,
    }

    return {
        "market_data": result,
        "evidence": result.get("evidence", []),
        "agent_logs": [log_entry],
    }


def research_agent_node(state: ResearchState) -> Dict[str, Any]:
    """Query Research MCP (Tavily) for recent events, news, and earnings."""
    t0 = time.time()
    ticker = state["ticker"]
    company_name = state.get("company_name", "")
    retry_count = state.get("retry_count", 0)

    # Targeted query if retrying after Critic feedback
    focus = "earnings revenue product announcements" if retry_count > 0 else ""
    result = ResearchAgent.run(ticker=ticker, company_name=company_name, query_focus=focus)
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "ResearchAgent",
        "status": result.get("status", "SUCCESS").upper(),
        "latency_ms": latency,
        "tool_calls": [{"tool": "search_company_news", "articles_found": result.get("count")}],
        "error_message": None,
    }

    return {
        "research_data": result.get("articles", []),
        "evidence": result.get("evidence", []),
        "agent_logs": [log_entry],
    }


def quant_agent_node(state: ResearchState) -> Dict[str, Any]:
    """Run pure Python financial arithmetic without LLM guessing."""
    t0 = time.time()
    ticker = state["ticker"]
    sec_data = state.get("sec_data", {})
    market_data = state.get("market_data", {})
    result = QuantAgent.run(ticker=ticker, sec_data=sec_data, market_data=market_data)
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "QuantAgent",
        "status": "SUCCESS",
        "latency_ms": latency,
        "tool_calls": [{"tool": "calculate_financial_metrics"}],
        "error_message": None,
    }

    return {
        "quantitative_metrics": result.get("metrics", {}),
        "evidence": result.get("evidence", []),
        "agent_logs": [log_entry],
    }


def risk_agent_node(state: ResearchState) -> Dict[str, Any]:
    """Synthesize documented risks across 8 categories with evidence links."""
    t0 = time.time()
    ticker = state["ticker"]
    sec_data = state.get("sec_data", {})
    market_data = state.get("market_data", {})
    research_data = state.get("research_data", [])
    quant_metrics = state.get("quantitative_metrics", {})

    result = RiskAgent.run(
        ticker=ticker,
        sec_data=sec_data,
        market_data=market_data,
        research_data=research_data,
        quant_metrics=quant_metrics,
    )
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "RiskAgent",
        "status": "SUCCESS",
        "latency_ms": latency,
        "tool_calls": [{"tool": "categorize_risks", "risk_count": result.get("count")}],
        "error_message": None,
    }

    return {
        "risks": result.get("risks", []),
        "agent_logs": [log_entry],
    }


def critic_agent_node(state: ResearchState) -> Dict[str, Any]:
    """Audit source citations, numbers, dates, and hallucination boundary."""
    t0 = time.time()
    ticker = state["ticker"]
    sec_data = state.get("sec_data", {})
    market_data = state.get("market_data", {})
    research_data = state.get("research_data", [])
    quant_metrics = state.get("quantitative_metrics", {})
    evidence = state.get("evidence", [])
    retry_count = state.get("retry_count", 0)

    evaluation = CriticAgent.evaluate(
        ticker=ticker,
        sec_data=sec_data,
        market_data=market_data,
        research_data=research_data,
        quant_metrics=quant_metrics,
        evidence=evidence,
        retry_count=retry_count,
    )
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "CriticAgent",
        "status": evaluation.get("status"),
        "latency_ms": latency,
        "tool_calls": [{"tool": "audit_evidence", "verified": evaluation.get("verified_claims")}],
        "error_message": evaluation.get("feedback") if evaluation.get("status") != "PASS" else None,
    }

    return {
        "critic_result": evaluation,
        "agent_logs": [log_entry],
    }


def critic_routing_condition(state: ResearchState) -> str:
    """Route to targeted research retry if Critic reports missing evidence, or forward to ReportAgent."""
    critic_res = state.get("critic_result", {})
    status = critic_res.get("status", "PASS")
    retry_count = state.get("retry_count", 0)
    settings = get_settings()

    if status == "RETRY" and retry_count < settings.MAX_CRITIC_RETRIES:
        logger.info("Routing from Critic back to ResearchAgent for retry cycle %d", retry_count + 1)
        return "retry_research"

    return "generate_report"


def increment_retry_node(state: ResearchState) -> Dict[str, Any]:
    """Increment retry counter before re-invoking Research Agent."""
    return {"retry_count": state.get("retry_count", 0) + 1}


def report_agent_node(state: ResearchState) -> Dict[str, Any]:
    """Synthesize complete 10-section research dossier."""
    t0 = time.time()
    ticker = state["ticker"]
    company_name = state.get("company_name", ticker)
    period = state.get("period", "12 months")
    sec_data = state.get("sec_data", {})
    market_data = state.get("market_data", {})
    research_data = state.get("research_data", [])
    quant_metrics = state.get("quantitative_metrics", {})
    risks = state.get("risks", [])
    evidence = state.get("evidence", [])
    critic_result = state.get("critic_result", {})

    report = ReportAgent.run(
        ticker=ticker,
        company_name=company_name,
        period=period,
        sec_data=sec_data,
        market_data=market_data,
        research_data=research_data,
        quant_metrics=quant_metrics,
        risks=risks,
        evidence=evidence,
        critic_result=critic_result,
    )
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "ReportAgent",
        "status": "SUCCESS",
        "latency_ms": latency,
        "tool_calls": [{"tool": "compile_dossier", "sections": 10}],
        "error_message": None,
    }

    return {
        "final_report": report,
        "agent_logs": [log_entry],
    }


def output_guardrail_node(state: ResearchState) -> Dict[str, Any]:
    """Validate report for financial advice boundaries, citations, and PII before user presentation."""
    t0 = time.time()
    report = state.get("final_report", "")
    quant_metrics = state.get("quantitative_metrics", {})
    market_data = state.get("market_data", {})
    evidence = state.get("evidence", [])

    validation = OutputGuardrail.validate_report(
        report_markdown=report,
        quantitative_metrics=quant_metrics,
        market_data=market_data,
        evidence=evidence,
    )
    latency = int((time.time() - t0) * 1000)

    log_entry = {
        "agent_name": "OutputGuardrail",
        "status": validation.get("status"),
        "latency_ms": latency,
        "tool_calls": [{"tool": "audit_output", "passed": validation.get("advice_boundary_passed")}],
        "error_message": "; ".join(validation.get("issues", [])) if validation.get("issues") else None,
    }

    return {
        "final_report": validation.get("sanitized_report", report),
        "output_guardrail_result": validation,
        "agent_logs": [log_entry],
    }


# ==============================================================================
# Graph Assembly
# ==============================================================================

def create_research_graph():
    """Build the compiled LangGraph workflow for Investment Research Swarm."""
    workflow = StateGraph(ResearchState)

    # Register Nodes
    workflow.add_node("input_guardrail", input_guardrail_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("sec_agent", sec_agent_node)
    workflow.add_node("market_agent", market_agent_node)
    workflow.add_node("research_agent", research_agent_node)
    workflow.add_node("quant_agent", quant_agent_node)
    workflow.add_node("risk_agent", risk_agent_node)
    workflow.add_node("critic_agent", critic_agent_node)
    workflow.add_node("increment_retry", increment_retry_node)
    workflow.add_node("report_agent", report_agent_node)
    workflow.add_node("output_guardrail", output_guardrail_node)

    # Edge Connections
    workflow.add_edge(START, "input_guardrail")
    workflow.add_edge("input_guardrail", "orchestrator")

    # Fan-out to SEC, Market, and Research agents
    workflow.add_edge("orchestrator", "sec_agent")
    workflow.add_edge("orchestrator", "market_agent")
    workflow.add_edge("orchestrator", "research_agent")

    # Fan-in to Quant Agent
    workflow.add_edge("sec_agent", "quant_agent")
    workflow.add_edge("market_agent", "quant_agent")
    workflow.add_edge("research_agent", "quant_agent")

    # Sequential downstream pipeline
    workflow.add_edge("quant_agent", "risk_agent")
    workflow.add_edge("risk_agent", "critic_agent")

    # Conditional Branch on Critic status
    workflow.add_conditional_edges(
        "critic_agent",
        critic_routing_condition,
        {
            "retry_research": "increment_retry",
            "generate_report": "report_agent",
        },
    )

    workflow.add_edge("increment_retry", "research_agent")
    workflow.add_edge("report_agent", "output_guardrail")
    workflow.add_edge("output_guardrail", END)

    return workflow.compile()


# Singleton compiled graph instance
research_graph = create_research_graph()
