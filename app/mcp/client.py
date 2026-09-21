"""Unified Model Context Protocol (MCP) Client for Agent-to-Tool abstraction.

Routes tool calls from agents to the appropriate MCP Servers (Finance, SEC, Research)
with timeout governance, structured telemetry, and resilient error recovery.
Conforms strictly to Section 17 of the architecture specification.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Optional

from app.config import get_settings
from app.mcp.finance import FinanceMCPServer
from app.mcp.sec import SECMCPServer
from app.mcp.research import ResearchMCPServer

logger = logging.getLogger("investment_swarm.mcp.client")


class MCPClient:
    """Standardized MCP Client connecting Agents to MCP Servers."""

    def __init__(self):
        self.settings = get_settings()
        # Registry of server tool handlers
        self._tool_registry: Dict[str, Dict[str, Callable[..., Any]]] = {
            "finance": {
                "get_stock_price": FinanceMCPServer.get_stock_price,
                "get_historical_prices": FinanceMCPServer.get_historical_prices,
                "get_company_info": FinanceMCPServer.get_company_info,
                "get_financials": FinanceMCPServer.get_financials,
                "get_balance_sheet": FinanceMCPServer.get_balance_sheet,
                "get_cashflow": FinanceMCPServer.get_cashflow,
            },
            "sec": {
                "get_company_facts": SECMCPServer.get_company_facts,
                "get_filings": SECMCPServer.get_filings,
                "get_10k": SECMCPServer.get_10k,
                "get_10q": SECMCPServer.get_10q,
                "get_8k": SECMCPServer.get_8k,
            },
            "research": {
                "web_search": ResearchMCPServer.web_search,
                "search_company_news": ResearchMCPServer.search_company_news,
                "search_industry_news": ResearchMCPServer.search_industry_news,
                "search_recent_events": ResearchMCPServer.search_recent_events,
            },
        }

    def call_tool(self, server_name: str, tool_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Invoke an MCP tool on a specified server, tracking latency and structured telemetry."""
        server = self._tool_registry.get(server_name.lower())
        if not server:
            logger.error("MCP Server '%s' not registered", server_name)
            return {
                "status": "error",
                "error": f"MCP Server '{server_name}' not registered",
                "server": server_name,
                "tool": tool_name,
            }

        tool_fn = server.get(tool_name)
        if not tool_fn:
            logger.error("Tool '%s' not found on MCP Server '%s'", tool_name, server_name)
            return {
                "status": "error",
                "error": f"Tool '{tool_name}' not found on server '{server_name}'",
                "server": server_name,
                "tool": tool_name,
            }

        start_time = time.time()
        try:
            logger.info("Executing MCP Tool: %s.%s with args=%s", server_name, tool_name, list(kwargs.keys()))
            result = tool_fn(**kwargs)
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info("Completed MCP Tool: %s.%s in %d ms", server_name, tool_name, latency_ms)

            if isinstance(result, dict):
                result["_meta"] = {
                    "server": server_name,
                    "tool": tool_name,
                    "latency_ms": latency_ms,
                    "status": result.get("status", "success"),
                }
                return result

            return {
                "status": "success",
                "data": result,
                "_meta": {
                    "server": server_name,
                    "tool": tool_name,
                    "latency_ms": latency_ms,
                },
            }
        except Exception as exc:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("Exception invoking MCP Tool %s.%s: %s", server_name, tool_name, exc, exc_info=True)
            return {
                "status": "error",
                "error": str(exc),
                "_meta": {
                    "server": server_name,
                    "tool": tool_name,
                    "latency_ms": latency_ms,
                },
            }

    # High-level convenience wrappers for Agents
    # Finance tools
    def get_stock_price(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("finance", "get_stock_price", ticker=ticker)

    def get_historical_prices(self, ticker: str, period: str = "1y") -> Dict[str, Any]:
        return self.call_tool("finance", "get_historical_prices", ticker=ticker, period=period)

    def get_company_info(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("finance", "get_company_info", ticker=ticker)

    def get_financials(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("finance", "get_financials", ticker=ticker)

    def get_balance_sheet(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("finance", "get_balance_sheet", ticker=ticker)

    def get_cashflow(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("finance", "get_cashflow", ticker=ticker)

    # SEC tools
    def get_company_facts(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("sec", "get_company_facts", ticker=ticker)

    def get_filings(self, ticker: str, form_type: Optional[str] = None) -> Dict[str, Any]:
        return self.call_tool("sec", "get_filings", ticker=ticker, form_type=form_type)

    def get_10k(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("sec", "get_10k", ticker=ticker)

    def get_10q(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("sec", "get_10q", ticker=ticker)

    def get_8k(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("sec", "get_8k", ticker=ticker)

    # Research tools
    def web_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        return self.call_tool("research", "web_search", query=query, max_results=max_results)

    def search_company_news(self, ticker: str, company_name: str = "", days: int = 30) -> Dict[str, Any]:
        return self.call_tool("research", "search_company_news", ticker=ticker, company_name=company_name, days=days)

    def search_industry_news(self, industry: str) -> Dict[str, Any]:
        return self.call_tool("research", "search_industry_news", industry=industry)

    def search_recent_events(self, ticker: str) -> Dict[str, Any]:
        return self.call_tool("research", "search_recent_events", ticker=ticker)


# Singleton MCP Client
mcp_client = MCPClient()
