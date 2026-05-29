from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

from backend.config import settings

PROVIDERS = {
  "openai": {
    "base_url": None,
    "model": "gpt-4o-mini",
    "fast_model": "gpt-4o-mini",
    "env_key": "OPENAI_API_KEY",
  },
  "deepseek": {
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "fast_model": "deepseek-chat",
    "env_key": "DEEPSEEK_API_KEY",
  },
}


def _strip_quotes(value: str) -> str:
  value = value.strip()
  if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
    return value[1:-1]
  return value


def get_api_key(provider: str | None = None) -> str:
  provider = provider or settings.llm_provider
  cfg = PROVIDERS.get(provider, PROVIDERS["openai"])
  key = _strip_quotes(os.getenv(cfg["env_key"], "") or "")
  if not key:
    raise RuntimeError(f"Missing API key for provider '{provider}' in .env")
  return key


def get_client(provider: str | None = None) -> OpenAI:
  provider = provider or settings.llm_provider
  cfg = PROVIDERS[provider]
  kwargs: dict[str, Any] = {"api_key": get_api_key(provider)}
  if cfg["base_url"]:
    kwargs["base_url"] = cfg["base_url"]
  return OpenAI(**kwargs)


def call_llm(
  system_prompt: str,
  user_prompt: str,
  temperature: float = 0.0,
  fast: bool = False,
  provider: str | None = None,
) -> str:
  provider = provider or settings.llm_provider
  cfg = PROVIDERS[provider]
  model = cfg["fast_model"] if fast else cfg["model"]
  client = get_client(provider)
  response = client.chat.completions.create(
    model=model,
    messages=[
      {"role": "system", "content": system_prompt},
      {"role": "user", "content": user_prompt},
    ],
    temperature=temperature,
    max_tokens=8192,
  )
  return response.choices[0].message.content or ""


def parse_json_response(raw: str) -> dict[str, Any]:
  text = re.sub(r"```json\s*", "", raw)
  text = re.sub(r"```\s*", "", text).strip()
  return json.loads(text)
