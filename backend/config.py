from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from backend.detection_defaults import (
  CHART_DEFAULTS,
  DATA_EXPLORER_DEFAULTS,
  DETECTION_DEFAULTS,
)

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
DATA_DIR = ROOT / "data"

load_dotenv(ROOT / ".env")


def load_yaml() -> dict[str, Any]:
  if not CONFIG_PATH.exists():
    return {}
  with CONFIG_PATH.open(encoding="utf-8") as f:
    return yaml.safe_load(f) or {}


def save_yaml(data: dict[str, Any]) -> None:
  with CONFIG_PATH.open("w", encoding="utf-8") as f:
    yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


class Settings:
  def __init__(self) -> None:
    self.reload()

  def reload(self) -> None:
    raw = load_yaml()
    self.llm_provider: str = raw.get("llm", {}).get("provider", "openai")
    analysis = raw.get("analysis", {})
    self.window_days: int = int(analysis.get("window_days", 30))
    self.grace_days: int = int(analysis.get("grace_days", 2))
    self.custom_start: str | None = analysis.get("custom_start")
    self.custom_end: str | None = analysis.get("custom_end")
    self.holiday_logic: str = raw.get("holidays", {}).get("logic", "ecuador")
    auth = raw.get("auth", {})
    self.auth_username: str = auth.get("username", "hduran")
    self.auth_password: str = str(auth.get("password", "123"))
    server = raw.get("server", {})
    self.host: str = server.get("host", "127.0.0.1")
    self.port: int = int(server.get("port", 8000))
    demo = raw.get("demo", {})
    self.train_months_back: int = int(demo.get("train_months_back", 18))

    detection = raw.get("detection", {})
    self.detection_params: dict[str, Any] = {
      **DETECTION_DEFAULTS,
      **{k: detection[k] for k in DETECTION_DEFAULTS if k in detection},
    }
    if "rolling_window_fixed" in detection:
      v = detection["rolling_window_fixed"]
      self.detection_params["rolling_window_fixed"] = int(v) if v not in (None, "", 0) else None

    chart = raw.get("chart", {})
    self.chart_params: dict[str, Any] = {
      **CHART_DEFAULTS,
      **{k: chart[k] for k in CHART_DEFAULTS if k in chart},
    }
    self.chart_params["show_std_bands"] = bool(self.chart_params.get("show_std_bands", True))

    explorer = raw.get("data_explorer", {})
    self.sample_rows: int = int(
      explorer.get("sample_rows", DATA_EXPLORER_DEFAULTS["sample_rows"])
    )

  @property
  def today(self) -> date:
    return date.today()

  def analysis_window(self) -> tuple[str, str]:
    if self.custom_start and self.custom_end:
      return self.custom_start, self.custom_end
    end = self.today - timedelta(days=self.grace_days)
    start = end - timedelta(days=self.window_days - 1)
    return start.isoformat(), end.isoformat()

  def baseline_start(self, analysis_start: str) -> str:
    start = date.fromisoformat(analysis_start) - timedelta(days=28)
    return start.isoformat()

  def to_public_dict(self) -> dict[str, Any]:
    start, end = self.analysis_window()
    return {
      "llm_provider": self.llm_provider,
      "window_days": self.window_days,
      "grace_days": self.grace_days,
      "custom_start": self.custom_start,
      "custom_end": self.custom_end,
      "analysis_start": start,
      "analysis_end": end,
      "holiday_logic": self.holiday_logic,
      "train_months_back": self.train_months_back,
      "detection": self.detection_params,
      "detection_defaults": DETECTION_DEFAULTS,
      "chart": self.chart_params,
      "chart_defaults": CHART_DEFAULTS,
      "sample_rows": self.sample_rows,
    }

  def update_from_dict(self, payload: dict[str, Any]) -> None:
    raw = load_yaml()
    if "llm_provider" in payload:
      raw.setdefault("llm", {})["provider"] = payload["llm_provider"]
    analysis = raw.setdefault("analysis", {})
    for key in ("window_days", "grace_days", "custom_start", "custom_end"):
      if key in payload:
        analysis[key] = payload[key]
    if "holiday_logic" in payload:
      raw.setdefault("holidays", {})["logic"] = payload["holiday_logic"]
    if "train_months_back" in payload:
      raw.setdefault("demo", {})["train_months_back"] = payload["train_months_back"]
    if "detection" in payload and isinstance(payload["detection"], dict):
      raw.setdefault("detection", {}).update(payload["detection"])
    if "chart" in payload and isinstance(payload["chart"], dict):
      raw.setdefault("chart", {}).update(payload["chart"])
    if "sample_rows" in payload:
      raw.setdefault("data_explorer", {})["sample_rows"] = payload["sample_rows"]
    save_yaml(raw)
    self.reload()

  def reset_detection_defaults(self) -> None:
    raw = load_yaml()
    raw["detection"] = dict(DETECTION_DEFAULTS)
    save_yaml(raw)
    self.reload()

  def reset_chart_defaults(self) -> None:
    raw = load_yaml()
    raw["chart"] = dict(CHART_DEFAULTS)
    save_yaml(raw)
    self.reload()


settings = Settings()
