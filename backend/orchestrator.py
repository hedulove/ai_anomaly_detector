from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pandas as pd

from backend.agents.qa_agent import qa_reviewer
from backend.agents.query_agent import execute_plan, query_agent
from backend.agents.reporter_agent import reporter_agent
from backend.agents.root_cause_agent import root_cause_agent
from backend.anomaly_detector import anomaly_detector
from backend.config import settings
from backend.data_loader import data_store
from backend.error_detail import build_error_detail
from backend.report_storage import save_investigation_report
from backend.serializers import serialize_investigation

EmitFn = Callable[[str, dict[str, Any]], None]

def get_sample_questions() -> list[str]:
  questions = [
    "Find anomalies in daily total sales across all stores",
    "Detect anomalies in daily sales by state",
    "Find anomalies in sales for the GROCERY I family by week",
    "Find anomalies in daily sales for store type A vs type D",
    "Detect spikes in on-promotion sales volume by month",
  ]
  if data_store.transactions is not None:
    questions.insert(
      3,
      "Detect unusual patterns in store transaction counts by city",
    )
  else:
    questions.insert(
      3,
      "Detect unusual patterns in daily sales by city",
    )
  return questions


SAMPLE_QUESTIONS = get_sample_questions()


def _emit(emit: EmitFn | None, agent: str, payload: dict[str, Any]) -> None:
  if emit:
    emit(agent, payload)


def investigate(
  question: str,
  max_query_retries: int = 2,
  max_qa_retries: int = 1,
  emit: EmitFn | None = None,
) -> dict[str, Any]:
  start, end = settings.analysis_window()
  _emit(emit, "orchestrator", {
    "status": "started",
    "message": "Anomaly investigation started",
    "question": question,
    "window": {"start": start, "end": end},
  })

  sql_feedback = None
  anomaly_results = None
  query_result = None
  df = None

  for attempt in range(max_query_retries + 1):
    label = f" (retry {attempt})" if attempt else ""
    _emit(emit, "query_agent", {"status": "running", "message": f"Designing data query{label}..."})
    try:
      query_result = query_agent(question, feedback=sql_feedback)
    except Exception as exc:
      _emit(emit, "query_agent", {
        "status": "error",
        "message": str(exc),
        "error_detail": build_error_detail("query_agent", exc, question=question),
      })
      if attempt < max_query_retries:
        sql_feedback = f"JSON parse error: {exc}. Return valid JSON only."
        continue
      return {"status": "error", "message": "Query agent failed"}

    _emit(emit, "query_agent", {
      "status": "done",
      "message": query_result.get("explanation", "Query plan ready"),
      "plan": query_result,
      "query_sql": query_result.get("sql") or None,
    })

    _emit(emit, "query_executor", {"status": "running", "message": "Executing pandas query..."})
    try:
      df = execute_plan(query_result)
    except Exception as exc:
      _emit(emit, "query_executor", {
        "status": "error",
        "message": str(exc),
        "error_detail": build_error_detail(
          "query_executor", exc, question=question, query_plan=query_result
        ),
      })
      sql_feedback = f"Execution failed: {exc}. Fix the plan. Use op '==' not 'eq'."
      continue

    _emit(emit, "query_executor", {
      "status": "done",
      "message": f"Loaded {len(df)} rows",
      "preview": df.head(5).to_dict(orient="records") if not df.empty else [],
    })

    if df.empty:
      sql_feedback = "Query returned no data. Broaden filters or aggregation."
      continue

    metric_col = query_result["metric_col"]
    date_col = query_result["date_col"]
    dimension_col = query_result.get("dimension_col")

    _emit(emit, "anomaly_detector", {
      "status": "running",
      "message": f"Analyzing {len(df)} points with statistical methods...",
    })
    anomaly_results = anomaly_detector(
      df,
      metric_col,
      date_col,
      dimension_col,
      holiday_logic=settings.holiday_logic,
      detection_params=settings.detection_params,
    )
    _emit(emit, "anomaly_detector", {
      "status": "done",
      "message": anomaly_results["summary"],
      "found": anomaly_results["found"],
      "count": len(anomaly_results.get("anomalies_df", [])),
    })

    if anomaly_results["found"]:
      break
    if attempt < max_query_retries:
      sql_feedback = (
        "No anomalies found. Try different granularity, dimension, or metric."
      )
    else:
      report = {
        "title": "No Anomalies Detected",
        "executive_summary": (
          f"Analysis from {start} to {end} shows values within normal bounds."
        ),
        "anomalies_found": [],
        "detection_methods": [],
        "root_causes": {"internal": [], "external": []},
        "recommendation": "Continue monitoring.",
      }
      inv = {
        "status": "no_anomalies",
        "question": question,
        "report": report,
        "anomaly_results": anomaly_results,
        "query_plan": query_result,
        "_meta": {
          "metric_col": metric_col,
          "date_col": date_col,
          "dimension_col": dimension_col,
        },
      }
      _emit(emit, "orchestrator", {"status": "complete", "message": "No anomalies detected"})
      return serialize_investigation(inv)

  if not anomaly_results or not anomaly_results["found"]:
    return {"status": "error", "message": "Investigation failed"}

  metric_col = query_result["metric_col"]
  date_col = query_result["date_col"]
  dimension_col = query_result.get("dimension_col")

  _emit(emit, "root_cause_agent", {"status": "running", "message": "Investigating root causes..."})
  root_cause = root_cause_agent(
    question,
    anomaly_results["summary"],
    query_result,
    query_result.get("context", ""),
    anomaly_results["anomalies_df"],
  )
  _emit(emit, "root_cause_agent", {
    "status": "done",
    "message": root_cause.get("hypothesis", "Analysis complete"),
    "hypothesis": root_cause.get("hypothesis"),
  })

  report = None
  qa_result = None
  saved_report_file = None
  for qa_attempt in range(max_qa_retries + 1):
    _emit(emit, "reporter_agent", {
      "status": "running",
      "message": "Generating executive report...",
    })
    report = reporter_agent(question, anomaly_results, root_cause)
    _emit(emit, "reporter_agent", {
      "status": "done",
      "message": report.get("title", "Report ready"),
    })

    _emit(emit, "qa_agent", {"status": "running", "message": "Validating report quality..."})
    raw = anomaly_results["anomalies_df"].head(10).to_string(index=False)
    qa_result = qa_reviewer(question, report, anomaly_results["summary"], raw)
    approved = qa_result.get("approved") or qa_result.get("score", 0) >= 6
    report_file = None
    if approved and report:
      try:
        report_file = saved_report_file = save_investigation_report(
          question,
          report,
          qa_result,
          query_plan=query_result,
          root_cause=root_cause,
          extra={
            "analysis_window": {"start": start, "end": end},
            "anomaly_summary": anomaly_results.get("summary"),
          },
        )
      except Exception as exc:
        report_file = None
        qa_result["save_error"] = str(exc)

    _emit(emit, "qa_agent", {
      "status": "done" if approved else "warning",
      "message": f"Score {qa_result.get('score', '?')}/10"
      + (f" · Report saved" if report_file else ""),
      "approved": approved,
      "feedback": qa_result.get("feedback"),
      "report_file": report_file,
    })
    if approved:
      break
    if qa_attempt < max_qa_retries:
      root_cause["hypothesis"] = (
        root_cause.get("hypothesis", "")
        + f" [QA: {qa_result.get('feedback', '')}]"
      )

  investigation = {
    "status": "anomalies_found",
    "question": question,
    "report": report,
    "anomaly_results": anomaly_results,
    "root_cause": root_cause,
    "qa_result": qa_result,
    "data": df,
    "query_plan": query_result,
    "report_file": saved_report_file,
    "_meta": {
      "metric_col": metric_col,
      "date_col": date_col,
      "dimension_col": dimension_col,
    },
  }
  _emit(emit, "orchestrator", {"status": "complete", "message": "Investigation complete"})
  return serialize_investigation(investigation)


def revise(prev_result: dict[str, Any], feedback: str, max_revisions: int = 3) -> dict[str, Any]:
  if not prev_result or prev_result.get("status") != "anomalies_found":
    return {"status": "error", "message": "Nothing to revise"}

  rev_count = prev_result.get("_revision_count", 0) + 1
  if rev_count > max_revisions:
    return prev_result

  question = prev_result["question"]
  anomaly_results = prev_result.get("anomaly_results", {})
  root_cause = prev_result.get("root_cause", {})
  meta = prev_result.get("_meta", {})

  full_df = pd.DataFrame(anomaly_results.get("full_df", []))
  anomalies_df = pd.DataFrame(anomaly_results.get("anomalies_df", []))
  restored = {
    "found": anomaly_results.get("found"),
    "summary": anomaly_results.get("summary"),
    "method_details": anomaly_results.get("method_details"),
    "full_df": full_df,
    "anomalies_df": anomalies_df,
  }

  report = reporter_agent(
    question, restored, root_cause, revision_feedback=feedback
  )
  prev_result["report"] = report
  prev_result["_revision_count"] = rev_count
  prev_result["_revision_feedback"] = feedback
  return serialize_investigation(prev_result)


async def investigate_async(
  question: str,
  queue: asyncio.Queue,
  **kwargs: Any,
) -> dict[str, Any]:
  loop = asyncio.get_event_loop()

  def emit(agent: str, payload: dict[str, Any]) -> None:
    loop.call_soon_threadsafe(
      queue.put_nowait,
      {"agent": agent, **payload},
    )

  return await loop.run_in_executor(
    None,
    lambda: investigate(question, emit=emit, **kwargs),
  )
