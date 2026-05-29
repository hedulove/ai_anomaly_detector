"""Generate minimal CSV files in data/ for local smoke tests (not full Kaggle dataset)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

rng = np.random.default_rng(42)
dates = pd.date_range("2016-01-01", "2017-08-15", freq="D")
stores = pd.DataFrame({
  "store_nbr": [1, 2, 3],
  "city": ["Quito", "Guayaquil", "Cuenca"],
  "state": ["Pichincha", "Guayas", "Azuay"],
  "type": ["A", "B", "C"],
  "cluster": [1, 2, 3],
})
rows = []
for d in dates:
  for sn in [1, 2, 3]:
    base = 800 + sn * 100
    spike = 400 if d == pd.Timestamp("2017-07-04") and sn == 1 else 0
    rows.append({
      "id": len(rows),
      "date": d,
      "store_nbr": sn,
      "family": "GROCERY I",
      "sales": max(0, base + rng.normal(0, 80) + spike),
      "onpromotion": int(rng.random() > 0.7),
    })
train = pd.DataFrame(rows)
train.to_csv(DATA / "train.csv", index=False)
stores.to_csv(DATA / "stores.csv", index=False)
holidays = pd.DataFrame({
  "date": ["2017-01-01", "2017-07-04", "2016-12-25"],
  "type": ["Holiday", "Holiday", "Holiday"],
  "locale": ["Ecuador", "Ecuador", "Ecuador"],
  "locale_name": ["Ecuador", "Ecuador", "Ecuador"],
  "description": ["New Year", "Independence", "Christmas"],
  "transferred": [False, False, False],
})
holidays.to_csv(DATA / "holidays_events.csv", index=False)

tx_rows = []
for d in dates:
  for sn in [1, 2, 3]:
    tx_rows.append({
      "date": d,
      "store_nbr": sn,
      "transactions": max(10, int(120 + sn * 15 + rng.normal(0, 20))),
    })
pd.DataFrame(tx_rows).to_csv(DATA / "transactions.csv", index=False)

print(f"Demo data written to {DATA} (includes transactions.csv)")
