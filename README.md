# ALPHA Quant — Institutional Trading Platform

[![Phase](https://img.shields.io/badge/Phase-3%3A%20Quantitative%20Strategies-gold.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-emerald.svg)](#)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)](#)
[![TypeScript](https://img.shields.io/badge/TypeScript-Strict%20Mode-blue.svg)](#)
[![Database](https://img.shields.io/badge/Database-TimescaleDB%20%2F%20Postgres-336791.svg)](#)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](#)

---

## 🏛️ Platform Architecture Overview

**ALPHA Quant** is an enterprise-scale quantitative intelligence, algorithmic factor modeling, and trading execution platform designed for institutional workflows.

- **Phase 1 (Foundation)**: Monorepo architecture, FastAPI application factory, lifespan management, structured JSON logging, central RFC-compliant exception handling, TimescaleDB / PostgreSQL persistence, Alembic migrations, and React strict mode shell.
- **Phase 2 (Market Data Subsystem)**: Binance Spot public market data adapter, historical REST OHLCV ingestion (1m, 5m, 15m), live WebSocket streaming with automatic reconnects and exponential backoff jitter, strict price/volume/timestamp integrity validation, separate exchange and ingestion UTC timestamps, open vs. finalized candle distinction, database constraints preventing duplicates, sequence gap detection, rate-limited REST backfills, restart recovery, and live telemetry endpoints.
- **Phase 3 (Quantitative Strategies & Research Pipeline)**: Mathematical feature engineering pipeline (SMA, EMA, simple and logarithmic returns, rolling volatility, rolling z-score, ATR, volume statistics, multi-period momentum, and graceful order-book imbalance handling). Zero-lookahead bias enforcement and incomplete candle rejection. Typed non-executing strategy interface returning immutable auditable Signals. Three baseline long-only spot research strategies (Trend Following, Mean Reversion, Volatility-Normalized Momentum with transaction cost hurdles). Cryptographic dataset fingerprinting (SHA-256) and persistent experiment ledger tracking (`strategy_experiments` and `strategy_signals`).

---

## 📂 Monorepo Structure

```
Alpha Quant/
├── .env.example              # Canonical environment template (zero committed secrets)
├── .gitignore                # Comprehensive ignore rules (secrets, venvs, builds)
├── docker-compose.yml        # Multi-service stack (TimescaleDB, Backend, Frontend)
├── README.md                 # Complete operational runbook and verification manual
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── health.py        # /api/v1/health & /readiness
│   │   │   │   │   ├── system.py        # /api/v1/system/status & audit-logs
│   │   │   │   │   ├── market.py        # /api/v1/market/candles, /status, /backfill
│   │   │   │   │   └── strategies.py    # /api/v1/strategies, /run, /experiments
│   │   │   │   └── router.py            # Central v1 routing table
│   │   │   └── deps.py                  # Database session dependency injection
│   │   ├── cli/
│   │   │   ├── ingest.py                # Public market data historical ingestion CLI
│   │   │   └── run_strategy.py          # Strategy experiment execution & signal generation CLI
│   │   ├── core/
│   │   │   ├── config.py                # Pydantic Settings & environment validation
│   │   │   ├── exceptions.py            # Central domain exceptions
│   │   │   ├── handlers.py              # Global exception handlers (JSON formatted)
│   │   │   └── logging.py               # Structlog structured logging engine
│   │   ├── db/
│   │   │   ├── base.py                  # SQLAlchemy 2.x DeclarativeBase & Mixins
│   │   │   └── session.py               # Async engine, sessionmaker & health checks
│   │   ├── market/
│   │   │   ├── backoff.py               # Exponential backoff with full jitter
│   │   │   ├── cli.py                   # Ingestion CLI implementation
│   │   │   ├── constants.py             # Supported intervals (1m, 5m, 15m) & symbol helpers
│   │   │   ├── exceptions.py            # Market data domain exceptions
│   │   │   ├── models.py                # Re-export of MarketCandle
│   │   │   ├── rate_limiter.py          # Sliding window 1200 weight/min REST rate limiter
│   │   │   ├── rest_adapter.py          # Binance Spot public REST client
│   │   │   ├── schemas.py               # Pydantic validation schemas
│   │   │   ├── service.py               # Upsert, gap detection, backfill & restart recovery
│   │   │   ├── tracker.py               # In-memory metrics & feed status telemetry
│   │   │   ├── validator.py             # OHLCV, sequence & gap integrity validator
│   │   │   └── ws_adapter.py            # Public WebSocket client with auto-reconnect
│   │   ├── quant/
│   │   │   ├── constants.py             # Strategy IDs, SignalSide enum, baseline parameters
│   │   │   ├── exceptions.py            # Quantitative domain exceptions
│   │   │   ├── features/                # Mathematical feature engineering pipeline
│   │   │   │   ├── atr.py               # Average True Range & True Range
│   │   │   │   ├── metadata.py          # Feature documentation registry
│   │   │   │   ├── momentum.py          # Multi-period momentum
│   │   │   │   ├── moving_averages.py   # SMA and EMA
│   │   │   │   ├── orderbook.py         # Spread & order-book imbalance
│   │   │   │   ├── pipeline.py          # FeaturePipeline orchestrator & lookahead prevention
│   │   │   │   ├── returns.py           # Simple & logarithmic returns
│   │   │   │   ├── volatility.py        # Rolling return volatility
│   │   │   │   ├── volume.py            # Volume SMA, ratio, and z-score
│   │   │   │   └── zscores.py           # Rolling z-scores
│   │   │   ├── strategy/                # BaseStrategy & Baseline research implementations
│   │   │   │   ├── base.py              # Signal dataclass & BaseStrategy ABC
│   │   │   │   ├── trend_following.py   # Dual SMA + Volatility filter
│   │   │   │   ├── mean_reversion.py    # Rolling Z-score + Regime filter
│   │   │   │   └── momentum.py          # Vol-normalized momentum + Transaction cost hurdle
│   │   │   ├── experiments/             # Experiment tracking & fingerprinting
│   │   │   │   └── tracker.py           # ExperimentService & SHA-256 fingerprinting
│   │   │   └── schemas.py               # Pydantic schemas for strategies & experiments
│   │   ├── models/
│   │   │   ├── base.py                  # Model registry
│   │   │   ├── market.py                # TimescaleDB MarketCandle model
│   │   │   ├── strategy.py              # StrategyExperiment & StrategySignal models
│   │   │   └── system.py                # SystemAuditLog model
│   │   ├── schemas/
│   │   │   └── health.py                # Health & readiness validation schemas
│   │   └── main.py                      # Application factory & lifespan manager
│   ├── alembic/
│   │   ├── versions/
│   │   │   ├── 0001_initial_schema.py   # Baseline system audit schema
│   │   │   ├── 0002_market_candles_schema.py # TimescaleDB hypertable candles schema
│   │   │   └── 0003_strategy_experiments_schema.py # Experiment ledger & signals schema
│   │   ├── env.py                       # Alembic migration runner
│   │   └── script.py.mako
│   ├── tests/
│   │   ├── conftest.py                  # Isolated async test engine & fixtures
│   │   ├── test_config.py               # Settings and configuration validation tests
│   │   ├── test_db.py                   # Live connection probe & CRUD tests
│   │   ├── test_exceptions.py           # Domain exception & 422 validation tests
│   │   ├── test_health.py               # Liveness & readiness probe tests
│   │   ├── test_market_api.py           # Market REST API endpoints tests
│   │   ├── test_market_rest.py          # Deterministic REST mock tests
│   │   ├── test_market_service_db.py    # Idempotent upsert & gap tests
│   │   ├── test_market_validator.py     # OHLCV integrity & sequence tests
│   │   ├── test_market_ws.py            # WebSocket parsing & backoff tests
│   │   ├── test_quant_api.py            # Quantitative strategy endpoints tests
│   │   ├── test_quant_features.py       # Mathematical feature formulas & lookahead prevention
│   │   ├── test_quant_strategies.py     # Deterministic signal generation & reproducibility
│   │   └── test_system.py               # Status diagnostics & honest empty state tests
│   ├── alembic.ini                      # Migration configuration
│   ├── Dockerfile                       # Multi-stage production container spec
│   ├── pyproject.toml                   # Project metadata and pytest configuration
│   └── requirements.txt                 # Pinned Python dependencies
└── frontend/
    ├── public/
    │   ├── favicon.ico
    │   └── logo.svg                     # Vector black-and-gold ALPHA emblem
    ├── src/
    │   ├── components/
    │   │   ├── common/
    │   │   │   ├── EmptyState.tsx       # Honest empty state component
    │   │   │   ├── HealthBadge.tsx      # Subsystem health indicator badge
    │   │   │   └── Logo.tsx             # Institutional black & gold logo
    │   │   └── layout/
    │   │       ├── AppHeader.tsx        # Top status bar with UTC clock & live badge
    │   │       ├── AppSidebar.tsx       # Collapsible navigation sidebar
    │   │       └── AppShell.tsx         # Master layout container
    │   ├── pages/
    │   │   ├── DashboardPage.tsx        # System overview & infrastructure status
    │   │   ├── MarketDataPage.tsx       # Live market feed & historical candles explorer
    │   │   ├── PortfolioPage.tsx        # Portfolio empty state (Phase 2 preview)
    │   │   ├── StrategiesPage.tsx       # Strategies empty state (Phase 3 preview)
    │   │   ├── SystemHealthPage.tsx     # Real-time health diagnostic dashboard
    │   │   └── NotFoundPage.tsx         # 404 handler
    │   ├── services/
    │   │   └── api.ts                   # Typed API service client
    │   ├── types/
    │   │   └── index.ts                 # Strict TypeScript interface contracts
    │   ├── App.tsx                      # Client router with /market-data
    │   ├── index.css                    # Tailwind directives and custom scrollbars
    │   └── main.tsx                     # React DOM entry
    ├── Dockerfile                       # Production Nginx container
    ├── nginx.conf                       # Production reverse proxy config
    ├── package.json                     # Pinned node dependencies
    ├── tailwind.config.js               # Black & gold color palette definition
    ├── tsconfig.json                    # Strict mode TypeScript configuration
    └── vite.config.ts                   # Fast Vite bundler and API proxy
```

---

## ⚡ Prerequisites

- **Python**: 3.11 or higher
- **Node.js**: v20 or higher (`npm` v10+)
- **Docker & Docker Compose**: Recommended for local TimescaleDB containerization

---

## 🚀 Setup & Execution Guide

### 1. Environment Configuration

```powershell
Copy-Item .env.example .env
```
*(The `.gitignore` strictly protects `.env` from accidental commits).*

### 2. Infrastructure via Docker Compose

```powershell
docker-compose up -d timescaledb
```

### 3. Backend Setup & Migrations

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\alembic upgrade head
```

#### Launch Backend Server
```powershell
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- Interactive OpenAPI Swagger Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Root Health: [http://localhost:8000/health](http://localhost:8000/health)
- Market Candles: [http://localhost:8000/api/v1/market/candles?symbol=BTCUSDT&interval=1m](http://localhost:8000/api/v1/market/candles?symbol=BTCUSDT&interval=1m)
- Market Feed Status: [http://localhost:8000/api/v1/market/status?symbol=BTCUSDT&interval=1m](http://localhost:8000/api/v1/market/status?symbol=BTCUSDT&interval=1m)

---

## 📈 Market Data Ingestion CLI

ALPHA Quant provides a dedicated CLI command to download real public historical OHLCV candles from Binance Spot with zero API keys:

```powershell
cd backend
# Download historical 1m candles for BTC/USDT over a specified date range:
.venv\Scripts\python -m app.market.cli --symbol BTCUSDT --interval 1m --start 2026-10-10 --end 2026-10-11

# Download 5m candles and immediately start live WebSocket streaming:
.venv\Scripts\python -m app.market.cli --symbol BTCUSDT --interval 5m --start 2026-10-01 --stream

# Ingestion command alias:
.venv\Scripts\python -m app.cli.ingest --symbol BTCUSDT --interval 15m --start 2026-10-01
```

---

## 🧪 Verification & Testing Commands

### Backend Automated Test Suite
Run all 42 automated tests (unit, integration, REST mock, WebSocket mock, validator, and DB upsert tests):
```powershell
cd backend
.venv\Scripts\pytest
```

### Frontend TypeScript Strict Type-Checking
Validate that the entire frontend conforms to TypeScript strict mode:
```powershell
cd frontend
npm run typecheck
```

### Frontend Production Build
Verify production bundle compilation:
```powershell
cd frontend
npm run build
```

---

## ⚗️ Quantitative Strategy Experiment Runner CLI

ALPHA Quant provides a dedicated CLI tool to execute strategies on validated historical candles, record cryptographic dataset fingerprints, and persist auditable non-executing signals:

```powershell
cd backend
# Run Trend Following (Dual SMA + Volatility Filter) on 151 stored candles:
.venv\Scripts\python -m app.cli.run_strategy --strategy trend_following --symbol BTCUSDT --interval 1m --limit 151

# Run Mean Reversion (Rolling Z-Score + Regime Filter) on stored candles:
.venv\Scripts\python -m app.cli.run_strategy --strategy mean_reversion --symbol BTCUSDT --interval 1m --limit 151

# Run Volatility-Normalized Momentum with transaction cost hurdle verification:
.venv\Scripts\python -m app.cli.run_strategy --strategy momentum --symbol BTCUSDT --interval 1m --limit 151

# Run with custom parameters and export experiment JSON report:
.venv\Scripts\python -m app.cli.run_strategy --strategy trend_following --symbol BTCUSDT --interval 1m --fast-window 15 --slow-window 80 --output-json experiment_report.json
```

---

## 🧪 Verification & Testing Commands

### Backend Automated Test Suite
Run all 63 automated tests (feature formulas, warm-up periods, timestamp alignment, look-ahead bias prevention, baseline strategies, reproducibility, REST/WS mocks, database upserts, and API endpoints):
```powershell
cd backend
.venv\Scripts\pytest -v
```

### Frontend TypeScript Strict Type-Checking
Validate that the entire frontend conforms to TypeScript strict mode:
```powershell
cd frontend
npm run typecheck
```

### Frontend Production Build
Verify production bundle compilation:
```powershell
cd frontend
npm run build
```

---

## 📡 API Endpoints Reference

| Method | Path | Summary | Description |
|---|---|---|---|
| `GET` | `/health` | Root Liveness | Asserts worker process is responsive (200 OK). |
| `GET` | `/ready` | Root Readiness | Verifies live database pool connectivity (`SELECT 1`). |
| `GET` | `/api/v1/health` | API v1 Liveness | Versioned liveness probe. |
| `GET` | `/api/v1/system/status` | System Status | Comprehensive uptime, dialect, and database latency. |
| `GET` | `/api/v1/market/candles` | Market Candles | Queries stored OHLCV candles with interval and time filters. |
| `GET` | `/api/v1/market/status` | Feed Health | Returns live WebSocket feed state, message rates, and gaps. |
| `POST` | `/api/v1/market/backfill` | REST Backfill | Triggers rate-limited historical gap backfill. |
| `GET` | `/api/v1/strategies` | Strategy Registry | Lists baseline strategies, candidate parameters, and feature requirements. |
| `POST` | `/api/v1/strategies/run` | Execute Experiment | Evaluates strategy on stored candles, computes features, and persists signals. |
| `GET` | `/api/v1/strategies/experiments` | Experiment Ledger | Queries historical recorded experiments with dataset fingerprints. |
| `GET` | `/api/v1/strategies/experiments/{id}` | Experiment Details | Returns complete experiment metadata and individual auditable signals. |

---

## 🛡️ Phase 3 Acceptance Criteria Checklist

- [x] **Feature engineering pipeline**: Implemented tested functions for SMA, EMA, simple and logarithmic returns, rolling volatility, rolling z-scores, ATR, volume statistics, multi-period momentum, and graceful order-book imbalance handling.
- [x] **Explicit formulas, lookback & warm-up documentation**: Every feature documents its exact formula, lookback, warm-up period, and timestamp alignment in docstrings and registry metadata.
- [x] **Zero look-ahead bias enforcement**: Look-ahead prevention test mathematically proves that mutating future observations does not alter features or signals at time $t$.
- [x] **Incomplete candle rejection**: Open candles (`is_closed=False`) are strictly filtered/rejected so unfinalized observations never pollute historical features.
- [x] **Common typed Strategy interface**: Returns immutable, auditable `Signal` containing `strategy_id`, `version`, `decision_timestamp`, `symbol`, `side` (buy/sell/hold), `signal_score`, `reference_price`, `reason`, `relevant_features`, and `config_id`.
- [x] **Strict zero-execution guarantee**: Strategies generate mathematical decision signals and never place orders or modify balances.
- [x] **Three baseline strategies**:
  - **Trend following**: Candidate moving average windows (20, 100), volatility filter, and explicit exit conditions.
  - **Mean reversion**: Candidate 60-candle lookback, absolute z-score threshold (2.0), regime filter, and explicit exits.
  - **Momentum**: Configurable multi-period returns, volatility normalization, and transaction cost hurdle verification.
- [x] **Cryptographic experiment tracking**: Persists strategy version, parameters, dataset SHA-256 fingerprint, time range, feature definitions, and signal timestamps in `strategy_experiments` and `strategy_signals`.
- [x] **Auditable and reproducible**: Outputs can be reproduced identically on real stored data and deterministic synthetic fixtures.
- [x] **All tests pass**: 63/63 automated backend tests pass, frontend strict typecheck passes, production build succeeds.
