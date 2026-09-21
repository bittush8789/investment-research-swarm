"""Orchestrator Agent: Parses research requests, extracts target ticker and period, and builds the plan.

Implements Section 6.1 of the architecture specification.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from app.config import get_settings

logger = logging.getLogger("investment_swarm.agents.orchestrator")

# Fast lookup for common company names to ticker
COMPANY_TICKER_MAP = {
    "NVIDIA": "NVDA",
    "NVDA": "NVDA",
    "APPLE": "AAPL",
    "AAPL": "AAPL",
    "MICROSOFT": "MSFT",
    "MSFT": "MSFT",
    "TESLA": "TSLA",
    "TSLA": "TSLA",
    "AMAZON": "AMZN",
    "AMZN": "AMZN",
    "ALPHABET": "GOOGL",
    "GOOGLE": "GOOGL",
    "GOOGL": "GOOGL",
    "GOOG": "GOOGL",
    "META": "META",
    "FACEBOOK": "META",
    "BERKSHIRE": "BRK.B",
    "JPMORGAN": "JPM",
    "JPM": "JPM",
    "VISA": "V",
    "NETFLIX": "NFLX",
    "NFLX": "NFLX",
    "AMD": "AMD",
    "INTEL": "INTC",
    "INTC": "INTC",
}

TICKER_COMPANY_NAMES = {
    "NVDA": "NVIDIA Corporation",
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "TSLA": "Tesla, Inc.",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms, Inc.",
    "BRK.B": "Berkshire Hathaway Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "NFLX": "Netflix, Inc.",
    "AMD": "Advanced Micro Devices, Inc.",
    "INTC": "Intel Corporation",
}


class OrchestratorAgent:
    """Orchestrator responsible for query decomposition, entity resolution, and research planning."""

    @classmethod
    def analyze_query(cls, query: str) -> Dict[str, Any]:
        """Extract ticker, company name, period, and research tasks from query."""
        ticker, company_name = cls._extract_entity(query)
        period = cls._extract_period(query)

        tasks = [
            "1. SEC EDGAR filing retrieval (10-K, 10-Q) and financial facts extraction",
            "2. Market performance analysis via yfinance (prices, returns, volatility, moving averages)",
            "3. Recent business intelligence & news research via Tavily (earnings, products, macro)",
            "4. Deterministic Python quantitative calculations (margins, ratios, growth)",
            "5. Categorized evidence-backed risk analysis (regulatory, financial, supply chain)",
            "6. Cross-agent evidence validation & hallucination audit by Critic Agent",
            "7. Comprehensive institutional report generation by Report Agent",
        ]

        logger.info("Orchestrator planned tasks for %s (%s) over %s", company_name, ticker, period)

        return {
            "ticker": ticker,
            "company_name": company_name,
            "period": period,
            "tasks": tasks,
            "plan_summary": f"Orchestrated 7-step institutional research plan for {company_name} ({ticker}) for {period}.",
        }

    @classmethod
    def _extract_entity(cls, query: str) -> Tuple[str, str]:
        """Resolve ticker symbol and full corporate legal name."""
        upper_q = query.upper()

        # Check direct ticker match in parentheses or word boundary e.g. "(NVDA)" or "NVDA"
        for name, ticker in COMPANY_TICKER_MAP.items():
            if re.search(r"\b" + re.escape(name) + r"\b", upper_q):
                return ticker, TICKER_COMPANY_NAMES.get(ticker, f"{name.title()} Inc.")

        # Regex search for parenthesized ticker like (NVDA)
        paren_match = re.search(r"\(([A-Z]{1,5})\)", upper_q)
        if paren_match:
            t = paren_match.group(1)
            return t, TICKER_COMPANY_NAMES.get(t, f"{t} Corporation")

        # General standalone uppercase word resembling ticker (1 to 5 letters)
        candidates = re.findall(r"\b[A-Z]{2,5}\b", query)
        filtered = [c for c in candidates if c not in ["THE", "FOR", "LAST", "AND", "WITH", "RISK", "PERF", "SEC", "PE"]]
        if filtered:
            t = filtered[0]
            return t, TICKER_COMPANY_NAMES.get(t, f"{t} Corporation")

        # Default fallback
        return "NVDA", "NVIDIA Corporation"

    @classmethod
    def _extract_period(cls, query: str) -> str:
        """Extract research period (e.g. 12 months, 1 year, 3 years)."""
        lower_q = query.lower()
        if "12 month" in lower_q or "last year" in lower_q or "1 year" in lower_q or "12m" in lower_q:
            return "12 months"
        if "6 month" in lower_q or "6m" in lower_q:
            return "6 months"
        if "3 month" in lower_q or "quarter" in lower_q:
            return "3 months"
        if "2 year" in lower_q:
            return "2 years"
        if "5 year" in lower_q:
            return "5 years"
        return "12 months"
