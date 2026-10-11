# ALPHA Quant — Institutional Trading Platform

[![Phase](https://img.shields.io/badge/Phase-2%3A%20Market%20Data-gold.svg)](#)
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
│   │   │   │   │   └── market.py        # /api/v1/market/candles, /status, /backfill
│   │   │   │   └── router.py            # Central v1 routing table
│   │   │   └── deps.py                  # Database session dependency injection
│   │   ├── cli/
│   │   │   └── ingest.py                # CLI runner entrypoint
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
│   │   ├── models/
│   │   │   ├── base.py                  # Model registry
│   │   │   ├── market.py                # TimescaleDB MarketCandle model
│   │   │   └── system.py                # SystemAuditLog model
│   │   ├── schemas/
│   │   │   └── health.py                # Health & readiness validation schemas
│   │   └── main.py                      # Application factory & lifespan manager
│   ├── alembic/
│   │   ├── versions/
│   │   │   ├── 0001_initial_schema.py   # Baseline system audit schema
│   │   │   └── 0002_market_candles_schema.py # TimescaleDB hypertable candles schema
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

---

## 🛡️ Phase 2 Acceptance Criteria Checklist

- [x] **Real public historical candles can be downloaded**: Verified directly against Binance Spot REST endpoint.
- [x] **Live public market updates can be ingested**: Binance Spot WebSocket stream with automatic reconnects and exponential backoff with jitter.
- [x] **Candle data persists across restarts**: TimescaleDB `market_candles` schema stores candles with time-series indexes.
- [x] **Duplicate candles are rejected or safely ignored**: Unique constraint `(symbol, interval, open_time)` and idempotent upsert logic.
- [x] **Missing data is detected and reported**: Gap detection algorithm computes exact missing ranges without synthetic fabrication.
- [x] **Health endpoints reflect actual feed status**: `/api/v1/market/status` reports real-time feed states and diagnostics.
- [x] **No exchange API keys are required**: 100% public endpoints.
- [x] **All relevant tests pass**: 42 automated tests pass with 100% success rate.
