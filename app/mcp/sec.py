"""SEC MCP Server providing access to official SEC EDGAR regulatory filings and company facts.

Implements tools specified in Section 16 of the architecture specification:
- get_company_facts
- get_filings
- get_10k
- get_10q
- get_8k
Respects SEC Fair Access Policy by sending declared SEC_USER_AGENT and caching CIK mappings.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.config import get_settings

logger = logging.getLogger("investment_swarm.mcp.sec")

SEC_BASE_URL = "https://data.sec.gov"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# In-memory cache for CIK mappings
_CIK_CACHE: Dict[str, str] = {}


class SECMCPServer:
    """SEC EDGAR MCP Server for regulatory submissions and financial facts."""

    @classmethod
    def _get_headers(cls) -> Dict[str, str]:
        """Generate compliance headers for SEC EDGAR API."""
        settings = get_settings()
        user_agent = settings.SEC_USER_AGENT or "InvestmentResearchSwarm analyst@swarmresearch.io"
        return {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }

    @classmethod
    def get_cik(cls, ticker: str) -> Optional[str]:
        """Resolve stock ticker symbol to 10-digit zero-padded SEC CIK."""
        clean_ticker = ticker.strip().upper()
        if clean_ticker in _CIK_CACHE:
            return _CIK_CACHE[clean_ticker]

        # Common company CIKs pre-loaded for instant resolution & offline safety
        known_ciks = {
            "NVDA": "0001045810",
            "AAPL": "0000320193",
            "MSFT": "0000789019",
            "AMZN": "0001018724",
            "GOOGL": "0001652044",
            "GOOG": "0001652044",
            "TSLA": "0001318605",
            "META": "0001326801",
            "BRK.B": "0001067983",
            "JPM": "0000019617",
            "V": "0001403161",
        }
        if clean_ticker in known_ciks:
            _CIK_CACHE[clean_ticker] = known_ciks[clean_ticker]
            return known_ciks[clean_ticker]

        try:
            settings = get_settings()
            headers = {"User-Agent": settings.SEC_USER_AGENT, "Host": "www.sec.gov"}
            with httpx.Client(timeout=10.0) as client:
                res = client.get(SEC_TICKERS_URL, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    for item in data.values():
                        t = item.get("ticker", "").upper()
                        cik_raw = str(item.get("cik_str", ""))
                        cik_10 = cik_raw.zfill(10)
                        _CIK_CACHE[t] = cik_10
                        if t == clean_ticker:
                            return cik_10
        except Exception as exc:
            logger.warning("Could not fetch SEC company tickers mapping: %s", exc)

        return None

    @classmethod
    def get_company_facts(cls, ticker: str) -> Dict[str, Any]:
        """Retrieve XBRL structured financial facts (revenue, net income, assets, etc.) from SEC EDGAR."""
        cik = cls.get_cik(ticker)
        if not cik:
            return {
                "status": "error",
                "ticker": ticker.upper(),
                "error": f"Could not find CIK for ticker '{ticker}' in SEC database",
            }

        url = f"{SEC_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
        try:
            headers = cls._get_headers()
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code == 200:
                    raw_data = res.json()
                    facts = raw_data.get("facts", {}).get("us-gaap", {})

                    # Extract key metric series
                    extracted_metrics = {}
                    metrics_to_extract = [
                        ("Revenues", "Revenue"),
                        ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenue"),
                        ("NetIncomeLoss", "NetIncome"),
                        ("GrossProfit", "GrossProfit"),
                        ("OperatingIncomeLoss", "OperatingIncome"),
                        ("CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalents"),
                        ("Assets", "TotalAssets"),
                        ("Liabilities", "TotalLiabilities"),
                        ("StockholdersEquity", "StockholdersEquity"),
                        ("NetCashProvidedByUsedInOperatingActivities", "OperatingCashFlow"),
                        ("PaymentsToAcquireProductiveAssets", "CapitalExpenditures"),
                    ]

                    for fact_key, friendly_name in metrics_to_extract:
                        if fact_key in facts:
                            units = facts[fact_key].get("units", {})
                            usd_units = units.get("USD", [])
                            if usd_units:
                                # Get latest 10-K / annual entries
                                annual_entries = [e for e in usd_units if e.get("form") in ["10-K", "10-K/A"]]
                                if annual_entries:
                                    latest_annual = sorted(annual_entries, key=lambda x: x.get("end", ""))[-1]
                                    extracted_metrics[f"{friendly_name}_annual"] = {
                                        "value": latest_annual.get("val"),
                                        "period_end": latest_annual.get("end"),
                                        "fy": latest_annual.get("fy"),
                                        "form": latest_annual.get("form"),
                                    }
                                # Also get latest entry overall (could be 10-Q)
                                latest_overall = sorted(usd_units, key=lambda x: x.get("end", ""))[-1]
                                extracted_metrics[f"{friendly_name}_latest"] = {
                                    "value": latest_overall.get("val"),
                                    "period_end": latest_overall.get("end"),
                                    "form": latest_overall.get("form"),
                                }

                    return {
                        "status": "success",
                        "ticker": ticker.upper(),
                        "cik": cik,
                        "entity_name": raw_data.get("entityName", ticker.upper()),
                        "metrics": extracted_metrics,
                        "source": f"SEC EDGAR XBRL (CIK: {cik})",
                    }
                else:
                    logger.warning("SEC EDGAR returned status %s for CIK %s", res.status_code, cik)
                    return {
                        "status": "error",
                        "ticker": ticker.upper(),
                        "error": f"SEC EDGAR returned status {res.status_code}",
                    }
        except Exception as exc:
            logger.error("Error retrieving SEC company facts for %s: %s", ticker, exc)
            return {"status": "error", "ticker": ticker.upper(), "error": str(exc)}

    @classmethod
    def get_filings(cls, ticker: str, form_type: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve recent SEC filing submissions (10-K, 10-Q, 8-K) and accession numbers."""
        cik = cls.get_cik(ticker)
        if not cik:
            return {
                "status": "error",
                "ticker": ticker.upper(),
                "error": f"Could not find CIK for ticker '{ticker}'",
            }

        url = f"{SEC_BASE_URL}/submissions/CIK{cik}.json"
        try:
            headers = cls._get_headers()
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    recent = data.get("filings", {}).get("recent", {})
                    forms = recent.get("form", [])
                    filing_dates = recent.get("filingDate", [])
                    report_dates = recent.get("reportDate", [])
                    accession_numbers = recent.get("accessionNumber", [])
                    primary_docs = recent.get("primaryDocument", [])
                    descriptions = recent.get("primaryDocDescription", [])

                    filings_list = []
                    for i in range(min(50, len(forms))):
                        form = forms[i]
                        if form_type and form != form_type:
                            continue
                        accession_clean = accession_numbers[i].replace("-", "")
                        doc_url = (
                            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_clean}/{primary_docs[i]}"
                            if i < len(primary_docs) and primary_docs[i]
                            else ""
                        )
                        filings_list.append({
                            "form": form,
                            "filing_date": filing_dates[i] if i < len(filing_dates) else None,
                            "report_date": report_dates[i] if i < len(report_dates) else None,
                            "accession_number": accession_numbers[i] if i < len(accession_numbers) else None,
                            "description": descriptions[i] if i < len(descriptions) else None,
                            "url": doc_url,
                        })

                    return {
                        "status": "success",
                        "ticker": ticker.upper(),
                        "cik": cik,
                        "company_name": data.get("name", ticker.upper()),
                        "sic": data.get("sic", ""),
                        "sic_description": data.get("sicDescription", ""),
                        "filings": filings_list[:15],
                    }
                else:
                    return {
                        "status": "error",
                        "ticker": ticker.upper(),
                        "error": f"SEC EDGAR returned status {res.status_code}",
                    }
        except Exception as exc:
            logger.error("Error retrieving SEC filings for %s: %s", ticker, exc)
            return {"status": "error", "ticker": ticker.upper(), "error": str(exc)}

    @classmethod
    def get_10k(cls, ticker: str) -> Dict[str, Any]:
        """Retrieve most recent annual report (Form 10-K) metadata and link."""
        return cls.get_filings(ticker, form_type="10-K")

    @classmethod
    def get_10q(cls, ticker: str) -> Dict[str, Any]:
        """Retrieve most recent quarterly report (Form 10-Q) metadata and link."""
        return cls.get_filings(ticker, form_type="10-Q")

    @classmethod
    def get_8k(cls, ticker: str) -> Dict[str, Any]:
        """Retrieve recent current event filings (Form 8-K) metadata and links."""
        return cls.get_filings(ticker, form_type="8-K")
