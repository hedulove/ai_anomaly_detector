from __future__ import annotations

import json

from backend.config import settings
from backend.llm_client import call_llm, parse_json_response

QA_SYSTEM_TEMPLATE = """You are the QA Reviewer Agent. Today is {today}.
Validate anomaly reports. Return ONLY JSON:
{{
  "approved": true/false,
  "score": <1-10>,
  "feedback": "<feedback if not approved>",
  "issues": ["..."],
  "improvements": ["..."]
}}
Approval threshold: score >= 6. Return ONLY valid JSON."""


def qa_reviewer(
  question: str,
  report: dict,
  anomaly_summary: str,
  raw_anomaly_data: str,
) -> dict:
  system = QA_SYSTEM_TEMPLATE.format(today=settings.today.isoformat())
  prompt = (
    f"Question: {question}\n\n"
    f"Report:\n{json.dumps(report, indent=2)}\n\n"
    f"Summary: {anomaly_summary}\n\n"
    f"Raw data:\n{raw_anomaly_data}"
  )
  raw = call_llm(system, prompt, fast=True)
  return parse_json_response(raw)
