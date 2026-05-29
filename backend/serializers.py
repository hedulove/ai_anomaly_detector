from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def _serialize_value(v: Any) -> Any:
  if isinstance(v, (pd.Timestamp, datetime)):
    return v.isoformat()
  if isinstance(v, date):
    return v.isoformat()
  if isinstance(v, (np.integer, np.floating)):
    return float(v) if isinstance(v, np.floating) else int(v)
  if isinstance(v, (np.bool_, bool)):
    return bool(v)
  if pd.isna(v):
    return None
  return v


def df_to_records(df: pd.DataFrame | list | None, limit: int | None = None) -> list[dict[str, Any]]:
  if isinstance(df, list):
    return df[:limit] if limit else df
  if df is None or df.empty:
    return []
  subset = df.head(limit) if limit else df
  records = []
  for row in subset.to_dict(orient="records"):
    records.append({k: _serialize_value(v) for k, v in row.items()})
  return records


def serialize_investigation(result: dict[str, Any]) -> dict[str, Any]:
  out = dict(result)
  if "anomaly_results" in out and out["anomaly_results"]:
    ar = out["anomaly_results"]
    out["anomaly_results"] = {
      "found": ar.get("found"),
      "summary": ar.get("summary"),
      "method_details": ar.get("method_details"),
      "full_df": df_to_records(ar.get("full_df", pd.DataFrame()), 2000),
      "anomalies_df": df_to_records(ar.get("anomalies_df", pd.DataFrame())),
    }
  if "data" in out and isinstance(out["data"], pd.DataFrame):
    out["data"] = df_to_records(out["data"], 500)
  if "query_plan" in out:
    out["query_plan"] = out["query_plan"]
  return out
