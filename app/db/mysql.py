"""Database persistence layer using SQLAlchemy and MySQL with resilient fallbacks.

Implements tables specified in Section 19 of the architecture specification:
- users
- companies
- research_sessions
- financial_metrics
- market_data
- news_articles
- agent_runs
- sources
- research_reports
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

from app.config import get_settings

logger = logging.getLogger("investment_swarm.db")

Base = declarative_base()


class User(Base):
    """User table for audit trails and session ownership."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, default="default_analyst")
    email = Column(String(255), unique=True, nullable=False, default="analyst@swarmresearch.io")
    created_at = Column(DateTime, default=datetime.utcnow)

    sessions = relationship("ResearchSession", back_populates="user", cascade="all, delete-orphan")


class Company(Base):
    """Company metadata and SEC filing identifiers."""

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    cik = Column(String(20), nullable=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    exchange = Column(String(50), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResearchSession(Base):
    """Central session record for every research request."""

    __tablename__ = "research_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    ticker = Column(String(10), nullable=False, index=True)
    company_name = Column(String(255), nullable=True)
    query = Column(Text, nullable=False)
    period = Column(String(50), default="12 months")
    status = Column(String(50), default="INITIATED")  # INITIATED, RUNNING, COMPLETED, FAILED, BLOCKED
    risk_level = Column(String(20), default="low")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    financial_metrics = relationship("FinancialMetric", back_populates="session", cascade="all, delete-orphan")
    market_data = relationship("MarketData", back_populates="session", cascade="all, delete-orphan")
    news_articles = relationship("NewsArticle", back_populates="session", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="session", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="session", cascade="all, delete-orphan")
    reports = relationship("ResearchReport", back_populates="session", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")


class FinancialMetric(Base):
    """Deterministic financial metrics extracted from SEC filings or calculations."""

    __tablename__ = "financial_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("research_sessions.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    period = Column(String(50), nullable=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(String(100), nullable=False)
    unit = Column(String(50), default="USD")
    source_filing = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="financial_metrics")


class MarketData(Base):
    """Market performance figures retrieved from yfinance."""

    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("research_sessions.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    current_price = Column(Float, nullable=True)
    market_cap = Column(Float, nullable=True)
    pe_ratio = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    high_52w = Column(Float, nullable=True)
    low_52w = Column(Float, nullable=True)
    return_1y = Column(Float, nullable=True)
    volatility = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    ma_50 = Column(Float, nullable=True)
    ma_200 = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="market_data")


class NewsArticle(Base):
    """Untrusted web news articles retrieved via Tavily and sanitized."""

    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("research_sessions.id"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False)
    source = Column(String(255), nullable=True)
    published_date = Column(String(100), nullable=True)
    snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="news_articles")


class AgentRun(Base):
    """Granular execution log for each agent invocation in a swarm run."""

    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("research_sessions.id"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)  # SUCCESS, FAILED, RETRY
    latency_ms = Column(Integer, default=0)
    tool_calls = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="agent_runs")


class Source(Base):
    """Audited sources and evidence verification records."""

    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("research_sessions.id"), nullable=False, index=True)
    claim = Column(Text, nullable=False)
    source_type = Column(String(50), nullable=False)  # SEC, YFINANCE, TAVILY, QUANT
    source_url = Column(String(1000), nullable=True)
    verified = Column(Boolean, default=True)
    date = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="sources")


class ResearchReport(Base):
    """Final validated research report and Critic evaluation."""

    __tablename__ = "research_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("research_sessions.id"), nullable=False, unique=True, index=True)
    ticker = Column(String(10), nullable=False)
    company_name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=False)
    executive_summary = Column(Text, nullable=True)
    full_markdown_report = Column(Text, nullable=False)
    critic_status = Column(String(50), default="PASS")  # PASS, FAIL, RETRY
    critic_issues = Column(JSON, nullable=True)
    verified_claims = Column(Integer, default=0)
    rejected_claims = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="reports")


class ChatMessage(Base):
    """Persistent conversational memory store for multi-turn research inquiries."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("research_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="chat_messages")


# Engine Initialization with Fallback
def create_app_engine():
    """Create SQLAlchemy engine, falling back gracefully to SQLite if MySQL is unreachable."""
    settings = get_settings()
    engine = None

    # Attempt MySQL first
    if settings.MYSQL_URL and not settings.MYSQL_URL.startswith("sqlite"):
        try:
            logger.info("Attempting connection to MySQL: %s", settings.MYSQL_URL.split("@")[-1] if "@" in settings.MYSQL_URL else settings.MYSQL_URL)
            engine = create_engine(
                settings.MYSQL_URL,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_size=5,
                max_overflow=10,
                connect_args={"connect_timeout": 3},
            )
            # Test connection
            with engine.connect() as conn:
                pass
            logger.info("Successfully connected to MySQL database.")
            return engine
        except Exception as exc:
            logger.warning(
                "Could not connect to MySQL (%s). Falling back to local SQLite (%s) for uninterrupted operation.",
                exc,
                settings.FALLBACK_SQLITE_URL,
            )

    # Fallback to SQLite
    engine = create_engine(
        settings.FALLBACK_SQLITE_URL,
        connect_args={"check_same_thread": False},
    )
    logger.info("Using SQLite database at %s", settings.FALLBACK_SQLITE_URL)
    return engine


engine = create_app_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created successfully.")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Persistence helper methods
def save_research_results(
    session_id: str,
    ticker: str,
    company_name: str,
    query: str,
    period: str,
    sec_data: Dict[str, Any],
    market_data: Dict[str, Any],
    research_data: List[Dict[str, Any]],
    quantitative_metrics: Dict[str, Any],
    risks: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
    critic_result: Dict[str, Any],
    final_report: str,
    agent_logs: List[Dict[str, Any]],
) -> None:
    """Persist all multi-agent artifacts and final report into the database."""
    with get_db() as db:
        # Upsert Company
        company = db.query(Company).filter(Company.ticker == ticker).first()
        if not company:
            company = Company(
                ticker=ticker,
                name=company_name or ticker,
                sector=market_data.get("sector"),
                industry=market_data.get("industry"),
            )
            db.add(company)

        # Upsert ResearchSession
        session = db.query(ResearchSession).filter(ResearchSession.id == session_id).first()
        if not session:
            session = ResearchSession(
                id=session_id,
                ticker=ticker,
                company_name=company_name,
                query=query,
                period=period,
                status="COMPLETED",
            )
            db.add(session)
        else:
            session.status = "COMPLETED"
            session.company_name = company_name

        # Save Market Data
        if market_data:
            m_data = MarketData(
                session_id=session_id,
                ticker=ticker,
                current_price=market_data.get("current_price"),
                market_cap=market_data.get("market_cap"),
                pe_ratio=market_data.get("trailing_pe"),
                volume=market_data.get("volume"),
                high_52w=market_data.get("fifty_two_week_high"),
                low_52w=market_data.get("fifty_two_week_low"),
                return_1y=market_data.get("return_1y"),
                volatility=market_data.get("volatility"),
                max_drawdown=market_data.get("max_drawdown"),
                ma_50=market_data.get("ma_50"),
                ma_200=market_data.get("ma_200"),
            )
            db.add(m_data)

        # Save Financial Metrics
        if quantitative_metrics:
            for k, v in quantitative_metrics.items():
                db.add(
                    FinancialMetric(
                        session_id=session_id,
                        ticker=ticker,
                        period=period,
                        metric_name=k,
                        metric_value=str(v),
                        source_filing=sec_data.get("source", "SEC 10-K / Python Quant"),
                    )
                )

        # Save News Articles
        if research_data:
            for item in research_data:
                db.add(
                    NewsArticle(
                        session_id=session_id,
                        ticker=ticker,
                        title=item.get("title", "Untitled"),
                        url=item.get("url", ""),
                        source=item.get("source", "Web"),
                        published_date=item.get("published_date", ""),
                        snippet=item.get("snippet", "")[:1000],
                    )
                )

        # Save Sources / Evidence
        if evidence:
            for ev in evidence:
                db.add(
                    Source(
                        session_id=session_id,
                        claim=ev.get("claim", "")[:500],
                        source_type=ev.get("source_type", "UNKNOWN"),
                        source_url=ev.get("source_url", ""),
                        verified=ev.get("verified", True),
                        date=ev.get("date", ""),
                    )
                )

        # Save Agent Runs
        if agent_logs:
            for log in agent_logs:
                db.add(
                    AgentRun(
                        session_id=session_id,
                        agent_name=log.get("agent_name", "UnknownAgent"),
                        status=log.get("status", "SUCCESS"),
                        latency_ms=log.get("latency_ms", 0),
                        tool_calls=log.get("tool_calls", []),
                        error_message=log.get("error_message"),
                    )
                )

        # Save Final Report
        report_record = db.query(ResearchReport).filter(ResearchReport.session_id == session_id).first()
        if not report_record:
            report_record = ResearchReport(
                session_id=session_id,
                ticker=ticker,
                company_name=company_name,
                title=f"Investment Research Report: {company_name} ({ticker})",
                full_markdown_report=final_report,
                critic_status=critic_result.get("status", "PASS"),
                critic_issues=critic_result.get("issues", []),
                verified_claims=critic_result.get("verified_claims", 0),
                rejected_claims=critic_result.get("rejected_claims", 0),
            )
            db.add(report_record)
        else:
            report_record.full_markdown_report = final_report
            report_record.critic_status = critic_result.get("status", "PASS")
            report_record.critic_issues = critic_result.get("issues", [])
            report_record.verified_claims = critic_result.get("verified_claims", 0)
            report_record.rejected_claims = critic_result.get("rejected_claims", 0)

        # Initialize conversation memory for session if not present
        existing_msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
        if existing_msgs == 0:
            db.add(ChatMessage(session_id=session_id, role="user", content=query))
            db.add(ChatMessage(session_id=session_id, role="assistant", content=final_report))


def save_chat_message(session_id: str, role: str, content: str) -> None:
    """Persist a user question or assistant reply into session conversation memory."""
    with get_db() as db:
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(msg)


def get_chat_history(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve full chronological conversation memory for a research session."""
    with get_db() as db:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        return [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]


def get_session_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve list of past research sessions."""
    with get_db() as db:
        sessions = (
            db.query(ResearchSession)
            .order_by(ResearchSession.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "session_id": s.id,
                "ticker": s.ticker,
                "company_name": s.company_name,
                "query": s.query,
                "period": s.period,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ]


def get_session_report(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full research report, artifacts, and multi-turn chat memory by session ID."""
    with get_db() as db:
        session = db.query(ResearchSession).filter(ResearchSession.id == session_id).first()
        if not session:
            return None

        report = db.query(ResearchReport).filter(ResearchReport.session_id == session_id).first()
        metrics = db.query(FinancialMetric).filter(FinancialMetric.session_id == session_id).all()
        market = db.query(MarketData).filter(MarketData.session_id == session_id).first()
        sources = db.query(Source).filter(Source.session_id == session_id).all()
        agent_runs = db.query(AgentRun).filter(AgentRun.session_id == session_id).all()
        chat_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

        return {
            "session_id": session.id,
            "ticker": session.ticker,
            "company_name": session.company_name,
            "query": session.query,
            "period": session.period,
            "status": session.status,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "report": report.full_markdown_report if report else "",
            "critic": {
                "status": report.critic_status if report else "PASS",
                "issues": report.critic_issues if report else [],
                "verified_claims": report.verified_claims if report else 0,
                "rejected_claims": report.rejected_claims if report else 0,
            },
            "metrics": {m.metric_name: m.metric_value for m in metrics},
            "market_data": {
                "current_price": market.current_price if market else None,
                "market_cap": market.market_cap if market else None,
                "pe_ratio": market.pe_ratio if market else None,
                "return_1y": market.return_1y if market else None,
                "volatility": market.volatility if market else None,
                "max_drawdown": market.max_drawdown if market else None,
                "ma_50": market.ma_50 if market else None,
                "ma_200": market.ma_200 if market else None,
            } if market else {},
            "sources": [
                {
                    "claim": s.claim,
                    "source_type": s.source_type,
                    "source_url": s.source_url,
                    "verified": s.verified,
                    "date": s.date,
                }
                for s in sources
            ],
            "agent_runs": [
                {
                    "agent_name": a.agent_name,
                    "status": a.status,
                    "latency_ms": a.latency_ms,
                    "tool_calls": a.tool_calls,
                    "error_message": a.error_message,
                }
                for a in agent_runs
            ],
            "chat_messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in chat_messages
            ],
        }
