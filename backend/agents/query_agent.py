from __future__ import annotations

import json
from typing import Any

import pandas as pd

from backend.config import settings
from backend.data_loader import TABLE_CATALOG
from backend.llm_client import call_llm, parse_json_response
from backend.query_executor import execute_query_plan

QUERY_AGENT_SYSTEM_TEMPLATE = """You are the Data Query Agent in a multi-agent anomaly detection system.
Today is {today}. You design pandas query plans (NOT SQL) for the Store Sales (Favorita Ecuador) dataset.

=== MANDATORY DATE CONSTRAINT ===
Analysis window:
  START: '{analysis_start}'
  END:   '{analysis_end}'
Always filter the date column within this window for the primary series.
Also include 4 weeks of baseline BEFORE the analysis start for comparison:
  baseline from '{baseline_start}' through day before '{analysis_start}'

Use filters with op "between" and value ["YYYY-MM-DD", "YYYY-MM-DD"] covering
'{baseline_start}' to '{analysis_end}' in a single filter when possible.

Available tables (pandas):
{table_catalog}

Return ONLY a JSON object:
{{
  "table": "sales",
  "filters": [{{"column": "date", "op": "between", "value": ["{baseline_start}", "{analysis_end}"]}}],
  "group_by": ["date"],
  "aggregations": [{{"column": "sales", "agg": "sum", "as": "total_sales"}}],
  "sort_by": [{{"column": "date", "ascending": true}}],
  "metric_col": "total_sales",
  "date_col": "date",
  "dimension_col": null,
  "explanation": "1-2 sentences",
  "context": "what normal means for this metric"
}}

Rules:
- table is usually "sales"
- group_by must include a time column: "date" (daily), "week" (weekly), or "month" (monthly)
- week/month/year are auto-derived from date — set date_col to the same name (e.g. date_col "week")
- metric_col must match an aggregation alias
- For by-state: group_by ["date", "state"]
- For product family: group_by ["date", "family"] or ["week", "family"] for weekly
- For transactions by city: table MUST be "transactions_enriched" (not "transactions"), group_by ["date", "city"], sum transactions
- If transactions table is unavailable, use sales table instead
- "cancellations" N/A — use sales drops or onpromotion patterns
- Filter ops: use "==", "!=", ">=", "<=", ">", "<", "between", "in", "contains" (NOT eq/ne/gte)
- No limit unless user asks top N
- Return ONLY valid JSON, no markdown."""


def build_system_prompt() -> str:
  start, end = settings.analysis_window()
  baseline = settings.baseline_start(start)
  return QUERY_AGENT_SYSTEM_TEMPLATE.format(
    today=settings.today.isoformat(),
    analysis_start=start,
    analysis_end=end,
    baseline_start=baseline,
    table_catalog=TABLE_CATALOG,
  )


def query_agent(question: str, feedback: str | None = None) -> dict[str, Any]:
  prompt = (
    f"Question: {question}\n\n"
    f"REMINDER: Analysis window {settings.analysis_window()[0]} to "
    f"{settings.analysis_window()[1]}. Include baseline from "
    f"{settings.baseline_start(settings.analysis_window()[0])}."
  )
  if feedback:
    prompt += f"\n\nPrevious attempt feedback: {feedback}"
  raw = call_llm(build_system_prompt(), prompt)
  return parse_json_response(raw)


def execute_plan(plan: dict[str, Any]) -> pd.DataFrame:
  return execute_query_plan(plan)
