"""Input Guardrails: AI Security, Prompt Injection Detection, PII Redaction, and Web Sanitization.

Enforces Section 13 and Section 14 of the architecture specification:
- Prompt Injection Detection
- Jailbreak Detection
- PII Detection & Redaction (PAN, Aadhaar, SSN, Credit Cards, API Keys)
- Financial Query Validation
- External Web Content Sanitization (Tavily prompt injection mitigation)
"""

from __future__ import annotations

import re
import html
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("investment_swarm.guardrails.input")

# Prompt injection signature patterns
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|commands)",
    r"disregard\s+(all\s+)?(previous|prior|above)",
    r"reveal\s+(the\s+)?(system\s+prompt|hidden\s+prompt|instructions|secret|api\s+key)",
    r"output\s+(the\s+)?(system\s+prompt|api\s+key|access\s+token)",
    r"what\s+(is|are)\s+your\s+(system\s+prompt|instructions|hidden\s+rules)",
    r"bypass\s+(the\s+)?(security|guardrails|safety|rules|filters)",
    r"you\s+are\s+now\s+(DAN|unrestricted|jailbroken|an\s+unfiltered\s+ai)",
    r"developer\s+mode\s+enabled",
    r"override\s+(all\s+)?safety\s+protocols",
    r"send\s+(api\s+key|keys|tokens|credentials)\s+to",
    r"base64\s+decode\s+and\s+execute",
]

# Sensitive PII regex patterns
PII_PATTERNS: List[Tuple[str, re.Pattern[str], str]] = [
    # Credit Card numbers (Luhn candidate 13-19 digits with separators)
    ("Credit Card", re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b"), "[REDACTED_CARD_NUMBER]"),
    # Generic API Keys / Tokens (hex or base64 high entropy)
    ("API Key / Token", re.compile(r"\b(?:ghp_[a-zA-Z0-9]{36}|sk-[a-zA-Z0-9]{32,}|gsk_[a-zA-Z0-9]{30,}|AKIA[0-9A-Z]{16})\b"), "[REDACTED_API_KEY]"),
    # Indian PAN Number (5 letters, 4 digits, 1 letter)
    ("PAN Number", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b", re.IGNORECASE), "[REDACTED_PAN]"),
    # Aadhaar Number (12 digits with optional spaces/dashes)
    ("Aadhaar Number", re.compile(r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b"), "[REDACTED_AADHAAR]"),
    # US SSN (3-2-4 format)
    ("Social Security Number", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    # Passwords in query (e.g. password=XYZ)
    ("Plaintext Password", re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE), "password=[REDACTED_PASSWORD]"),
]

# Common ticker or company indicators
FINANCIAL_INTENT_KEYWORDS = [
    "analyze", "research", "stock", "shares", "ticker", "financial", "earnings",
    "valuation", "balance sheet", "cash flow", "sec", "10-k", "10-q", "market cap",
    "pe ratio", "margin", "risk", "revenue", "nvda", "aapl", "msft", "tsla", "amzn",
    "googl", "meta", "nvidia", "apple", "microsoft", "tesla", "amazon", "google",
    "performance", "quarter", "fy", "metrics", "invest", "company"
]


class InputGuardrail:
    """Multi-layer input inspection and sanitization engine."""

    @classmethod
    def validate_request(cls, raw_query: str) -> Dict[str, Any]:
        """Run comprehensive security screening on user research query.

        Returns structured evaluation:
        {
            "allowed": bool,
            "risk_level": "low" | "medium" | "high",
            "action": "ALLOW" | "BLOCK" | "REDACT",
            "reason": str,
            "sanitized_query": str
        }
        """
        if not raw_query or not raw_query.strip():
            return {
                "allowed": False,
                "risk_level": "high",
                "action": "BLOCK",
                "reason": "Research query is empty.",
                "sanitized_query": "",
            }

        cleaned_text = raw_query.strip()

        # 1. Prompt Injection Detection
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, cleaned_text, re.IGNORECASE):
                logger.warning("Prompt injection detected matching pattern '%s': %s", pattern, cleaned_text[:100])
                return {
                    "allowed": False,
                    "risk_level": "high",
                    "action": "BLOCK",
                    "reason": "Security Alert: Prompt injection or system instruction bypass attempt detected.",
                    "sanitized_query": "",
                }

        # 2. PII Detection and Redaction
        pii_detected = []
        sanitized_query = cleaned_text
        for pii_name, pattern, placeholder in PII_PATTERNS:
            if pattern.search(sanitized_query):
                pii_detected.append(pii_name)
                sanitized_query = pattern.sub(placeholder, sanitized_query)

        # 3. Query Relevance / Financial Domain Validation
        lower_query = sanitized_query.lower()
        has_domain_term = any(kw in lower_query for kw in FINANCIAL_INTENT_KEYWORDS)

        # Check if query contains any uppercase ticker-like symbol (2-5 letters, excluding common English words)
        common_words = {
            "I", "A", "AN", "THE", "HOW", "DO", "AT", "TO", "IN", "ON", "OF", "FOR",
            "IS", "IT", "MY", "ME", "WE", "US", "HE", "SHE", "AND", "OR", "BUT", "SO",
            "IF", "BY", "WITH", "FROM", "AS", "BE", "WAS", "ARE", "THAT", "THIS", "CAN",
            "YOU", "WHAT", "WHEN", "WHERE", "WHY", "WHO", "WHICH", "WILL", "WOULD"
        }
        raw_uppercase_candidates = set(re.findall(r"\b[A-Z]{2,5}\b", raw_query))
        valid_ticker_candidates = raw_uppercase_candidates - common_words
        has_ticker_like = len(valid_ticker_candidates) > 0

        if not has_domain_term and not has_ticker_like:
            logger.info("Non-financial query received: %s", raw_query[:80])
            return {
                "allowed": False,
                "risk_level": "medium",
                "action": "BLOCK",
                "reason": "The query does not appear related to company financial research, stocks, or SEC filings. This platform is specialized for investment research and company decision-support.",
                "sanitized_query": sanitized_query,
            }

        action = "REDACT" if pii_detected else "ALLOW"
        risk_level = "medium" if pii_detected else "low"
        reason = f"PII detected and redacted: {', '.join(pii_detected)}" if pii_detected else "Valid financial research query."

        return {
            "allowed": True,
            "risk_level": risk_level,
            "action": action,
            "reason": reason,
            "sanitized_query": sanitized_query,
        }

    @classmethod
    def sanitize_external_content(cls, raw_content: str) -> str:
        """Sanitize untrusted external web/Tavily content to prevent indirect prompt injections (Section 14).

        - Unescapes HTML entities
        - Strips HTML/script/iframe tags
        - Neutralizes prompt injection commands inside external text
        - Truncates extreme length
        """
        if not raw_content:
            return ""

        # Unescape and strip HTML tags
        text = html.unescape(raw_content)
        text = re.sub(r"<(script|style|iframe|object|embed)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)

        # Neutralize injection triggers embedded in web pages
        for pattern in PROMPT_INJECTION_PATTERNS:
            text = re.sub(pattern, "[EXTERNAL_DIRECTIVE_NEUTRALIZED]", text, flags=re.IGNORECASE)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Cap length to avoid context blowout
        return text[:2000]
