from __future__ import annotations

import pandas as pd

from backend.config import settings
from backend.llm_client import call_llm, parse_json_response

ROOT_CAUSE_SYSTEM_TEMPLATE = """You are the Root Cause Agent in a multi-agent anomaly detection system.
Today is {today}. Analysis window: {analysis_start} to {analysis_end}.
Dataset: Ecuador retail store sales (Favorita). Consider Ecuador holidays, oil prices,
paydays, earthquakes, and retail seasonality.

Return ONLY JSON:
{{
  "external_causes": [
    {{"date_range": "<dates>", "factor": "<event>", "explanation": "<impact>", "confidence": "high|medium|low"}}
  ],
  "hypothesis": "<1-2 sentence overall hypothesis>"
}}
Return ONLY valid JSON, no markdown."""


def root_cause_agent(
  question: str,
  anomaly_summary: str,
  query_plan: dict,
  metric_context: str,
  anomalies_df: pd.DataFrame,
) -> dict:
  start, end = settings.analysis_window()
  system = ROOT_CAUSE_SYSTEM_TEMPLATE.format(
    today=settings.today.isoformat(),
    analysis_start=start,
    analysis_end=end,
  )
  snapshot = anomalies_df.head(20).to_string(index=False)
  prompt = (
    f"Original question: {question}\n\n"
    f"Anomaly summary: {anomaly_summary}\n\n"
    f"Metric context: {metric_context}\n\n"
    f"Query plan:\n{query_plan}\n\n"
    f"Anomalous points (sample):\n{snapshot}"
  )
  raw = call_llm(system, prompt)
  return parse_json_response(raw)
