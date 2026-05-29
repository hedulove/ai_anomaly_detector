from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.auth import create_session, require_auth, validate_credentials
from backend.config import ROOT, settings
from backend.data_loader import data_store
from backend.orchestrator import get_sample_questions, investigate, investigate_async, revise
from backend.report_storage import plan_to_display_sql, report_path
from backend.serializers import serialize_investigation

app = FastAPI(title="Data Anomaly Agent", version="1.0.0")
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

_investigations: dict[str, dict[str, Any]] = {}


class LoginRequest(BaseModel):
  username: str
  password: str


class InvestigateRequest(BaseModel):
  question: str = Field(min_length=3)


class ReviseRequest(BaseModel):
  investigation_id: str
  feedback: str = Field(min_length=3)


class ConfigUpdate(BaseModel):
  llm_provider: str | None = None
  window_days: int | None = None
  grace_days: int | None = None
  custom_start: str | None = None
  custom_end: str | None = None
  holiday_logic: str | None = None
  train_months_back: int | None = None
  detection: dict[str, Any] | None = None
  chart: dict[str, Any] | None = None
  sample_rows: int | None = None


class DetectionUpdate(BaseModel):
  z_threshold: float | None = None
  iqr_factor: float | None = None
  mad_scale_factor: float | None = None
  rolling_window_cap: int | None = None
  rolling_window_floor: int | None = None
  rolling_window_divisor: int | None = None
  rolling_window_fixed: int | None = None
  rolling_detection_std_factor: float | None = None
  vote_min: int | None = None


@app.on_event("startup")
def startup() -> None:
  data_store.load()


@app.post("/api/auth/login")
def login(body: LoginRequest) -> dict[str, str]:
  if not validate_credentials(body.username, body.password):
    raise HTTPException(status_code=401, detail="Invalid credentials")
  return {"token": create_session()}


@app.get("/api/health")
def health() -> dict[str, Any]:
  return {"status": "ok", "data": data_store.status()}


@app.get("/api/config")
def get_config(_: str = Depends(require_auth)) -> dict[str, Any]:
  return settings.to_public_dict()


@app.put("/api/config")
def update_config(body: ConfigUpdate, _: str = Depends(require_auth)) -> dict[str, Any]:
  payload = body.model_dump(exclude_none=True)
  if payload.get("llm_provider") not in (None, "openai", "deepseek"):
    raise HTTPException(400, "llm_provider must be openai or deepseek")
  if payload.get("holiday_logic") not in (None, "ecuador", "us_federal", "none"):
    raise HTTPException(400, "Invalid holiday_logic")
  settings.update_from_dict(payload)
  if "train_months_back" in payload:
    data_store.load()
  return settings.to_public_dict()


@app.get("/api/data/date-range")
def data_date_range(_: str = Depends(require_auth)) -> dict[str, Any]:
  return data_store.date_range()


@app.get("/api/data/tables")
def data_tables(_: str = Depends(require_auth)) -> dict[str, Any]:
  return {"tables": data_store.list_tables()}


@app.get("/api/data/sample")
def data_sample(
  table: str = "sales",
  limit: int | None = None,
  offset: int = 0,
  _: str = Depends(require_auth),
) -> dict[str, Any]:
  if not data_store.loaded:
    raise HTTPException(400, "Data not loaded")
  row_limit = limit if limit is not None else settings.sample_rows
  return data_store.sample_table(table=table, limit=row_limit, offset=offset)


@app.post("/api/detection/reset")
def reset_detection(_: str = Depends(require_auth)) -> dict[str, Any]:
  settings.reset_detection_defaults()
  return settings.to_public_dict()


@app.post("/api/chart/reset")
def reset_chart(_: str = Depends(require_auth)) -> dict[str, Any]:
  settings.reset_chart_defaults()
  return settings.to_public_dict()


@app.put("/api/detection")
def update_detection(body: DetectionUpdate, _: str = Depends(require_auth)) -> dict[str, Any]:
  payload = body.model_dump(exclude_none=True)
  if "rolling_window_fixed" in payload and payload["rolling_window_fixed"] == 0:
    payload["rolling_window_fixed"] = None
  settings.update_from_dict({"detection": payload})
  return settings.to_public_dict()


@app.get("/api/suggestions")
def suggestions(_: str = Depends(require_auth)) -> dict[str, list[str]]:
  return {"questions": get_sample_questions()}


@app.get("/api/reports/download/{filename}")
def download_report(filename: str, _: str = Depends(require_auth)):
  try:
    path = report_path(filename)
  except FileNotFoundError:
    raise HTTPException(404, "Report not found") from None
  return FileResponse(
    path,
    media_type="application/json",
    filename=path.name,
  )


@app.post("/api/query/format")
def format_query_plan(body: dict[str, Any], _: str = Depends(require_auth)) -> dict[str, str]:
  return {"sql": plan_to_display_sql(body)}


@app.post("/api/investigate")
async def run_investigate(
  body: InvestigateRequest,
  _: str = Depends(require_auth),
) -> dict[str, str]:
  if not data_store.loaded:
    raise HTTPException(400, data_store.error or "Data not loaded. Add CSV files to data/")
  inv_id = str(uuid.uuid4())
  return {"investigation_id": inv_id, "question": body.question}


@app.get("/api/investigate/stream")
async def investigate_stream(
  investigation_id: str,
  question: str,
  token: str,
):
  from backend.auth import validate_token

  if not validate_token(token):
    raise HTTPException(401, "Not authenticated")
  if not data_store.loaded:
    raise HTTPException(400, "Data not loaded")

  queue: asyncio.Queue = asyncio.Queue()

  async def run() -> None:
    try:
      result = await investigate_async(question, queue)
      _investigations[investigation_id] = result
      await queue.put({"agent": "result", "status": "complete", "investigation_id": investigation_id, "result": result})
    except Exception as exc:
      await queue.put({"agent": "error", "status": "error", "message": str(exc)})

  asyncio.create_task(run())

  async def event_generator():
    while True:
      event = await queue.get()
      yield f"data: {json.dumps(event, default=str)}\n\n"
      if event.get("agent") in ("result", "error"):
        break

  return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/revise")
def run_revise(body: ReviseRequest, _: str = Depends(require_auth)) -> dict[str, Any]:
  raw = _investigations.get(body.investigation_id)
  if not raw:
    raise HTTPException(404, "Investigation not found or expired")
  updated = revise(raw, body.feedback)
  _investigations[body.investigation_id] = updated
  return updated


@app.get("/api/investigation/{investigation_id}")
def get_investigation(investigation_id: str, _: str = Depends(require_auth)) -> dict[str, Any]:
  raw = _investigations.get(investigation_id)
  if not raw:
    raise HTTPException(404, "Not found")
  return raw if raw.get("status") != "anomalies_found" or isinstance(raw.get("anomaly_results", {}).get("full_df"), list) else serialize_investigation(raw)


frontend_dir = ROOT / "frontend"
if frontend_dir.exists():
  app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
