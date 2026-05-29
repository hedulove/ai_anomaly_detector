from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.config import ROOT

REPORTS_DIR = ROOT / "Reports"


def plan_to_display_sql(plan: dict[str, Any]) -> str:
  """Format pandas query plan as readable SQL-like text for the UI."""
  table = plan.get("table", "sales")
  lines = [
    f"-- Data Query Agent output (pandas plan → SQL-style view)",
    f"-- {plan.get('explanation', '')}",
    "",
  ]
  agg_parts = []
  for agg in plan.get("aggregations", []):
    col = agg.get("column", "*")
    fn = str(agg.get("agg", "sum")).upper()
    alias = agg.get("as", col)
    agg_parts.append(f"  {fn}({col}) AS {alias}")
  select_clause = ",\n".join(agg_parts) if agg_parts else "  *"
  group_by = plan.get("group_by") or []
  if group_by:
    select_clause = ",\n".join([f"  {c}" for c in group_by]) + ",\n" + select_clause

  lines.append(f"SELECT\n{select_clause}")
  lines.append(f"FROM {table}")
  for filt in plan.get("filters", []):
    col = filt.get("column")
    op = filt.get("op", "=")
    val = filt.get("value")
    if op == "between" and isinstance(val, list) and len(val) == 2:
      lines.append(f"WHERE {col} BETWEEN '{val[0]}' AND '{val[1]}'")
    else:
      lines.append(f"WHERE {col} {op} {json.dumps(val)}")
  if group_by:
    lines.append(f"GROUP BY {', '.join(group_by)}")
  for sort in plan.get("sort_by", []):
    if isinstance(sort, dict):
      col = sort.get("column")
      asc = "ASC" if sort.get("ascending", True) else "DESC"
      lines.append(f"ORDER BY {col} {asc}")
  if plan.get("limit"):
    lines.append(f"LIMIT {plan['limit']}")
  lines.extend([
    "",
    f"-- metric_col: {plan.get('metric_col')}",
    f"-- date_col: {plan.get('date_col')}",
    f"-- dimension_col: {plan.get('dimension_col')}",
    "",
    "-- Raw JSON plan:",
    json.dumps(plan, indent=2),
  ])
  return "\n".join(lines)


def save_investigation_report(
  question: str,
  report: dict[str, Any],
  qa_result: dict[str, Any],
  query_plan: dict[str, Any] | None = None,
  root_cause: dict[str, Any] | None = None,
  extra: dict[str, Any] | None = None,
) -> str:
  REPORTS_DIR.mkdir(parents=True, exist_ok=True)
  ts = datetime.now().strftime("%y%m%d-%H%M%S")
  filename = f"{ts}_anomaly_report.json"
  path = REPORTS_DIR / filename

  payload = {
    "saved_at": datetime.now().isoformat(),
    "question": question,
    "report": report,
    "qa_result": qa_result,
    "query_plan": query_plan,
    "query_display_sql": plan_to_display_sql(query_plan) if query_plan else None,
    "root_cause": root_cause,
    **(extra or {}),
  }
  path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
  return filename


def report_path(filename: str) -> Path:
  safe = Path(filename).name
  path = REPORTS_DIR / safe
  if not path.exists():
    raise FileNotFoundError(safe)
  return path
