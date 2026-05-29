from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import settings

security = HTTPBearer(auto_error=False)
_sessions: dict[str, datetime] = {}
SESSION_HOURS = 12


def create_session() -> str:
  token = secrets.token_urlsafe(32)
  _sessions[token] = datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)
  return token


def validate_credentials(username: str, password: str) -> bool:
  return username == settings.auth_username and password == settings.auth_password


def validate_token(token: str | None) -> bool:
  if not token or token not in _sessions:
    return False
  if datetime.now(timezone.utc) > _sessions[token]:
    _sessions.pop(token, None)
    return False
  return True


def require_auth(
  credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
  token = credentials.credentials if credentials else None
  if not validate_token(token):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Not authenticated",
    )
  return token  # type: ignore[return-value]
