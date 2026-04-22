# Data Observability Agent

![Status](https://img.shields.io/badge/status-in%20progress-yellow)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Stack](https://img.shields.io/badge/LLM-Claude%20Sonnet-orange)

> Monitors any SQL database across 5 observability pillars, detects anomalies statistically, and generates a natural-language Root Cause Analysis — replacing manual data incident triage.

---

<!--
## Demo

🚧 Streamlit deployment in progress — link will be updated here.

![Demo GIF](docs/demo.gif)
-->

---

## Problem Statement

Data teams detect most data quality incidents **after** stakeholders do.

A table goes stale at 3am. A pipeline silently drops 40% of rows. A schema migration adds a nullable column that breaks three downstream dashboards. By the time anyone notices, the damage is done — hours of triage, broken reports, and eroded trust.

Existing solutions (Monte Carlo, Acceldata) cost $30k+/year and require weeks of onboarding. This agent does the same core job: **continuous monitoring + automated root cause analysis**, with zero proprietary lock-in and a 5-minute setup.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│              Streamlit Dashboard              │
│   (trigger checks · view incidents · ROI)    │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
          ┌──────────────────┐
          │  Monitor Agent   │  ← orchestrates the full pipeline
          └────────┬─────────┘
                   │ runs in parallel
       ┌───────────┼────────────┐
       ▼           ▼            ▼
  ┌─────────┐ ┌────────┐ ┌──────────┐
  │Freshness│ │ Volume │ │Distribut.│  5 pure-function checks
  └─────────┘ └────────┘ └──────────┘
  ┌─────────┐ ┌─────────────────────┐
  │ Schema  │ │       Lineage       │
  └────┬────┘ └──────────┬──────────┘
       │                 │
       ▼                 ▼
  ┌──────────────────────────┐
  │   Anomaly Detection      │  Z-score · rolling average (14d)
  └────────────┬─────────────┘
               │ incident detected
               ▼
       ┌───────────────┐
       │   RCA Agent   │  ← Claude Sonnet (Agno)
       └───────┬───────┘
               │
       ┌───────┴────────┐
       ▼                ▼
 ┌───────────┐   ┌─────────────┐
 │ Snapshot  │   │Notifications│
 │Store(JSON)│   │ Slack/Email │
 └───────────┘   └─────────────┘
```

**Data flow:** SQLConnector → checks → anomaly scoring → RCA (LLM) → incident stored + alert sent.

---

## Key Technical Decisions

### 1. Pure functions for checks, not a class hierarchy
Each of the 5 pillars is a standalone function `check_X(connector, table) -> dict` returning a standardized result. No base class, no inheritance.

**Why:** Checks need to be testable in total isolation, composable without coupling, and easy to add without touching existing code. A class hierarchy would make mocking harder and force shared state between unrelated checks.

### 2. Z-score + rolling average over ARIMA or ML models
Anomaly detection uses statistical primitives (Z-score with σ threshold, 14-day rolling average) rather than autoregressive models.

**Why:** ARIMA requires training data, hyperparameter tuning, and fails silently when the series has gaps. Z-score is deterministic and explainable — when an alert fires, the reason is a number the engineer can verify in 10 seconds. ARIMA adds 6+ weeks of complexity for marginal gain at this data scale. The architecture makes it easy to swap in later.

### 3. JSON snapshot store over a dedicated time-series database
Historical baselines (null rates, row counts, schema snapshots) are stored in a local `.obs_snapshots.json` file via a thin wrapper.

**Why:** The observability layer must not itself depend on the database it monitors — the "who watches the watchmen" problem. A JSON file has zero infrastructure dependency, survives the monitored DB going down, and is trivially portable. The wrapper interface makes it swappable for SQLite or Redis later without touching check logic.

### 4. SQLAlchemy as the universal connector layer
All database interactions go through `SQLConnector`, which wraps SQLAlchemy's `Engine` and `Inspector`.

**Why:** Direct drivers (psycopg2, mysql-connector) would require a different code path per database. SQLAlchemy's unified dialect system means the same `execute_query()` call works on SQLite, Postgres, MySQL, and BigQuery. The connector also centralizes error handling — a single `try/except` boundary so a DB failure never propagates into check logic.

### 5. Claude Sonnet for RCA over rule-based analysis
When an anomaly is detected, a prompt combining incident data + lineage context + column metadata is sent to Claude Sonnet to generate a structured 5-step RCA.

**Why:** Rule-based RCA ("if null rate > 50% then check ETL job X") cannot generalize across table structures and business contexts. The LLM contextualizes heterogeneous signals (lineage, schema drift, distribution shift) into actionable reasoning in natural language — the output a data engineer would write after 20 minutes of investigation, in under 5 seconds.

---

## Features

- **5-pillar monitoring** — Freshness, Volume, Distribution, Schema, Lineage on any SQL table
- **Statistical anomaly detection** — Z-score and 14-day rolling average with configurable thresholds
- **AI-generated RCA** — Claude Sonnet produces a 5-step root cause analysis on every incident
- **Universal DB support** — SQLite, Postgres, MySQL, BigQuery via single connector interface
- **Graceful degradation** — every component fails silently; a DB error never crashes the pipeline

---

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| LLM / RCA | Claude Sonnet (Anthropic) | Long context, French/English, structured output |
| Agent orchestration | Agno framework | Lightweight, native multi-agent, minimal boilerplate |
| DB connector | SQLAlchemy 2.x | Single API for 10+ database dialects |
| Anomaly detection | pandas + scipy | Deterministic, no training data, explainable |
| UI | Streamlit | Prototype-to-production without frontend overhead |
| Deployment | Streamlit Community Cloud | Direct GitHub integration, free tier |
| Scheduling | APScheduler | Cron-like scheduling without Airflow's operational cost |
| Alerting | Slack webhook + smtplib | Zero-dependency notifications |

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/akhadirdia/data-observability-agent.git
cd data-observability-agent
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and DATABASE_URL

# 3. Run the Streamlit dashboard
streamlit run app.py
```

> **DATABASE_URL examples:**
> - SQLite (local): `sqlite:///./mydb.db`
> - Postgres: `postgresql://user:password@localhost:5432/dbname`

---

## Project Structure

```
data-observability-agent/
│
├── app.py                      # Streamlit UI — 3 tabs: Dashboard, Analyze, History
│
├── agents/
│   ├── monitor_agent.py        # Orchestrates all 5 checks per table
│   └── rca_agent.py            # Calls Claude Sonnet to generate RCA
│
├── checks/                     # One pure function per observability pillar
│   ├── freshness.py            # Time since last record vs. historical average
│   ├── volume.py               # Row count deviation from 14-day baseline
│   ├── distribution.py         # Null rates, zero rates, numeric stats
│   ├── schema.py               # Column add/remove/type change detection
│   └── lineage.py              # Upstream/downstream from lineage.yml
│
├── anomaly/
│   ├── zscore.py               # Z-score outlier detection
│   └── rolling.py              # Rolling average threshold detection
│
├── connectors/
│   └── sql_connector.py        # SQLAlchemy wrapper — connect, query, inspect
│
├── core/
│   ├── config.py               # pydantic-settings Settings + @lru_cache singleton
│   ├── snapshot_store.py       # JSON-based historical baseline store
│   └── incident_store.py       # SQLite incident log with TTD/TTR/ROI
│
├── notifications/
│   └── alerting.py             # Slack webhook + email alerts
│
├── prompts/
│   ├── rca_prompt.py           # RCA system prompt (versioned)
│   └── summary_prompt.py       # Daily digest prompt
│
├── tests/                      # pytest — all network calls mocked
│
├── lineage.yml                 # Declarative table dependency map
├── .env.example                # All required variables with comments
├── docker-compose.yml          # Optional Postgres test service
└── requirements.txt
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | From [console.anthropic.com](https://console.anthropic.com) |
| `DATABASE_URL` | Yes | SQLAlchemy connection string to the monitored DB |
| `SLACK_WEBHOOK_URL` | No | Incoming webhook for incident alerts |
| `ALERT_EMAIL` | No | Email address for incident notifications |
| `ENV` | No | `development` (default) or `production` |
| `CHECK_INTERVAL_MINUTES` | No | Auto-check frequency in minutes (default: 60) |

---

## Roadmap

1. **ARIMA-based seasonality detection** — replace the rolling average with a Holt-Winters model to handle weekly patterns (weekend volume dips, end-of-month spikes) without false positives
2. **dbt integration** — parse `manifest.json` to auto-populate `lineage.yml` from the dbt DAG, removing the manual declaration step
3. **Incident correlation** — when multiple tables alert simultaneously, group them into a single root incident with a shared RCA rather than N separate alerts
