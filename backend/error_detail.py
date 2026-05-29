from __future__ import annotations

import json
import traceback
from typing import Any


def build_error_detail(
  agent: str,
  error: Exception,
  *,
  question: str | None = None,
  query_plan: dict[str, Any] | None = None,
  extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
  detail: dict[str, Any] = {
    "agent": agent,
    "error_type": type(error).__name__,
    "message": str(error),
    "question": question,
    "query_plan": query_plan,
    "traceback": traceback.format_exc(),
  }
  if extra:
    detail.update(extra)
  return detail


def format_error_detail_text(detail: dict[str, Any]) -> str:
  lines = [
    "=== Agent Error Details ===",
    f"Agent: {detail.get('agent', 'unknown')}",
    f"Type: {detail.get('error_type', 'Error')}",
    f"Message: {detail.get('message', '')}",
  ]
  if detail.get("question"):
    lines.extend(["", f"Question: {detail['question']}"])
  if detail.get("query_plan"):
    lines.extend(["", "Query plan (JSON):", json.dumps(detail["query_plan"], indent=2)])
  if detail.get("traceback"):
    lines.extend(["", "Traceback:", detail["traceback"]])
  for key, val in detail.items():
    if key not in ("agent", "error_type", "message", "question", "query_plan", "traceback"):
      lines.extend(["", f"{key}: {json.dumps(val, indent=2) if isinstance(val, (dict, list)) else val}"])
  return "\n".join(lines)
