"""FastAPI Application Entry Point for Investment Research Swarm.

Implements Section 21 of the architecture specification:
- POST /api/research
- POST /api/chat
- GET /api/research/{session_id}
- GET /api/history
- GET /api/company/{ticker}
- GET /health
- Real-time Server-Sent Events (SSE) streaming
- Static frontend hosting
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.mysql import init_db, get_session_history, get_session_report, engine
from app.services.research import ResearchService
from app.mcp.client import mcp_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("investment_swarm.api")


# Pydantic Schemas
class ResearchRequest(BaseModel):
    query: str = Field(..., description="Natural language company research prompt e.g. 'Analyze NVDA for last 12 months'")


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="ID of the research session context")
    message: str = Field(..., description="Follow-up question or clarification request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycles."""
    logger.info("Initializing Investment Research Swarm Database...")
    try:
        init_db()
    except Exception as exc:
        logger.warning("Database schema initialization encountered issue (%s). Proceeding with runtime resilience.", exc)
    yield
    logger.info("Shutting down Investment Research Swarm.")


app = FastAPI(
    title="Investment Research Swarm API",
    description="ChatGPT-style multi-agent financial research and decision-support platform.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# API Endpoints
# ==============================================================================

@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Health status check verifying database and external API configuration."""
    settings = get_settings()
    db_ok = True
    try:
        with engine.connect() as conn:
            pass
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "groq_configured": settings.is_groq_configured(),
        "groq_model": settings.GROQ_MODEL,
        "tavily_configured": settings.is_tavily_configured(),
        "langsmith_tracing": settings.LANGSMITH_TRACING,
        "environment": settings.APP_ENV,
    }


@app.post("/api/research")
async def start_research(request: ResearchRequest) -> Dict[str, Any]:
    """Initiate multi-agent research swarm on a company or ticker."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be blank.")

    result = await ResearchService.start_research(request.query)
    return result


@app.get("/api/research/stream/{session_id}")
async def stream_research(session_id: str) -> StreamingResponse:
    """Stream real-time agent execution events, progress checklist, and final report via SSE."""
    return StreamingResponse(
        ResearchService.stream_events(session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat")
async def chat_followup(request: ChatRequest) -> Dict[str, Any]:
    """Submit a follow-up inquiry referencing an existing research session context."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be blank.")

    res = await ResearchService.answer_followup(request.session_id, request.message)
    return res


@app.get("/api/research/{session_id}")
def get_research_dossier(session_id: str) -> Dict[str, Any]:
    """Retrieve full completed research dossier, financial metrics, and audit records."""
    dossier = get_session_report(session_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Research session '{session_id}' not found.")
    return dossier


@app.get("/api/history")
def get_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve list of recent research sessions."""
    return get_session_history(limit=limit)


@app.get("/api/company/{ticker}")
def get_company_snapshot(ticker: str) -> Dict[str, Any]:
    """Retrieve rapid overview and market snapshot for a ticker symbol."""
    price_info = mcp_client.get_stock_price(ticker)
    company_info = mcp_client.get_company_info(ticker)
    return {
        "ticker": ticker.upper(),
        "price": price_info.get("price"),
        "pct_change_1d": price_info.get("pct_change_1d"),
        "market_cap": price_info.get("market_cap"),
        "name": company_info.get("name"),
        "sector": company_info.get("sector"),
        "industry": company_info.get("industry"),
        "pe_ratio": company_info.get("trailing_pe"),
    }


# Mount Static Frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
