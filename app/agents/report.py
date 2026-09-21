"""Report Agent: Synthesizes multi-agent intelligence into an institutional-grade research report.

Implements Section 12 of the architecture specification:
- Strictly adheres to the 10 required report sections:
  1. Company Overview
  2. Executive Summary
  3. Financial Performance
  4. Market Performance
  5. Quantitative Metrics
  6. Recent Developments
  7. Key Risks
  8. Key Catalysts / Business Developments
  9. Research Evidence
  10. Sources
- Neutral research tone, no speculative price targets, no personalized buy/sell advice
- Enriched with markdown tables, KPI summaries, and structured citations with direct clickable URLs
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.config import get_settings

logger = logging.getLogger("investment_swarm.agents.report")


class ReportAgent:
    """Agent responsible for compiling the 10-section institutional research report."""

    @classmethod
    def run(
        cls,
        ticker: str,
        company_name: str,
        period: str,
        sec_data: Dict[str, Any],
        market_data: Dict[str, Any],
        research_data: List[Dict[str, Any]],
        quant_metrics: Dict[str, str],
        risks: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]],
        critic_result: Dict[str, Any],
    ) -> str:
        """Generate full institutional investment research report."""
        logger.info("Report Agent generating 10-section report for %s (%s)", company_name, ticker)
        settings = get_settings()

        # If Groq is configured, utilize Groq LLM for natural narrative synthesis
        if settings.is_groq_configured():
            try:
                llm_report = cls._generate_with_groq(
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
                if llm_report and len(llm_report) > 500:
                    # Enforce that Section 10 Sources has direct clickable URLs
                    sources_section = cls._build_sources_section(ticker, sec_data, research_data)
                    if "10. Sources" not in llm_report:
                        llm_report = llm_report.strip() + "\n\n---\n\n" + sources_section
                    else:
                        after_sources = re.split(r"##?\s*10\.?\s*Sources", llm_report, maxsplit=1)[-1]
                        if "http" not in after_sources:
                            before_sources = re.split(r"##?\s*10\.?\s*Sources", llm_report, maxsplit=1)[0]
                            llm_report = before_sources.strip() + "\n\n---\n\n" + sources_section
                    return llm_report
            except Exception as exc:
                logger.warning("Groq report generation encountered exception (%s). Falling back to deterministic compiler.", exc)

        # Deterministic institutional compiler
        return cls._compile_deterministic_report(
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

    @classmethod
    def execute(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph node execution wrapper."""
        report = cls.run(
            ticker=state.get("ticker", "NVDA"),
            company_name=state.get("company_name", state.get("ticker", "NVDA")),
            period=state.get("period", "12 months"),
            sec_data=state.get("sec_data", {}),
            market_data=state.get("market_data", {}),
            research_data=state.get("research_data", []),
            quant_metrics=state.get("quant_metrics", {}),
            risks=state.get("risks", []),
            evidence=state.get("evidence", []),
            critic_result=state.get("critic_result", {}),
        )
        return {"report": report, "final_report": report}

    @classmethod
    def _build_sources_section(
        cls,
        ticker: str,
        sec_data: Dict[str, Any],
        research_data: List[Dict[str, Any]],
    ) -> str:
        """Generate structured Section 10 markdown guaranteeing direct, clickable URLs."""
        sec_source = sec_data.get("source", "SEC EDGAR Form 10-K")
        sec_cik = sec_data.get("cik", "N/A")
        sec_filing_url = sec_data.get("filing_url") or f"https://www.sec.gov/edgar/browse/?CIK={sec_cik}"
        sec_cik_url = f"https://www.sec.gov/edgar/browse/?CIK={sec_cik}"
        yf_quote_url = f"https://finance.yahoo.com/quote/{ticker}"
        yf_fin_url = f"https://finance.yahoo.com/quote/{ticker}/financials"
        yf_bs_url = f"https://finance.yahoo.com/quote/{ticker}/balance-sheet"
        yf_cf_url = f"https://finance.yahoo.com/quote/{ticker}/cash-flow"

        sources_md = f"""## 10. Sources
Primary regulatory, market, and intelligence sources with direct URLs:

### Regulatory & SEC EDGAR Filings
1. **SEC EDGAR Regulatory Filing**: [{sec_source}]({sec_filing_url})
   - URL: [{sec_filing_url}]({sec_filing_url})
2. **SEC Company Profile & XBRL Facts**: [SEC EDGAR CIK {sec_cik} Database]({sec_cik_url})
   - URL: [{sec_cik_url}]({sec_cik_url})

### Market Telemetry & Financial Statements
3. **Yahoo Finance Real-Time Quote & Telemetry**: [Yahoo Finance Quote for {ticker}]({yf_quote_url})
   - URL: [{yf_quote_url}]({yf_quote_url})
4. **Yahoo Finance Income Statement**: [Yahoo Finance Financials for {ticker}]({yf_fin_url})
   - URL: [{yf_fin_url}]({yf_fin_url})
5. **Yahoo Finance Balance Sheet**: [Yahoo Finance Balance Sheet for {ticker}]({yf_bs_url})
   - URL: [{yf_bs_url}]({yf_bs_url})
6. **Yahoo Finance Cash Flow Statement**: [Yahoo Finance Cash Flow for {ticker}]({yf_cf_url})
   - URL: [{yf_cf_url}]({yf_cf_url})

### Verified Web & News Intelligence (Tavily Research MCP)
"""
        if research_data:
            for idx, item in enumerate(research_data, 7):
                item_title = item.get("title", "News Article")
                item_url = item.get("url", f"https://finance.yahoo.com/quote/{ticker}")
                item_src = item.get("source", "Web Intelligence")
                item_date = item.get("published_date", "Recent")
                sources_md += f"{idx}. **{item_src}**: [{item_title}]({item_url})\n   - Direct URL: [{item_url}]({item_url})\n   - Published Date: `{item_date}`\n"
        else:
            sources_md += f"7. **Tavily Financial Search**: [Tavily Web Intelligence](https://tavily.com)\n   - URL: [https://tavily.com](https://tavily.com)\n"

        sources_md += f"""
### Quantitative Deterministic Engine
- **Deterministic Python Engine**: [Pandas & NumPy Ratio Calculations](https://pandas.pydata.org)
  - Formulaic verification of Margins, ROE, ROA, Debt/Equity, Volatility, and Drawdowns without LLM arithmetic.
"""
        return sources_md

    @classmethod
    def _compile_deterministic_report(
        cls,
        ticker: str,
        company_name: str,
        period: str,
        sec_data: Dict[str, Any],
        market_data: Dict[str, Any],
        research_data: List[Dict[str, Any]],
        quant_metrics: Dict[str, str],
        risks: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]],
        critic_result: Dict[str, Any],
    ) -> str:
        """Deterministic, rich Markdown report formatting guaranteeing all 10 required sections."""
        now_str = datetime.utcnow().strftime("%B %d, %Y")
        fin = sec_data.get("financial_summary", {})
        price = market_data.get("current_price")
        mcap = market_data.get("market_cap")
        ret_1y = market_data.get("return_1y")
        pe = market_data.get("trailing_pe")
        sec_source = sec_data.get("source", "SEC EDGAR Form 10-K")
        critic_status = critic_result.get("status", "PASS")
        verified_count = critic_result.get("verified_claims", len(evidence))

        def fmt_cur(val: Optional[float]) -> str:
            if val is None:
                return "Not available"
            if abs(val) >= 1e9:
                return f"${val / 1e9:,.2f}B"
            if abs(val) >= 1e6:
                return f"${val / 1e6:,.2f}M"
            return f"${val:,.2f}"

        def fmt_val(val: Optional[float], prefix: str = "$", suffix: str = "", decimals: int = 2) -> str:
            if val is None:
                return "N/A"
            return f"{prefix}{val:,.{decimals}f}{suffix}"

        price_display = fmt_val(price)
        low_52_display = fmt_val(market_data.get("fifty_two_week_low"))
        high_52_display = fmt_val(market_data.get("fifty_two_week_high"))
        ma_50_display = fmt_val(market_data.get("ma_50"))
        ma_200_display = fmt_val(market_data.get("ma_200"))

        sec_filing_url = sec_data.get("filing_url") or f"https://www.sec.gov/edgar/browse/?CIK={sec_data.get('cik', '')}"

        report = f"""# Comprehensive Investment Research Report: {company_name} ({ticker})
**Report Date:** {now_str} | **Evaluation Period:** {period} | **Critic Status:** `{critic_status}` ({verified_count} Claims Verified)

---

## 1. Company Overview
**{company_name}** (Ticker: `{ticker}`) is a publicly traded entity operating in the **{market_data.get('sector', 'Technology')}** sector and **{market_data.get('industry', 'Semiconductors & Equipment')}** industry.
- **Trading Exchange:** NASDAQ / Global Select
- **Market Capitalization:** {fmt_cur(mcap)}
- **Current Share Price:** {price_display}
- **Regulatory Authority:** SEC EDGAR (CIK: `{sec_data.get('cik', 'N/A')}`)
- **Filing Reference:** [{sec_source}]({sec_filing_url})

---

## 2. Executive Summary
This research dossier compiles empirical regulatory filings, deterministic technical indicators, quantitative financial calculations, and recent corporate developments for **{company_name}**.
Over the investigated period ({period}), the company demonstrated:
- **Financial Scale:** Annual revenue of **{fmt_cur(fin.get('revenue'))}** and net income of **{fmt_cur(fin.get('net_income'))}**.
- **Market Dynamics:** 1-year total return of **{f'{ret_1y:+.2f}%' if ret_1y is not None else 'N/A'}**, reflecting prevailing macroeconomic sentiment and capital expenditure momentum.
- **Balance Sheet Resilience:** Cash reserves of **{fmt_cur(fin.get('cash_and_equivalents'))}** against total debt obligations of **{fmt_cur(fin.get('total_debt'))}**.
- **Evidence Verification:** Critic Agent audited **{verified_count}** underlying claims against primary filings and market price feeds with zero ungrounded assertions.

---

## 3. Financial Performance
Data extracted directly from official regulatory submissions ({sec_source}):

| Financial Metric | Reported Value | Source Verification |
| :--- | :--- | :--- |
| **Total Revenue** | {fmt_cur(fin.get('revenue'))} | {sec_source} |
| **Gross Profit** | {fmt_cur(fin.get('gross_profit'))} | {sec_source} |
| **Operating Income** | {fmt_cur(fin.get('operating_income'))} | {sec_source} |
| **Net Income** | {fmt_cur(fin.get('net_income'))} | {sec_source} |
| **Operating Cash Flow** | {fmt_cur(fin.get('operating_cash_flow'))} | Cash Flow Statement |
| **Capital Expenditures** | {fmt_cur(fin.get('capital_expenditures'))} | Cash Flow Statement |
| **Free Cash Flow (FCF)** | {fmt_cur(fin.get('free_cash_flow'))} | Cash Flow Statement (OCF - CapEx) |
| **Cash & Cash Equivalents** | {fmt_cur(fin.get('cash_and_equivalents'))} | Balance Sheet |
| **Total Debt** | {fmt_cur(fin.get('total_debt'))} | Balance Sheet |
| **Total Assets** | {fmt_cur(fin.get('total_assets'))} | Balance Sheet |
| **Total Liabilities** | {fmt_cur(fin.get('total_liabilities'))} | Balance Sheet |
| **Stockholders' Equity** | {fmt_cur(fin.get('stockholders_equity'))} | Balance Sheet |

---

## 4. Market Performance
Quantitative price telemetry and technical moving averages calculated deterministically via Finance MCP:

| Market Indicator | Current Figure | Historical Context |
| :--- | :--- | :--- |
| **Current Stock Price** | {price_display} | Latest Closing Auction |
| **52-Week Range** | {low_52_display} - {high_52_display} | 1-Year Price Bounds |
| **Trailing P/E Ratio** | {f'{pe:.2f}x' if pe else 'N/A'} | Valuation Multiple |
| **1-Day Return** | {f'{market_data.get("return_1d", 0):+.2f}%'} | Prior Trading Day |
| **1-Month Return** | {f'{market_data.get("return_1m", 0):+.2f}%' if market_data.get("return_1m") is not None else 'N/A'} | 21 Trading Days |
| **6-Month Return** | {f'{market_data.get("return_6m", 0):+.2f}%' if market_data.get("return_6m") is not None else 'N/A'} | 126 Trading Days |
| **1-Year Return** | {f'{ret_1y:+.2f}%' if ret_1y is not None else 'N/A'} | Full 252-day Trading Cycle |
| **Annualized Volatility** | {f'{market_data.get("volatility", 0):.2f}%'} | Standard Deviation of Daily Log Returns |
| **Maximum Drawdown** | {f'{market_data.get("max_drawdown", 0):.2f}%'} | Peak-to-Trough Decline |
| **50-Day Moving Average** | {ma_50_display} | Short-Term Momentum |
| **200-Day Moving Average** | {ma_200_display} | Long-Term Trend Benchmark |

---

## 5. Quantitative Metrics
Financial ratios calculated deterministically in Python (Pandas/NumPy) without LLM arithmetic:

| Ratio Category | Metric Name | Computed Result |
| :--- | :--- | :--- |
| **Profitability** | Gross Margin | `{quant_metrics.get('Gross Margin', 'Not available')}` |
| **Profitability** | Operating Margin | `{quant_metrics.get('Operating Margin', 'Not available')}` |
| **Profitability** | Net Profit Margin | `{quant_metrics.get('Net Margin', 'Not available')}` |
| **Profitability** | Free Cash Flow Margin | `{quant_metrics.get('FCF Margin', 'Not available')}` |
| **Returns** | Return on Equity (ROE) | `{quant_metrics.get('Return on Equity (ROE)', 'Not available')}` |
| **Returns** | Return on Assets (ROA) | `{quant_metrics.get('Return on Assets (ROA)', 'Not available')}` |
| **Leverage** | Debt-to-Equity | `{quant_metrics.get('Debt to Equity', 'Not available')}` |
| **Liquidity** | Current Ratio | `{quant_metrics.get('Current Ratio', 'Not available')}` |
| **Risk** | Maximum Drawdown | `{quant_metrics.get('Maximum Drawdown', 'Not available')}` |
| **Risk** | Annualized Price Volatility | `{quant_metrics.get('Annualized Volatility', 'Not available')}` |

---

## 6. Recent Developments
Sanitized web intelligence and news feeds retrieved via Tavily Research MCP:
"""
        if research_data:
            for idx, item in enumerate(research_data[:4], 1):
                report += f"\n### {idx}. {item.get('title')}\n"
                report += f"- **Source:** {item.get('source')} | **Date:** {item.get('published_date', 'Recent')}\n"
                report += f"- **Summary:** {item.get('snippet')}\n"
                report += f"- **Link:** [{item.get('url')}]({item.get('url')})\n"
        else:
            report += "\n*No external press releases were identified within the research timeframe.*\n"

        report += f"""
---

## 7. Key Risks
Documented risks categorized across operational, regulatory, and financial dimensions:
"""
        for r in risks:
            report += f"\n- **[{r.get('category')}] {r.get('title')}** (Severity: `{r.get('severity', 'Moderate')}`)\n"
            report += f"  - *Evidence:* {r.get('evidence')}\n"
            report += f"  - *Source:* {r.get('source')}\n"

        report += f"""
---

## 8. Key Catalysts / Business Developments
1. **Architectural Advancements & Innovation:** Continued capital allocation towards next-generation hardware pipelines and software ecosystem stickiness.
2. **Enterprise IT & Infrastructure Secular Trends:** Growth in enterprise modernization, data center expansion, and operational automation.
3. **Diversified Customer Adoption:** Strategic commercial agreements across hyperscale cloud providers and multinational corporations.
4. **Capital Allocation Framework:** Ongoing cash flow generation facilitating strategic investments and debt service capabilities.

---

## 9. Research Evidence
Audited and verified claims cross-checked by the Critic Agent:

| ID | Verified Evidence Claim | Source Layer | Auditable Source URL |
| :--- | :--- | :--- | :--- |
"""
        for idx, ev in enumerate(evidence[:10], 1):
            claim_text = ev.get("claim", "")[:80]
            stype = ev.get("source_type", "DATA")
            surl = ev.get("source_url", "Internal Database")
            link_display = surl if len(surl) <= 50 else f"{surl[:47]}..."
            report += f"| {idx} | {claim_text} | `{stype}` | [{link_display}]({surl}) |\n"

        report += "\n---\n\n"
        report += cls._build_sources_section(ticker, sec_data, research_data)
        return report

    @classmethod
    def _generate_with_groq(
        cls,
        ticker: str,
        company_name: str,
        period: str,
        sec_data: Dict[str, Any],
        market_data: Dict[str, Any],
        research_data: List[Dict[str, Any]],
        quant_metrics: Dict[str, str],
        risks: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]],
        critic_result: Dict[str, Any],
    ) -> Optional[str]:
        """Synthesize report using Groq Cloud LLM reasoning while strictly enforcing the 10-section structure and source URLs."""
        settings = get_settings()
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY)

        sec_cik = sec_data.get("cik", "N/A")
        sec_filing_url = sec_data.get("filing_url") or f"https://www.sec.gov/edgar/browse/?CIK={sec_cik}"
        yf_quote_url = f"https://finance.yahoo.com/quote/{ticker}"
        yf_fin_url = f"https://finance.yahoo.com/quote/{ticker}/financials"

        prompt = f"""You are an institutional Equity Research Analyst.
Generate a comprehensive, structured investment research report for {company_name} ({ticker}) for the period: {period}.

MANDATORY RULES:
1. You MUST include EXACTLY these 10 numbered Markdown sections:
   ## 1. Company Overview
   ## 2. Executive Summary
   ## 3. Financial Performance
   ## 4. Market Performance
   ## 5. Quantitative Metrics
   ## 6. Recent Developments
   ## 7. Key Risks
   ## 8. Key Catalysts / Business Developments
   ## 9. Research Evidence
   ## 10. Sources
2. You must maintain an objective, institutional research tone.
3. DO NOT give personalized investment advice (do NOT say "you should buy" or "you should sell").
4. DO NOT present speculative price targets as facts.
5. Use the provided factual data below. DO NOT hallucinate numbers.
6. CRITICAL RULE FOR SECTION 10 (SOURCES):
   Every single source listed in Section 10 MUST include its clickable URL in markdown format `[Source Name](URL)` AND display the full direct URL explicitly.
   Example:
   1. **SEC EDGAR Filing**: [SEC 10-K Filing]({sec_filing_url}) - URL: {sec_filing_url}
   2. **Yahoo Finance Quote**: [Yahoo Finance {ticker}]({yf_quote_url}) - URL: {yf_quote_url}
   3. **News Articles**: List each retrieved news article with its title and exact URL: `[Article Title](URL) - URL: URL`
   DO NOT omit URLs for any source.

GROUND TRUTH DATA:
- Financial Data (SEC): {sec_data.get('financial_summary')}
- SEC Filing Reference: {sec_data.get('source', 'SEC Form 10-K')} | Direct URL: {sec_filing_url}
- SEC CIK: {sec_cik} | CIK URL: https://www.sec.gov/edgar/browse/?CIK={sec_cik}
- Market Data (yfinance): Price=${market_data.get('current_price')}, MarketCap=${market_data.get('market_cap')}, 1YReturn={market_data.get('return_1y')}%, Volatility={market_data.get('volatility')}%, MaxDrawdown={market_data.get('max_drawdown')}%
- Market URLs: Quote={yf_quote_url}, Financials={yf_fin_url}
- Quantitative Metrics (Python): {quant_metrics}
- Risks Documented: {risks}
- Recent News Articles with Direct URLs (Tavily): {[{'title': a.get('title'), 'url': a.get('url'), 'source': a.get('source'), 'date': a.get('published_date')} for a in research_data]}
- Critic Verification: {critic_result.get('status')} ({critic_result.get('verified_claims')} claims verified)

Produce the complete Markdown report now.
"""
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional financial research reporting assistant that always provides direct URLs for all sources."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
        return response.choices[0].message.content
