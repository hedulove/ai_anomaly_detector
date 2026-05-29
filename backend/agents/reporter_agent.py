from __future__ import annotations

import json

import pandas as pd

from backend.config import settings
from backend.llm_client import call_llm, parse_json_response

REPORTER_SYSTEM_TEMPLATE = """You are the Reporter Agent in a multi-agent anomaly detection system.
Today is {today}. Window: {analysis_start} to {analysis_end}.

Write a report in this EXACT JSON format:
{{
  "title": "<title>",
  "executive_summary": "<2-3 sentences>",
  "detection_methods": [
    {{"name": "Modified Z-Score", "description": "<specific>"}},
    {{"name": "IQR Fences", "description": "<specific>"}},
    {{"name": "Rolling Window Deviation", "description": "<specific>"}}
  ],
  "anomalies_found": [
    {{
      "date": "<date>",
      "metric_value": "<value>",
      "expected_range": "<range>",
      "severity": "high|medium|low",
      "description": "<what happened>",
      "flagged_by": "<methods>",
      "category": "Sudden Spike|Unexpected Drop|Erratic Behavior|Other"
    }}
  ],
  "root_causes": {{"internal": ["..."], "external": ["..."]}},
  "recommendation": "<actionable>"
}}
Return ONLY valid JSON, no markdown."""


def reporter_agent(
  question: str,
  anomaly_results: dict,
  root_cause_results: dict,
  revision_feedback: str | None = None,
) -> dict:
  start, end = settings.analysis_window()
  system = REPORTER_SYSTEM_TEMPLATE.format(
    today=settings.today.isoformat(),
    analysis_start=start,
    analysis_end=end,
  )
  method_info = anomaly_results.get("method_details", {})
  adf = anomaly_results.get("anomalies_df", pd.DataFrame())
  prompt = (
    f"Original question: {question}\n\n"
    f"Summary: {anomaly_results['summary']}\n\n"
    f"Method details: {json.dumps(method_info)}\n\n"
    f"Anomaly points:\n{adf.head(15).to_string(index=False)}\n\n"
    f"Root cause: {root_cause_results.get('hypothesis', 'N/A')}\n\n"
    f"External: {json.dumps(root_cause_results.get('external_causes', []), indent=2)}"
  )
  if revision_feedback:
    prompt += f"\n\nREVISION REQUEST:\n{revision_feedback}"
  raw = call_llm(system, prompt)
  return parse_json_response(raw)
