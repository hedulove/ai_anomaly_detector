# Data Anomaly Agent

Multi-agent AI system for detecting, explaining, and reporting anomalies in **Store Sales Time Series Forecasting** (Kaggle) data.

## Quick start

1. **Install dependencies**

```bash
pip install -r requirements.txt
```

2. **API keys** — ensure `.env` contains:

```
OPENAI_API_KEY="sk-..."
DEEPSEEK_API_KEY="sk-..."
```

3. **Kaggle data** — download from  
   https://www.kaggle.com/competitions/store-sales-time-series-forecasting/data  
   and place files in `data/` (see `data/README.md`).

4. **Run** (single command — API + web UI):

```bash
python start.py
```

5. Open http://127.0.0.1:8000 — login: **hduran** / **123**

## Configuration

Edit `config.yaml`:

| Setting | Description |
|---------|-------------|
| `llm.provider` | `openai` or `deepseek` |
| `analysis.window_days` | Default 30 (~4 weeks) |
| `analysis.grace_days` | Default 2 |
| `analysis.custom_start` / `custom_end` | Optional fixed range |
| `holidays.logic` | `ecuador`, `us_federal`, or `none` |

You can also change LLM provider, date window, and holiday logic in the **Settings** panel (gear icon).

## Architecture

| Agent | Role |
|-------|------|
| Data Query Agent | Builds pandas query plans for Kaggle tables |
| Query Executor | Runs filters / groupby / aggregations |
| Anomaly Detector | Z-score, IQR, rolling deviation (2-of-3 vote) |
| Root Cause Agent | External / contextual explanations |
| Reporter Agent | Structured executive report |
| QA Reviewer | Validates report before display |

## Tech stack

- **Backend:** FastAPI, pandas, OpenAI SDK (OpenAI + DeepSeek)
- **Frontend:** React 18 + Babel standalone (no build step), Chart.js

## Kaggle files required

| File | Required |
|------|----------|
| `train.csv` | Yes |
| `stores.csv` | Yes |
| `holidays_events.csv` | Yes |
| `oil.csv` | Optional |
| `transactions.csv` | Optional |
