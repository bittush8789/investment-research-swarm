"""Research Agent: Gathers recent news, earnings developments, and corporate actions via Tavily Research MCP.

Implements Section 8 of the architecture specification:
- Treats all web content as untrusted external data
- Sanitizes snippets via InputGuardrail to neutralize prompt injection directives
- Preserves title, url, source, published_date, and snippet
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.mcp.client import mcp_client
from app.guardrails.input import InputGuardrail

logger = logging.getLogger("investment_swarm.agents.research")


class ResearchAgent:
    """Agent specializing in live web research, earnings news, and market developments."""

    @classmethod
    def run(cls, ticker: str, company_name: str = "", query_focus: str = "") -> Dict[str, Any]:
        """Execute web intelligence queries and sanitize external content."""
        logger.info("Research Agent conducting intelligence gathering for %s (%s)", company_name, ticker)

        # 1. Query company news and earnings developments
        news_res = mcp_client.search_company_news(ticker=ticker, company_name=company_name, days=45)
        # 2. Query major corporate events or targeted focus if specified (for retries)
        if query_focus:
            events_res = mcp_client.web_search(query=f"{ticker} {query_focus}", max_results=4)
        else:
            events_res = mcp_client.search_recent_events(ticker=ticker)

        raw_articles = news_res.get("results", []) + events_res.get("results", [])

        # Deduplicate and sanitize articles
        seen_urls = set()
        sanitized_articles: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []

        for item in raw_articles:
            url = item.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Untrusted data sanitization
            clean_title = InputGuardrail.sanitize_external_content(item.get("title", ""))
            clean_snippet = InputGuardrail.sanitize_external_content(item.get("snippet", ""))

            article = {
                "title": clean_title,
                "url": url,
                "source": item.get("source", "Web Intelligence"),
                "published_date": item.get("published_date", ""),
                "snippet": clean_snippet,
            }
            sanitized_articles.append(article)

            # Record into evidence registry
            if clean_snippet:
                evidence.append({
                    "claim": f"Recent Development: {clean_title}",
                    "source_type": "TAVILY",
                    "source_url": url,
                    "verified": True,
                    "date": item.get("published_date", "Recent"),
                    "snippet": clean_snippet[:250],
                })

        return {
            "status": "success",
            "ticker": ticker.upper(),
            "count": len(sanitized_articles),
            "articles": sanitized_articles[:8],
            "evidence": evidence[:8],
        }
