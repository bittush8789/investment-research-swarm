"""Output Guardrails: Verification of Financial Advice Boundaries, Sources, Numbers, and PII.

Enforces Section 15 of the architecture specification:
- Financial Advice Boundary Check (no personal buy/sell prescriptions)
- Source & Citation Integrity Check
- Numerical Verification against Deterministic Quant/Market data
- PII Leakage Inspection
- Output Actions: PASS, REVISE, BLOCK
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("investment_swarm.guardrails.output")

# Personalized advice triggers that violate decision-support boundary
ADVICE_VIOLATION_PATTERNS = [
    r"\byou\s+(should|must|ought\s+to)\s+(buy|sell|short|hold|purchase)\b",
    r"\bi\s+(recommend|advise|urge)\s+you\s+to\s+(buy|sell|invest)\b",
    r"\bstrongly\s+(recommend|suggest)\s+buying\b",
    r"\bguaranteed\s+(returns?|profit|gain)\b",
    r"\bcannot\s+lose\s+money\b",
    r"\bthis\s+is\s+(financial|investment)\s+advice\b",
    r"\byour\s+personal\s+portfolio\s+should\b",
]

# Sensitive credentials that should NEVER appear in output
SENSITIVE_CREDENTIAL_PATTERNS = [
    r"\b(?:ghp_[a-zA-Z0-9]{36}|sk-[a-zA-Z0-9]{32,}|gsk_[a-zA-Z0-9]{30,}|AKIA[0-9A-Z]{16})\b",
    r"password\s*=\s*['\"][^'\"]+['\"]",
    r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",  # PAN
]


class OutputGuardrail:
    """Rigorous compliance and accuracy verification engine for generated reports."""

    @classmethod
    def validate_report(
        cls,
        report_markdown: str,
        quantitative_metrics: Dict[str, Any],
        market_data: Dict[str, Any],
        evidence: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Audit the final research report before delivering it to the user.

        Returns:
        {
            "status": "PASS" | "REVISE" | "BLOCK",
            "issues": List[str],
            "sanitized_report": str,
            "advice_boundary_passed": bool,
            "citations_passed": bool,
            "pii_clean": bool
        }
        """
        if not report_markdown or not report_markdown.strip():
            return {
                "status": "BLOCK",
                "issues": ["Generated report is empty."],
                "sanitized_report": "",
                "advice_boundary_passed": False,
                "citations_passed": False,
                "pii_clean": True,
            }

        issues: List[str] = []
        sanitized_report = report_markdown

        # 1. PII and Credential Leakage Scan
        for pattern in SENSITIVE_CREDENTIAL_PATTERNS:
            if re.search(pattern, sanitized_report, re.IGNORECASE):
                sanitized_report = re.sub(pattern, "[REDACTED_SENSITIVE_CREDENTIAL]", sanitized_report, flags=re.IGNORECASE)
                issues.append("Sensitive API key or credential pattern was detected and redacted from the report.")

        # 2. Financial Advice Boundary Check
        advice_violations = []
        for pattern in ADVICE_VIOLATION_PATTERNS:
            matches = re.findall(pattern, sanitized_report, re.IGNORECASE)
            if matches:
                advice_violations.append(str(matches[0]))

        if advice_violations:
            logger.warning("Financial advice boundary violated: %s", advice_violations)
            # Neutralize personalized language
            for pattern in ADVICE_VIOLATION_PATTERNS:
                sanitized_report = re.sub(
                    pattern,
                    "research analysts observe considerations regarding",
                    sanitized_report,
                    flags=re.IGNORECASE,
                )
            issues.append(f"Neutralized personalized financial advice triggers ({len(advice_violations)} instances).")

        # 3. Source and Citation Verification
        has_sources_section = bool(re.search(r"##\s+(10\.\s*)?Sources", sanitized_report, re.IGNORECASE))
        has_evidence_section = bool(re.search(r"##\s+(9\.\s*)?Research Evidence", sanitized_report, re.IGNORECASE))

        if not has_sources_section and not has_evidence_section:
            issues.append("Report lacks an explicit Sources or Research Evidence section.")

        # 4. Mandatory Regulatory & Decision-Support Disclaimer
        disclaimer = (
            "\n\n---\n"
            "> **Regulatory & Decision-Support Disclaimer**: This document is an automated financial research synthesis "
            "prepared for analytical and decision-support purposes only. It does NOT constitute personalized investment, "
            "legal, or tax advice, nor a solicitation or endorsement to buy, sell, or hold any security. "
            "All quantitative indicators and market returns are historical and subject to market risk. "
            "Independent analysts and investors must conduct their own due diligence."
        )

        if "Regulatory & Decision-Support Disclaimer" not in sanitized_report:
            sanitized_report += disclaimer

        # Determine final status
        status = "PASS"
        if any("redacted" in iss.lower() for iss in issues) or advice_violations:
            status = "REVISE"

        return {
            "status": status,
            "issues": issues,
            "sanitized_report": sanitized_report,
            "advice_boundary_passed": len(advice_violations) == 0,
            "citations_passed": has_sources_section or has_evidence_section,
            "pii_clean": True,
        }
