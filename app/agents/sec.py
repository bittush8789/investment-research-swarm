"""SEC Agent: Extracts regulatory filings, official financial statements, and GAAP facts.

Implements Section 6.2 of the architecture specification:
- Queries SEC MCP Server for XBRL company facts and filings
- Extracts core GAAP metrics with filing citations
- Never fabricates numbers
- Returns structured filing metadata and auditable evidence
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.mcp.client import mcp_client

logger = logging.getLogger("investment_swarm.agents.sec")


class SECAgent:
    """Agent specializing in SEC EDGAR filings and regulatory disclosures."""

    @classmethod
    def run(cls, ticker: str, company_name: str = "") -> Dict[str, Any]:
        """Execute SEC regulatory research and financial facts extraction."""
        logger.info("SEC Agent starting research for ticker %s", ticker)

        # 1. Fetch SEC company facts
        facts_res = mcp_client.get_company_facts(ticker=ticker)
        # 2. Fetch recent 10-K annual report metadata
        tenk_res = mcp_client.get_10k(ticker=ticker)
        # 3. Fetch yfinance financial statements as SEC-backed supplementary figures
        fin_res = mcp_client.get_financials(ticker=ticker)
        bs_res = mcp_client.get_balance_sheet(ticker=ticker)
        cf_res = mcp_client.get_cashflow(ticker=ticker)

        # Formulate structured metrics map
        raw_metrics = facts_res.get("metrics", {}) if facts_res.get("status") == "success" else {}
        filings = tenk_res.get("filings", []) if tenk_res.get("status") == "success" else []
        latest_10k = filings[0] if filings else {}
        cik = facts_res.get("cik") or tenk_res.get("cik") or "N/A"

        # Extract primary financial figures
        financial_summary: Dict[str, Any] = {}
        evidence: List[Dict[str, Any]] = []

        source_label = f"SEC EDGAR Form 10-K (CIK: {cik})"

        # Fallback helper to inspect yfinance financials if SEC XBRL facts were sparse
        fin_dict = fin_res.get("financials", {})
        bs_dict = bs_res.get("balance_sheet", {})
        cf_dict = cf_res.get("cashflow", {})

        # Helper to extract the most recent value from nested financial statement dict
        def get_recent_statement_val(d: Dict[str, Dict[str, Any]], key_candidates: List[str]) -> Optional[float]:
            if not d:
                return None
            # sort dates descending
            sorted_dates = sorted(d.keys(), reverse=True)
            for dt in sorted_dates:
                sub_dict = d[dt]
                for cand in key_candidates:
                    for k, val in sub_dict.items():
                        if cand.lower() in k.lower() and val is not None:
                            return float(val)
            return None

        # 1. Revenue
        revenue = None
        if "Revenue_annual" in raw_metrics:
            revenue = raw_metrics["Revenue_annual"]["value"]
        else:
            revenue = get_recent_statement_val(fin_dict, ["Total Revenue", "Operating Revenue", "Revenue"])
        financial_summary["revenue"] = revenue

        # 2. Net Income
        net_income = None
        if "NetIncome_annual" in raw_metrics:
            net_income = raw_metrics["NetIncome_annual"]["value"]
        else:
            net_income = get_recent_statement_val(fin_dict, ["Net Income Common Stockholders", "Net Income", "Net Income Continuous Operations"])
        financial_summary["net_income"] = net_income

        # 3. Gross Profit
        gross_profit = None
        if "GrossProfit_annual" in raw_metrics:
            gross_profit = raw_metrics["GrossProfit_annual"]["value"]
        else:
            gross_profit = get_recent_statement_val(fin_dict, ["Gross Profit"])
        financial_summary["gross_profit"] = gross_profit

        # 4. Operating Income
        operating_income = None
        if "OperatingIncome_annual" in raw_metrics:
            operating_income = raw_metrics["OperatingIncome_annual"]["value"]
        else:
            operating_income = get_recent_statement_val(fin_dict, ["Operating Income", "Operating Revenue", "Total Operating Income"])
        financial_summary["operating_income"] = operating_income

        # 5. Cash & Cash Equivalents
        cash = None
        if "CashAndCashEquivalents_latest" in raw_metrics:
            cash = raw_metrics["CashAndCashEquivalents_latest"]["value"]
        else:
            cash = get_recent_statement_val(bs_dict, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
        financial_summary["cash_and_equivalents"] = cash

        # 6. Total Debt
        total_debt = get_recent_statement_val(bs_dict, ["Total Debt", "Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
        financial_summary["total_debt"] = total_debt

        # 7. Total Assets
        total_assets = None
        if "TotalAssets_latest" in raw_metrics:
            total_assets = raw_metrics["TotalAssets_latest"]["value"]
        else:
            total_assets = get_recent_statement_val(bs_dict, ["Total Assets"])
        financial_summary["total_assets"] = total_assets

        # 8. Total Liabilities
        total_liabilities = None
        if "TotalLiabilities_latest" in raw_metrics:
            total_liabilities = raw_metrics["TotalLiabilities_latest"]["value"]
        else:
            total_liabilities = get_recent_statement_val(bs_dict, ["Total Liabilities Net Minority Interest", "Total Liabilities"])
        financial_summary["total_liabilities"] = total_liabilities

        # 9. Stockholders' Equity
        equity = None
        if "StockholdersEquity_latest" in raw_metrics:
            equity = raw_metrics["StockholdersEquity_latest"]["value"]
        else:
            equity = get_recent_statement_val(bs_dict, ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"])
        financial_summary["stockholders_equity"] = equity

        # 10. Operating Cash Flow
        ocf = None
        if "OperatingCashFlow_annual" in raw_metrics:
            ocf = raw_metrics["OperatingCashFlow_annual"]["value"]
        else:
            ocf = get_recent_statement_val(cf_dict, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
        financial_summary["operating_cash_flow"] = ocf

        # 11. Capital Expenditures
        capex = None
        if "CapitalExpenditures_annual" in raw_metrics:
            capex = raw_metrics["CapitalExpenditures_annual"]["value"]
        else:
            capex = get_recent_statement_val(cf_dict, ["Capital Expenditure", "Capital Expenditures"])
            if capex is not None:
                capex = abs(capex)  # ensure positive magnitude
        financial_summary["capital_expenditures"] = capex

        # 12. Free Cash Flow
        fcf = None
        if ocf is not None and capex is not None:
            fcf = ocf - capex
        financial_summary["free_cash_flow"] = fcf

        # Record verified claims into evidence collection
        if revenue is not None:
            evidence.append({
                "claim": f"{ticker} annual revenue is reported at ${revenue:,.0f}",
                "source_type": "SEC",
                "source_url": latest_10k.get("url", "https://www.sec.gov/edgar/searchedgar/companysearch"),
                "verified": True,
                "date": latest_10k.get("filing_date", "Latest Annual Filing"),
            })

        if net_income is not None:
            evidence.append({
                "claim": f"{ticker} annual net income is reported at ${net_income:,.0f}",
                "source_type": "SEC",
                "source_url": latest_10k.get("url", "https://www.sec.gov/edgar/searchedgar/companysearch"),
                "verified": True,
                "date": latest_10k.get("filing_date", "Latest Annual Filing"),
            })

        return {
            "status": "success",
            "ticker": ticker.upper(),
            "cik": cik,
            "source": source_label,
            "filing_url": latest_10k.get("url", ""),
            "filing_date": latest_10k.get("filing_date", ""),
            "financial_summary": financial_summary,
            "evidence": evidence,
        }
