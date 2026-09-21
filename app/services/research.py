"""Research Service orchestrating LangGraph execution, real-time SSE streaming, and persistence.

Implements Section 21 and Section 22 of the architecture specification.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from app.graph.workflow import research_graph, ResearchState
from app.db.mysql import save_research_results, get_session_report, get_session_history, save_chat_message, get_chat_history
from app.guardrails.input import InputGuardrail
from app.config import get_settings

logger = logging.getLogger("investment_swarm.services.research")

# In-memory registry of active streaming queues keyed by session_id
_ACTIVE_STREAMS: Dict[str, asyncio.Queue] = {}


class ResearchService:
    """Service layer coordinating swarm execution and client event dispatching."""

    @classmethod
    async def start_research(cls, query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Initiate asynchronous swarm research execution and return session handle."""
        sid = session_id or str(uuid.uuid4())
        queue = asyncio.Queue()
        _ACTIVE_STREAMS[sid] = queue

        # Pre-screen input guardrails synchronously for immediate feedback
        screening = InputGuardrail.validate_request(query)
        if not screening["allowed"]:
            await queue.put({
                "event": "guardrail_blocked",
                "session_id": sid,
                "reason": screening["reason"],
                "risk_level": screening["risk_level"],
            })
            await queue.put({"event": "done", "session_id": sid})
            return {
                "session_id": sid,
                "status": "BLOCKED",
                "reason": screening["reason"],
            }

        # Launch background execution
        asyncio.create_task(cls._execute_swarm(sid, screening["sanitized_query"]))

        return {
            "session_id": sid,
            "status": "INITIATED",
            "sanitized_query": screening["sanitized_query"],
        }

    @classmethod
    async def _execute_swarm(cls, session_id: str, query: str) -> None:
        """Run the compiled LangGraph pipeline and emit SSE progress frames."""
        queue = _ACTIVE_STREAMS.get(session_id)
        if not queue:
            return

        initial_state: ResearchState = {
            "session_id": session_id,
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

        try:
            await queue.put({
                "event": "step",
                "agent": "InputGuardrail",
                "status": "Passed",
                "message": "Security screening passed. Prompt injection & PII clear.",
            })

            # Stream LangGraph execution node by node
            current_state: Dict[str, Any] = dict(initial_state)
            for output in research_graph.stream(initial_state):
                for node_name, node_state in output.items():
                    for k, v in node_state.items():
                        if k in ["agent_logs", "evidence"]:
                            current_state[k] = list(current_state.get(k, [])) + list(v)
                        else:
                            current_state[k] = v

                    agent_display_names = {
                        "orchestrator": ("Orchestrator Agent", f"Formulated research plan for {current_state.get('company_name', 'Company')} ({current_state.get('ticker')})"),
                        "sec_agent": ("SEC Agent", f"Retrieved regulatory filings & financial facts for {current_state.get('ticker')}"),
                        "market_agent": ("Market Agent", f"Computed returns, volatility & moving averages for {current_state.get('ticker')}"),
                        "research_agent": ("Research Agent", f"Gathered {len(current_state.get('research_data', []))} news articles via Tavily"),
                        "quant_agent": ("Quant Agent", "Completed deterministic ratio calculations in Python"),
                        "risk_agent": ("Risk Agent", f"Identified {len(current_state.get('risks', []))} evidence-backed risk factors"),
                        "critic_agent": ("Critic Agent", f"Audited evidence: Status `{current_state.get('critic_result', {}).get('status')}` ({current_state.get('critic_result', {}).get('verified_claims', 0)} verified)"),
                        "increment_retry": ("Critic Feedback Loop", "Missing critical evidence: Re-routing to Research Agent"),
                        "report_agent": ("Report Agent", "Synthesized 10-section institutional research dossier"),
                        "output_guardrail": ("Output Guardrail", "Audited financial advice boundaries and citation links"),
                    }

                    name, msg = agent_display_names.get(node_name, (node_name.title(), "Processing"))
                    await queue.put({
                        "event": "step",
                        "agent": name,
                        "status": "Completed",
                        "message": msg,
                        "node": node_name,
                        "ticker": current_state.get("ticker"),
                        "company_name": current_state.get("company_name"),
                    })

            # Save state artifacts to database
            save_research_results(
                session_id=session_id,
                ticker=current_state.get("ticker", "NVDA"),
                company_name=current_state.get("company_name", ""),
                query=query,
                period=current_state.get("period", "12 months"),
                sec_data=current_state.get("sec_data", {}),
                market_data=current_state.get("market_data", {}),
                research_data=current_state.get("research_data", []),
                quantitative_metrics=current_state.get("quantitative_metrics", {}),
                risks=current_state.get("risks", []),
                evidence=current_state.get("evidence", []),
                critic_result=current_state.get("critic_result", {}),
                final_report=current_state.get("final_report", ""),
                agent_logs=current_state.get("agent_logs", []),
            )

            # Emit final report and completion event
            await queue.put({
                "event": "report",
                "session_id": session_id,
                "ticker": current_state.get("ticker"),
                "company_name": current_state.get("company_name"),
                "report": current_state.get("final_report"),
                "market_data": current_state.get("market_data"),
                "metrics": current_state.get("quantitative_metrics"),
                "critic": current_state.get("critic_result"),
                "agent_runs": current_state.get("agent_logs"),
            })

            await queue.put({"event": "done", "session_id": session_id})

        except Exception as exc:
            logger.error("Swarm execution error for session %s: %s", session_id, exc, exc_info=True)
            await queue.put({
                "event": "error",
                "session_id": session_id,
                "error": str(exc),
            })
            await queue.put({"event": "done", "session_id": session_id})
        finally:
            pass

    @classmethod
    async def stream_events(cls, session_id: str) -> AsyncGenerator[str, None]:
        """Yield Server-Sent Events (SSE) formatted text chunks to client."""
        queue = _ACTIVE_STREAMS.get(session_id)
        if not queue:
            # If session already finished in DB, return stored report immediately
            stored = get_session_report(session_id)
            if stored:
                yield f"data: {json.dumps({'event': 'report', 'report': stored['report'], 'session_id': session_id})}\n\n"
                yield f"data: {json.dumps({'event': 'done', 'session_id': session_id})}\n\n"
                return
            yield f"data: {json.dumps({'event': 'error', 'error': 'Session not found'})}\n\n"
            return

        while True:
            try:
                # Wait for next event
                item = await asyncio.wait_for(queue.get(), timeout=60.0)
                yield f"data: {json.dumps(item)}\n\n"
                if item.get("event") == "done":
                    break
            except asyncio.TimeoutError:
                # Heartbeat to keep connection alive
                yield f": heartbeat\n\n"
            except Exception as exc:
                logger.warning("Stream exception for %s: %s", session_id, exc)
                break

        # Clean up queue
        _ACTIVE_STREAMS.pop(session_id, None)

    @classmethod
    async def answer_followup(cls, session_id: str, question: str) -> Dict[str, Any]:
        """Process follow-up questions referencing previous session context and multi-turn conversational memory."""
        screening = InputGuardrail.validate_request(question)
        if not screening["allowed"]:
            return {
                "answer": f"Security Notice: {screening['reason']}",
                "allowed": False,
            }

        stored = get_session_report(session_id)
        if not stored:
            return {"answer": "Previous research session context could not be located.", "allowed": True}

        # 1. Persist user question into conversation memory
        save_chat_message(session_id=session_id, role="user", content=question)

        # 2. Retrieve past conversation memory history
        history = get_chat_history(session_id=session_id)

        settings = get_settings()
        report_text = stored.get("report", "")
        ticker = stored.get("ticker", "")

        answer = None
        # If Groq is available, ask Groq with full multi-turn memory + report context
        if settings.is_groq_configured():
            try:
                from groq import Groq
                client = Groq(api_key=settings.GROQ_API_KEY)

                system_prompt = f"""You are an institutional equity research assistant with persistent conversational memory answering follow-up inquiries.
Target Company: {ticker}
Full Verified Research Report Context:
{report_text[:6000]}

Operational Guidelines:
1. Remember and reference previous turns in the conversation where relevant.
2. Answer concisely based strictly on the factual report data, quantitative calculations, and documented sources.
3. If mentioning or citing any sources, filings, or news articles, include their direct clickable Markdown URLs: [Source Name](URL).
4. Maintain neutral, objective research tone.
5. Do NOT give personalized buy/sell financial advice."""

                messages = [{"role": "system", "content": system_prompt}]

                # Include previous conversational memory (up to last 8 turns)
                recent_history = history[-8:]
                for msg in recent_history:
                    content = msg["content"]
                    # If this is the initial report, cap length for memory budget
                    if len(content) > 1500 and msg["role"] == "assistant":
                        content = content[:1500] + "... [dossier truncated in memory context]"
                    messages.append({"role": msg["role"], "content": content})

                resp = client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=800,
                )
                answer = resp.choices[0].message.content
            except Exception as exc:
                logger.warning("Groq follow-up answering failed: %s", exc)

        if not answer:
            # Fallback intelligent answer using memory and metrics
            answer = (
                f"Regarding your inquiry on {ticker}: Based on the verified research dossier and conversational history, "
                f"{ticker} reports Gross Margin of {stored.get('metrics', {}).get('Gross Margin', 'N/A')} and "
                f"Debt-to-Equity of {stored.get('metrics', {}).get('Debt to Equity', 'N/A')}. "
                f"Please review the detailed risk disclosures and SEC filing citations above."
            )

        # 3. Persist assistant reply into conversation memory
        save_chat_message(session_id=session_id, role="assistant", content=answer)

        return {
            "answer": answer,
            "allowed": True,
            "session_id": session_id,
            "memory_turns": len(history) + 1,
        }
