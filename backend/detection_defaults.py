"""Default anomaly detection and chart visualization parameters."""

from __future__ import annotations

from typing import Any

DETECTION_DEFAULTS: dict[str, Any] = {
  "z_threshold": 2.5,
  "iqr_factor": 1.5,
  "mad_scale_factor": 0.6745,
  "rolling_window_cap": 7,
  "rolling_window_floor": 3,
  "rolling_window_divisor": 3,
  "rolling_window_fixed": None,
  "rolling_detection_std_factor": 2.0,
  "vote_min": 2,
}

CHART_DEFAULTS: dict[str, Any] = {
  "show_std_bands": False,
  "band_std_factor": 1.5,
}

DATA_EXPLORER_DEFAULTS: dict[str, Any] = {
  "sample_rows": 100,
}
