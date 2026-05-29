from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from backend.config import DATA_DIR, settings

TABLE_CATALOG = """
### sales (primary — daily store sales)
Merged from train.csv + stores.csv. One row per id in train.
Columns:
- id (int), date (datetime), store_nbr (int), family (string product category)
- sales (float), onpromotion (int)
- city, state, type, cluster (from stores)

### stores
- store_nbr, city, state, type, cluster

### oil
- date, dcoilwtico (oil price — external factor for Ecuador economy)

### transactions (requires transactions.csv in data/)
- date, store_nbr, transactions (foot traffic)

### transactions_enriched (requires transactions.csv)
- Same as transactions joined with stores → includes city, state, type, cluster
- Use this table for questions about transactions by city or state

### holidays_events
- date, type, locale, locale_name, description, transferred
"""


class DataStore:
  def __init__(self) -> None:
    self.sales: pd.DataFrame | None = None
    self.stores: pd.DataFrame | None = None
    self.oil: pd.DataFrame | None = None
    self.transactions: pd.DataFrame | None = None
    self.holidays: pd.DataFrame | None = None
    self.loaded = False
    self.error: str | None = None

  def date_range(self) -> dict[str, Any]:
    if not self.loaded or self.sales is None or self.sales.empty:
      return {
        "available": False,
        "min_date": None,
        "max_date": None,
        "rows": 0,
        "message": self.error or "Data not loaded",
      }
    min_d = self.sales["date"].min()
    max_d = self.sales["date"].max()
    return {
      "available": True,
      "min_date": pd.Timestamp(min_d).strftime("%Y-%m-%d"),
      "max_date": pd.Timestamp(max_d).strftime("%Y-%m-%d"),
      "rows": int(len(self.sales)),
      "store_count": int(self.sales["store_nbr"].nunique()),
      "message": None,
    }

  def status(self) -> dict[str, Any]:
    required = ["train.csv", "stores.csv", "holidays_events.csv"]
    files = {name: (DATA_DIR / name).exists() for name in required}
    optional = {
      "oil.csv": (DATA_DIR / "oil.csv").exists(),
      "transactions.csv": (DATA_DIR / "transactions.csv").exists(),
    }
    out = {
      "ready": all(files.values()) and self.loaded,
      "required_files": files,
      "optional_files": optional,
      "error": self.error,
      "rows": len(self.sales) if self.sales is not None else 0,
    }
    out.update(self.date_range())
    return out

  def load(self) -> None:
    train_path = DATA_DIR / "train.csv"
    stores_path = DATA_DIR / "stores.csv"
    if not train_path.exists() or not stores_path.exists():
      self.error = "Missing train.csv or stores.csv in data/ folder"
      self.loaded = False
      return

    try:
      train = pd.read_csv(
        train_path,
        usecols=["id", "date", "store_nbr", "family", "sales", "onpromotion"],
        parse_dates=["date"],
      )
      stores = pd.read_csv(stores_path)
      self.stores = stores

      max_date = train["date"].max()
      cutoff = max_date - pd.DateOffset(months=settings.train_months_back)
      train = train[train["date"] >= cutoff]

      sales = train.merge(stores, on="store_nbr", how="left")
      self.sales = sales

      if (DATA_DIR / "oil.csv").exists():
        self.oil = pd.read_csv(DATA_DIR / "oil.csv", parse_dates=["date"])
      if (DATA_DIR / "transactions.csv").exists():
        self.transactions = pd.read_csv(
          DATA_DIR / "transactions.csv", parse_dates=["date"]
        )
      if (DATA_DIR / "holidays_events.csv").exists():
        self.holidays = pd.read_csv(
          DATA_DIR / "holidays_events.csv", parse_dates=["date"]
        )

      self.loaded = True
      self.error = None
    except Exception as exc:
      self.error = str(exc)
      self.loaded = False

  def sample_table(
    self,
    table: str = "sales",
    limit: int = 100,
    offset: int = 0,
  ) -> dict[str, Any]:
    if not self.loaded:
      return {
        "available": False,
        "message": self.error or "Data not loaded",
        "columns": [],
        "rows": [],
        "total_rows": 0,
      }
    try:
      df = self.get_table(table)
    except ValueError as exc:
      return {
        "available": False,
        "message": str(exc),
        "columns": [],
        "rows": [],
        "total_rows": 0,
      }
    total = len(df)
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    slice_df = df.iloc[offset : offset + limit]
    rows = []
    for rec in slice_df.to_dict(orient="records"):
      clean = {}
      for k, v in rec.items():
        if hasattr(v, "isoformat"):
          clean[k] = v.isoformat()[:19] if hasattr(v, "hour") else v.isoformat()[:10]
        elif pd.isna(v):
          clean[k] = None
        else:
          clean[k] = v if isinstance(v, (int, float, str, bool)) else str(v)
      rows.append(clean)
    return {
      "available": True,
      "table": table,
      "columns": list(slice_df.columns),
      "rows": rows,
      "total_rows": total,
      "offset": offset,
      "limit": limit,
      "message": None,
    }

  def transactions_enriched_df(self) -> pd.DataFrame | None:
    if self.transactions is None:
      return None
    if self.stores is None:
      return self.transactions.copy()
    return self.transactions.merge(self.stores, on="store_nbr", how="left")

  def list_tables(self) -> list[dict[str, str]]:
    tables = []
    if self.sales is not None:
      tables.append({"id": "sales", "label": "Sales (train + stores)"})
    if self.stores is not None:
      tables.append({"id": "stores", "label": "Stores"})
    if self.oil is not None:
      tables.append({"id": "oil", "label": "Oil prices"})
    if self.transactions is not None:
      tables.append({"id": "transactions", "label": "Transactions"})
      tables.append({
        "id": "transactions_enriched",
        "label": "Transactions + stores (city/state)",
      })
    if self.holidays is not None:
      tables.append({"id": "holidays_events", "label": "Holidays & events"})
    return tables

  def get_table(self, name: str) -> pd.DataFrame:
    if name == "transactions_enriched":
      df = self.transactions_enriched_df()
      if df is None:
        raise ValueError(
          "Table 'transactions' is not loaded. Add transactions.csv to the data/ folder "
          "(Kaggle Store Sales dataset), then restart the app."
        )
      return df

    mapping = {
      "sales": self.sales,
      "stores": self.stores,
      "oil": self.oil,
      "transactions": self.transactions,
      "holidays_events": self.holidays,
      "holidays": self.holidays,
    }
    df = mapping.get(name)
    if df is None:
      if name == "transactions":
        raise ValueError(
          "Table 'transactions' is not loaded. Add transactions.csv to the data/ folder "
          "(Kaggle Store Sales dataset), then restart the app."
        )
      raise ValueError(f"Unknown or unloaded table: {name}")
    return df.copy()


data_store = DataStore()
