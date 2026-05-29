from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from backend.config import DATA_DIR, settings

_holiday_cache: dict[str, set[date]] = {}


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
  first = date(year, month, 1)
  offset = (weekday - first.weekday()) % 7
  return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
  if month == 12:
    last_day = date(year + 1, 1, 1) - timedelta(days=1)
  else:
    last_day = date(year, month + 1, 1) - timedelta(days=1)
  offset = (last_day.weekday() - weekday) % 7
  return last_day - timedelta(days=offset)


def us_federal_holidays(years: set[int]) -> set[date]:
  grace = {
    "standard": (1, 1),
    "long_weekend": (1, 2),
    "thanksgiving": (1, 3),
    "year_end": (2, 5),
  }
  exclusion: set[date] = set()

  def add_holiday(d: date, category: str) -> None:
    before, after = grace[category]
    observed = d
    if d.weekday() == 5:
      observed = d - timedelta(days=1)
    elif d.weekday() == 6:
      observed = d + timedelta(days=1)
    day = observed - timedelta(days=before)
    end = observed + timedelta(days=after)
    while day <= end:
      exclusion.add(day)
      day += timedelta(days=1)
    exclusion.add(d)

  for yr in years:
    add_holiday(date(yr, 1, 1), "year_end")
    add_holiday(date(yr, 12, 25), "year_end")
    add_holiday(_nth_weekday(yr, 2, 0, 3), "long_weekend")
    add_holiday(_last_weekday(yr, 5, 0), "long_weekend")
    add_holiday(date(yr, 7, 4), "long_weekend")
    add_holiday(_nth_weekday(yr, 9, 0, 1), "long_weekend")
    add_holiday(_nth_weekday(yr, 11, 3, 4), "thanksgiving")
    add_holiday(_nth_weekday(yr, 1, 0, 3), "standard")
    add_holiday(date(yr, 6, 19), "standard")
    add_holiday(_nth_weekday(yr, 10, 0, 2), "standard")
    add_holiday(date(yr, 11, 11), "standard")
  return exclusion


def ecuador_holidays(years: set[int]) -> set[date]:
  path = DATA_DIR / "holidays_events.csv"
  if not path.exists():
    return set()
  df = pd.read_csv(path, parse_dates=["date"])
  df = df[df["transferred"].astype(str).str.lower() == "false"]
  national = df[
    (df["locale"] == "Ecuador")
    & (df["locale_name"] == "Ecuador")
    & (df["type"].isin(["Holiday", "Bridge", "Additional", "Transfer"]))
  ]
  dates = set()
  for d in national["date"].dt.date:
    if d.year in years:
      dates.add(d)
      for offset in (-1, 0, 1):
        dates.add(d + timedelta(days=offset))
  return dates


def get_exclusion_dates(years: set[int], logic: str | None = None) -> set[date]:
  logic = logic or settings.holiday_logic
  cache_key = f"{logic}:{min(years)}-{max(years)}" if years else logic
  if cache_key in _holiday_cache:
    return _holiday_cache[cache_key]
  if logic == "none":
    result: set[date] = set()
  elif logic == "us_federal":
    result = us_federal_holidays(years)
  else:
    result = ecuador_holidays(years)
  _holiday_cache[cache_key] = result
  return result
