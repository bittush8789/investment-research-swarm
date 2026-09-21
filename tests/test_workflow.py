"""End-to-end integration test for the LangGraph multi-agent swarm workflow.

Verifies Section 18 and Section 25:
- Full state progression through all nodes
- SEC, Market, and Research fan-out
- Quant deterministic calculations
- Critic validation and report generation
- Output Guardrail execution
"""

import pytest
from app.graph.workflow import research_graph, ResearchState


class TestSwarmWorkflow:
    """Integration test suite executing the compiled LangGraph."""

    def test_complete_swarm_execution_flow(self):
        query = "Analyze NVDA for the last 12 months."

        initial_state: ResearchState = {
            "session_id": "test-session-e2e",
            "query": query,
            "ticker": "",
            "company_name": "",
            "period": "12 months",
            "input_guardrail_result": {},
            "output_guardrail_result": {},
            "sec_data": {},
            "market_data": {},
            "research_data": [],
            "quantitative_metrics": {},
            "risks": [],
            "evidence": [],
            "critic_result": {},
            "retry_count": 0,
            "final_report": "",
            "errors": [],
            "agent_logs": [],
        }

        # Run compiled LangGraph workflow to completion
        final_state = research_graph.invoke(initial_state)

        # Assertions on final state integrity
        assert final_state["ticker"] == "NVDA"
        assert "NVIDIA" in final_state["company_name"]
        assert final_state["input_guardrail_result"]["allowed"] is True

        # Assert SEC & Market data extraction
        assert "financial_summary" in final_state["sec_data"]
        assert "current_price" in final_state["market_data"]

        # Assert Quant Agent calculations
        assert "Gross Margin" in final_state["quantitative_metrics"]
        assert "Return on Equity (ROE)" in final_state["quantitative_metrics"]

        # Assert Risk and Evidence
        assert len(final_state["risks"]) >= 5
        assert len(final_state["evidence"]) >= 3

        # Assert Critic audit
        assert final_state["critic_result"]["status"] in ["PASS", "RETRY"]
        assert final_state["critic_result"]["verified_claims"] > 0

        # Assert Final Report and Output Guardrail
        assert len(final_state["final_report"]) > 1000
        assert "## 1. Company Overview" in final_state["final_report"]
        assert "## 10. Sources" in final_state["final_report"]
        assert "Regulatory & Decision-Support Disclaimer" in final_state["final_report"]

        # Assert Agent Telemetry logs were captured for every node
        agent_names = [log["agent_name"] for log in final_state["agent_logs"]]
        assert "InputGuardrail" in agent_names
        assert "OrchestratorAgent" in agent_names
        assert "SECAgent" in agent_names
        assert "MarketAgent" in agent_names
        assert "ResearchAgent" in agent_names
        assert "QuantAgent" in agent_names
        assert "RiskAgent" in agent_names
        assert "CriticAgent" in agent_names
        assert "ReportAgent" in agent_names
        assert "OutputGuardrail" in agent_names
