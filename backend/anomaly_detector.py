from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from backend.detection_defaults import DETECTION_DEFAULTS
from backend.holidays import get_exclusion_dates


def _rolling_window_size(n: int, params: dict[str, Any]) -> int:
  fixed = params.get("rolling_window_fixed")
  if fixed is not None and int(fixed) > 0:
    return int(fixed)
  cap = int(params.get("rolling_window_cap", DETECTION_DEFAULTS["rolling_window_cap"]))
  floor = int(params.get("rolling_window_floor", DETECTION_DEFAULTS["rolling_window_floor"]))
  divisor = int(params.get("rolling_window_divisor", DETECTION_DEFAULTS["rolling_window_divisor"]))
  divisor = max(1, divisor)
  return min(cap, max(floor, n // divisor))


def _detect_partial_periods(work: pd.DataFrame, date_col: str) -> pd.Series:
  is_partial = pd.Series(False, index=work.index)
  unique_dates = sorted(work[date_col].dt.normalize().unique())
  if len(unique_dates) < 3:
    return is_partial

  gaps_days = np.array(
    [(unique_dates[i + 1] - unique_dates[i]).days for i in range(len(unique_dates) - 1)],
    dtype=float,
  )
  median_gap = float(np.median(gaps_days))
  if median_gap < 5:
    return is_partial

  last_period = unique_dates[-1]
  today = pd.Timestamp(date.today())
  if (today - last_period).days < median_gap:
    is_partial = is_partial | (work[date_col].dt.normalize() == last_period)

  first_gap = (unique_dates[1] - unique_dates[0]).days
  if first_gap < median_gap * 0.6:
    is_partial = is_partial | (work[date_col].dt.normalize() == unique_dates[0])

  return is_partial


def anomaly_detector(
  df: pd.DataFrame,
  metric_col: str,
  date_col: str,
  dimension_col: str | None = None,
  holiday_logic: str | None = None,
  detection_params: dict[str, Any] | None = None,
) -> dict:
  params = {**DETECTION_DEFAULTS, **(detection_params or {})}
  z_threshold = float(params["z_threshold"])
  iqr_factor = float(params["iqr_factor"])
  mad_scale = float(params["mad_scale_factor"])
  rolling_std_factor = float(params["rolling_detection_std_factor"])
  vote_min = int(params["vote_min"])

  results = {
    "found": False,
    "anomalies_df": pd.DataFrame(),
    "summary": "",
    "method_details": {},
    "full_df": df.copy(),
    "detection_params": params,
  }

  if df.empty or metric_col not in df.columns:
    results["summary"] = "No data or metric column not found."
    return results

  work = df.copy()
  work[date_col] = pd.to_datetime(work[date_col])
  work = work.sort_values(date_col)

  years = set(work[date_col].dt.year.unique())
  exclusion = get_exclusion_dates(years, holiday_logic)
  work["is_holiday"] = work[date_col].dt.date.isin(exclusion)
  work["is_partial_period"] = _detect_partial_periods(work, date_col)

  def _detect_group(gdf: pd.DataFrame) -> pd.DataFrame:
    vals = gdf[metric_col].astype(float)
    n = len(vals)
    if n < 5:
      gdf = gdf.copy()
      gdf["is_anomaly"] = False
      gdf["anomaly_score"] = 0.0
      gdf["anomaly_methods"] = ""
      gdf["rolling_mean"] = np.nan
      gdf["rolling_std"] = np.nan
      gdf["rolling_upper"] = np.nan
      gdf["rolling_lower"] = np.nan
      return gdf

    median = vals.median()
    mad = np.median(np.abs(vals - median))
    mad = mad if mad > 0 else float(vals.std() or 1)
    mod_z = mad_scale * (vals - median) / mad
    z_flag = mod_z.abs() > z_threshold

    q1, q3 = vals.quantile(0.25), vals.quantile(0.75)
    iqr = q3 - q1
    iqr_flag = (vals < q1 - iqr_factor * iqr) | (vals > q3 + iqr_factor * iqr)

    win = _rolling_window_size(n, params)
    rolling_mean = vals.rolling(window=win, center=True, min_periods=2).mean()
    rolling_std = vals.rolling(window=win, center=True, min_periods=2).std()
    rolling_flag = (vals - rolling_mean).abs() > rolling_std_factor * rolling_std

    methods_list = []
    for i in gdf.index:
      methods = []
      if z_flag.get(i, False):
        methods.append("z-score")
      if iqr_flag.get(i, False):
        methods.append("iqr")
      if rolling_flag.get(i, False):
        methods.append("rolling")
      methods_list.append(", ".join(methods))

    vote = z_flag.astype(int) + iqr_flag.astype(int) + rolling_flag.astype(int)
    gdf = gdf.copy()
    gdf["is_anomaly"] = vote >= vote_min
    gdf["anomaly_score"] = mod_z.abs().round(2)
    gdf["anomaly_methods"] = methods_list
    gdf["rolling_mean"] = rolling_mean
    gdf["rolling_std"] = rolling_std
    gdf["rolling_upper"] = rolling_mean + rolling_std_factor * rolling_std
    gdf["rolling_lower"] = rolling_mean - rolling_std_factor * rolling_std
    gdf["rolling_window_used"] = win
    return gdf

  if dimension_col and dimension_col in work.columns:
    work = work.groupby(dimension_col, group_keys=False).apply(_detect_group)
  else:
    work = _detect_group(work)

  work.loc[work["is_holiday"], "is_anomaly"] = False
  work.loc[work["is_partial_period"], "is_anomaly"] = False

  anomalies = work[work["is_anomaly"]].copy()
  results["full_df"] = work
  results["anomalies_df"] = anomalies
  results["found"] = len(anomalies) > 0

  holiday_excluded = int(work["is_holiday"].sum())
  partial_excluded = int(work["is_partial_period"].sum())
  notes = []
  if holiday_excluded:
    notes.append(f"{holiday_excluded} holiday/grace-period")
  if partial_excluded:
    notes.append(f"{partial_excluded} incomplete-period")
  exclusion_str = f" ({' + '.join(notes)} data points excluded.)" if notes else ""

  win_desc = (
    f"fixed={params['rolling_window_fixed']}"
    if params.get("rolling_window_fixed")
    else f"min({params['rolling_window_cap']}, max({params['rolling_window_floor']}, n//{params['rolling_window_divisor']}))"
  )

  if results["found"]:
    pct = round(100 * len(anomalies) / len(work), 1)
    dim_info = ""
    if dimension_col and dimension_col in anomalies.columns:
      top = anomalies[dimension_col].value_counts().head(5).to_dict()
      dim_info = f" Top affected groups: {top}."
    results["summary"] = (
      f"Detected {len(anomalies)} anomalies out of {len(work)} data points ({pct}%).{dim_info} "
      f"Methods: Modified Z-score (threshold={z_threshold}), IQR (factor={iqr_factor}), "
      f"Rolling (window={win_desc}, std×{rolling_std_factor}), vote≥{vote_min}/3.{exclusion_str}"
    )
  else:
    results["summary"] = (
      f"No anomalies detected across {len(work)} data points.{exclusion_str}"
    )

  results["method_details"] = {
    **params,
    "total_points": len(work),
    "anomaly_count": len(anomalies),
    "holiday_points_excluded": holiday_excluded,
    "partial_period_points_excluded": partial_excluded,
  }
  return results
