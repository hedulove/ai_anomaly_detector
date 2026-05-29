from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data_loader import data_store

OPS = {
  ">=": lambda s, v: s >= v,
  "<=": lambda s, v: s <= v,
  ">": lambda s, v: s > v,
  "<": lambda s, v: s < v,
  "==": lambda s, v: s == v,
  "!=": lambda s, v: s != v,
  "in": lambda s, v: s.isin(v if isinstance(v, list) else [v]),
  "contains": lambda s, v: s.astype(str).str.contains(str(v), case=False, na=False),
}

# LLMs often emit SQL-style operators
OP_ALIASES = {
  "eq": "==",
  "equals": "==",
  "equal": "==",
  "=": "==",
  "ne": "!=",
  "neq": "!=",
  "not_equals": "!=",
  "gte": ">=",
  "ge": ">=",
  "lte": "<=",
  "le": "<=",
  "gt": ">",
  "lt": "<",
  "like": "contains",
  "ilike": "contains",
}


def normalize_op(op: str) -> str:
  if not op:
    return "=="
  key = str(op).strip().lower()
  return OP_ALIASES.get(key, key)

# group_by aliases → pandas period frequency (derived from date column)
PERIOD_COLUMNS = {
  "week": "W",
  "month": "M",
  "year": "Y",
  "quarter": "Q",
  "day": "D",
}


def _resolve_date_column(df: pd.DataFrame, plan: dict[str, Any]) -> str:
  for candidate in (plan.get("date_col"), "date", "Date"):
    if candidate and candidate in df.columns:
      return candidate
  for col in df.columns:
    if "date" in col.lower():
      return col
  raise ValueError("No date column found for time aggregation")


def _add_period_columns(df: pd.DataFrame, columns: list[str], date_col: str) -> pd.DataFrame:
  """Create week/month/year/quarter columns from date when used in group_by or filters."""
  df = df.copy()
  if date_col not in df.columns:
    return df
  dates = pd.to_datetime(df[date_col])
  for col in columns:
    if col in df.columns:
      continue
    freq = PERIOD_COLUMNS.get(col)
    if freq:
      df[col] = dates.dt.to_period(freq).dt.start_time
    elif col in ("week_start", "period_week"):
      df[col] = dates.dt.to_period("W").dt.start_time
  return df


def _apply_transforms(df: pd.DataFrame, transforms: list[dict[str, Any]]) -> pd.DataFrame:
  for tr in transforms or []:
    ttype = tr.get("type")
    if ttype == "date_period":
      col = tr.get("column", "date")
      grain = tr.get("grain", "week")
      alias = tr.get("as") or grain
      if col not in df.columns:
        raise ValueError(f"Transform column not found: {col}")
      freq = PERIOD_COLUMNS.get(grain, grain)
      df = df.copy()
      df[alias] = pd.to_datetime(df[col]).dt.to_period(freq).dt.start_time
  return df


def execute_query_plan(plan: dict[str, Any]) -> pd.DataFrame:
  table = plan.get("table", "sales")
  df = data_store.get_table(table)

  date_col = _resolve_date_column(df, plan)
  period_needed = set()
  for col in plan.get("group_by") or []:
    if col in PERIOD_COLUMNS:
      period_needed.add(col)
  for filt in plan.get("filters", []):
    if filt.get("column") in PERIOD_COLUMNS:
      period_needed.add(filt["column"])

  df = _add_period_columns(df, list(period_needed), date_col)
  df = _apply_transforms(df, plan.get("transforms"))

  for filt in plan.get("filters", []):
    col = filt["column"]
    op = normalize_op(filt.get("op", "=="))
    val = filt["value"]
    if col in PERIOD_COLUMNS and col not in df.columns:
      df = _add_period_columns(df, [col], date_col)
    if col not in df.columns:
      raise ValueError(f"Filter column not found: {col}")
    series = df[col]
    is_date = col == date_col or col in PERIOD_COLUMNS or "date" in col.lower()
    if is_date:
      series = pd.to_datetime(series)
    if op == "between" and isinstance(val, list) and len(val) == 2:
      lo, hi = val[0], val[1]
      if is_date:
        lo, hi = pd.to_datetime(lo), pd.to_datetime(hi)
      df = df[(series >= lo) & (series <= hi)]
      continue
    if is_date and not isinstance(val, list):
      val = pd.to_datetime(val)
    fn = OPS.get(op)
    if not fn:
      raise ValueError(f"Unsupported filter op: {op}")
    df = df[fn(series, val)]

  group_by = plan.get("group_by") or []
  aggregations = plan.get("aggregations") or []

  if group_by:
    df = _add_period_columns(df, group_by, date_col)
    for col in group_by:
      if col not in df.columns:
        raise ValueError(
          f"Group column not found: {col}. "
          f"For weekly/monthly data use 'week' or 'month' (derived from {date_col}), "
          f"or add transforms in the plan."
        )

    named_aggs: dict[str, tuple[str, str]] = {}
    for agg in aggregations:
      col = agg["column"]
      func = agg.get("agg", "sum")
      alias = agg.get("as", col)
      if col not in df.columns:
        raise ValueError(f"Aggregation column not found: {col}")
      if alias in group_by:
        raise ValueError(f"Aggregation alias '{alias}' cannot match a group_by column")
      named_aggs[alias] = (col, func)

    if named_aggs:
      df = df.groupby(group_by, as_index=False).agg(
        **{alias: pd.NamedAgg(column=col, aggfunc=func) for alias, (col, func) in named_aggs.items()}
      )
    else:
      df = df.groupby(group_by, as_index=False).size().rename(columns={"size": "count"})

  sort_by = plan.get("sort_by", [])
  if sort_by:
    spec = sort_by[0]
    if isinstance(spec, dict):
      col, asc = spec.get("column"), spec.get("ascending", True)
    else:
      col, asc = spec, True
    if col in df.columns:
      df = df.sort_values(col, ascending=asc)

  limit = plan.get("limit")
  if limit:
    df = df.head(int(limit))

  return df.reset_index(drop=True)
