"""Unit tests for specialized swarm agents.

Verifies:
- Quant Agent deterministic Python calculations and "Not available" handling
- Critic Agent evidence auditing and bounded retry conditions
- Orchestrator Agent ticker/timeframe extraction
- Report Agent 10-section compliance
"""

import pytest
from app.agents.quant import QuantAgent
from app.agents.critic import CriticAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.report import ReportAgent


class TestQuantAgent:
    """Test suite for deterministic arithmetic in QuantAgent."""

    def test_calculate_margins_accurately(self):
        sec_data = {
            "financial_summary": {
                "revenue": 100000000.0,
                "gross_profit": 75000000.0,
                "operating_income": 50000000.0,
                "net_income": 40000000.0,
                "free_cash_flow": 35000000.0,
                "stockholders_equity": 80000000.0,
                "total_assets": 120000000.0,
                "total_debt": 20000000.0,
            }
        }
        market_data = {
            "return_1y": 45.50,
            "volatility": 32.10,
            "max_drawdown": -18.20,
        }

        res = QuantAgent.run(ticker="TEST", sec_data=sec_data, market_data=market_data)
        metrics = res["metrics"]

        assert metrics["Gross Margin"] == "75.00%"
        assert metrics["Operating Margin"] == "50.00%"
        assert metrics["Net Margin"] == "40.00%"
        assert metrics["FCF Margin"] == "35.00%"
        assert metrics["Return on Equity (ROE)"] == "50.00%"
        assert metrics["Return on Assets (ROA)"] == "33.33%"
        assert metrics["Debt to Equity"] == "0.25x"
        assert metrics["1Y Total Return"] == "+45.50%"
        assert metrics["Annualized Volatility"] == "32.10%"
        assert metrics["Maximum Drawdown"] == "-18.20%"

    def test_missing_data_emits_not_available_never_fabricates(self):
        # Empty financial statements
        sec_data = {"financial_summary": {}}
        market_data = {}

        res = QuantAgent.run(ticker="EMPTY", sec_data=sec_data, market_data=market_data)
        metrics = res["metrics"]

        assert metrics["Gross Margin"] == "Not available"
        assert metrics["Net Margin"] == "Not available"
        assert metrics["Return on Equity (ROE)"] == "Not available"
        assert metrics["Debt to Equity"] == "Not available"
        assert metrics["1Y Total Return"] == "Not available"


class TestCriticAgent:
    """Test suite for CriticAgent evidence verification."""

    def test_critic_passes_verified_evidence(self):
        evidence = [
            {"claim": "NVDA revenue is $60B", "source_type": "SEC", "source_url": "https://sec.gov", "date": "2024-01-31"},
            {"claim": "NVDA price is $120", "source_type": "YFINANCE", "source_url": "https://yahoo.com", "date": "2024-05-01"},
            {"claim": "Gross Margin is 75%", "source_type": "QUANT", "source_url": "Python", "date": "TTM"},
            {"claim": "New GPU announced", "source_type": "TAVILY", "source_url": "https://reuters.com", "date": "2024-06-01"},
        ]
        market_data = {"current_price": 120.0, "fifty_two_week_high": 140.0, "fifty_two_week_low": 40.0}
        research_data = [{"title": "News 1"}]

        res = CriticAgent.evaluate(
            ticker="NVDA",
            sec_data={},
            market_data=market_data,
            research_data=research_data,
            quant_metrics={},
            evidence=evidence,
            retry_count=0,
        )
        assert res["status"] == "PASS"
        assert res["verified_claims"] >= 4
        assert res["rejected_claims"] == 0

    def test_critic_detects_numerical_anomaly_and_missing_sources(self):
        evidence = [
            {"claim": "Unsupported rumor", "source_type": None, "source_url": None, "date": None},
        ]
        # Current price ($250) exceeds 52w high ($140) by over 5%
        market_data = {"current_price": 250.0, "fifty_two_week_high": 140.0, "fifty_two_week_low": 40.0}

        res = CriticAgent.evaluate(
            ticker="NVDA",
            sec_data={},
            market_data=market_data,
            research_data=[],
            quant_metrics={},
            evidence=evidence,
            retry_count=0,
        )
        # Should issue RETRY since retry_count is 0
        assert res["status"] in ["RETRY", "FAIL"]
        assert res["rejected_claims"] > 0
        assert any("exceeds reported 52-week boundary" in iss for iss in res["issues"])


class TestOrchestratorAgent:
    """Test suite for query parsing."""

    def test_extract_ticker_and_period(self):
        plan = OrchestratorAgent.analyze_query("Please analyze NVIDIA (NVDA) for the last 12 months.")
        assert plan["ticker"] == "NVDA"
        assert "NVIDIA" in plan["company_name"]
        assert plan["period"] == "12 months"
        assert len(plan["tasks"]) == 7


class TestReportAgent:
    """Test suite for report structure compliance."""

    def test_report_contains_all_ten_required_sections(self):
        report = ReportAgent._compile_deterministic_report(
            ticker="NVDA",
            company_name="NVIDIA Corporation",
            period="12 months",
            sec_data={"financial_summary": {"revenue": 60922000000.0}},
            market_data={"current_price": 120.0, "market_cap": 3000000000000.0, "return_1y": 180.0},
            research_data=[{"title": "Blackwell architecture announcement", "source": "Reuters", "url": "https://reuters.com", "snippet": "New chips"}],
            quant_metrics={"Gross Margin": "75.00%", "ROE": "55.00%"},
            risks=[{"category": "Supply Chain Risk", "title": "TSMC packaging", "severity": "Moderate", "evidence": "Item 1A", "source": "SEC"}],
            evidence=[{"claim": "Revenue verified", "source_type": "SEC", "source_url": "https://sec.gov"}],
            critic_result={"status": "PASS", "verified_claims": 5},
        )

        required_sections = [
            "## 1. Company Overview",
            "## 2. Executive Summary",
            "## 3. Financial Performance",
            "## 4. Market Performance",
            "## 5. Quantitative Metrics",
            "## 6. Recent Developments",
            "## 7. Key Risks",
            "## 8. Key Catalysts / Business Developments",
            "## 9. Research Evidence",
            "## 10. Sources",
        ]

        for sec in required_sections:
            assert sec in report, f"Missing required section: {sec}"
