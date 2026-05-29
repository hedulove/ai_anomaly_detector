#!/usr/bin/env python3
"""Start backend (serves API + React frontend on one port)."""
from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.config import settings  # noqa: E402


def main() -> None:
  url = f"http://{settings.host}:{settings.port}"
  print(f"\n  Data Anomaly Agent\n  Open: {url}\n  Login: {settings.auth_username} / (see config.yaml)\n")
  webbrowser.open(url)
  uvicorn.run(
    "backend.main:app",
    host=settings.host,
    port=settings.port,
    reload=False,
  )


if __name__ == "__main__":
  main()
