# ALPHA Quant — Institutional Trading Platform

[![Phase](https://img.shields.io/badge/Phase-6%3A%20API%20%26%20Orchestration-gold.svg)](#)
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
- **Phase 4 (Deterministic Historical Backtesting Engine)**: Event-driven historical simulation engine with chronological event loop. Strict next-bar Open execution model preventing look-ahead fill bias. Explicit cost separation (Gross P&L, Maker/Taker fees, adverse slippage penalty, Net P&L). Strict portfolio ledger invariants ($\text{Equity}_t = \text{Cash}_t + \sum \text{PositionValue}_t$, $\Delta\text{Equity} = \text{GrossPnL} - \text{Fees} - \text{Slippage}$). Liquidity participation constraints (capped at $10\%$ of bar volume). Comprehensive validation framework: chronological train/validation/untouched holdout splits, rolling walk-forward evaluation, 4-regime classification (Bullish, Bearish, Choppy, High Volatility), passive buy-and-hold benchmark, no-trade baseline, and multi-scenario cost/latency stress testing (2x/5x fees, 3x slippage, severe stress, delayed execution by 1 bar). High-precision analytics persisted in TimescaleDB/PostgreSQL (`backtest_runs` & `backtest_trades`) and exposed via REST APIs and an institutional React frontend.
- **Phase 5 (Paper Execution & Central Risk Subsystem)**: Dedicated PaperBroker simulating spot execution without live trading capabilities. Strict pre-trade Central Risk Gate enforcing maximum order notional ($10,000), position concentration (10% of equity), aggregate exposure (80%), daily loss limits (2%), peak-to-trough drawdown limits (5%), consecutive loss streak halts, data-freshness guards (max 300s feed age), and spread/liquidity filters. Transactional atomicity for orders, fills, positions, and balance mutations with idempotent submissions (`client_order_id`). Emergency Stop kill switch with strict non-resetting restart recovery, operational ledger reconciliation, and institutional React control console (`/portfolio`).
- **Phase 6 (API & Lifecycle Orchestration)**: Enterprise lifecycle manager coordinating the complete 9-stage quantitative pipeline: (1) market data health, (2) feature pipeline readiness, (3) strategy scheduling, (4) signal validation, (5) Central Risk Gate, (6) paper order submission, (7) fill processing, (8) portfolio updates, and (9) event persistence. Explicit task ownership preventing duplicate scheduler executions with HTTP 409 conflict detection. Asynchronous background task queue for long-running backtests and heavy jobs. Real-time WebSocket telemetry streaming (`/api/v1/ws/live`) with handshake snapshots, ping/pong heartbeats, and REST fallback (`/api/v1/live/fallback`). Mandatory multi-dependency operational readiness probes (`/ready` requires both healthy database and responsive market data feed). Administrative authentication and authorization protecting mutating operations (`ADMIN_API_KEY`), and unified paginated REST endpoints (`/portfolio`, `/orders`, `/fills`, `/events`, `/risk/status`, `/paper-trading/*`, `/risk/reset`).


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
│   │   │   │   │   ├── strategies.py    # /api/v1/strategies, /run, /experiments
│   │   │   │   │   └── backtest.py      # /api/v1/backtests & /analytics/performance
│   │   │   │   └── router.py            # Central v1 routing table
│   │   │   └── deps.py                  # Database session dependency injection
│   │   ├── backtest/                    # Event-driven backtesting & simulation engine
│   │   │   ├── accounting.py            # Fixed-precision portfolio ledger & invariants
│   │   │   ├── analytics.py             # Sharpe, Sortino, Drawdown & bootstrap CIs
│   │   │   ├── constants.py             # Annualization constants, fees, benchmarks
│   │   │   ├── cost_model.py            # Adverse slippage, fee schedules & liquidity caps
│   │   │   ├── engine.py                # Chronological event loop & stress runner
│   │   │   ├── exceptions.py            # Backtest domain exceptions
│   │   │   ├── execution.py             # Next-bar Open fills & limit order simulation
│   │   │   ├── schemas.py               # Pydantic schemas for backtest runs & trades
│   │   │   ├── service.py               # Backtest persistence & analytics service
│   │   │   └── validation.py            # Chronological splits, holdout & walk-forward generator
│   │   ├── paper/                       # Dedicated paper execution & central risk engine
│   │   │   ├── broker.py                # Simulated spot broker, fills, & reconciliation
│   │   │   ├── constants.py             # Default risk limits, fees, order states
│   │   │   ├── exceptions.py            # Risk breach, balance, and invariant exceptions
│   │   │   ├── risk_gate.py             # Central Pre-Trade Risk Gate & limit reset logic
│   │   │   ├── schemas.py               # Pydantic schemas for orders, accounts, risk status
│   │   │   └── service.py               # Paper trading application orchestration service
│   │   ├── cli/
│   │   │   ├── ingest.py                # Public market data historical ingestion CLI
│   │   │   ├── run_strategy.py          # Strategy experiment execution & signal generation CLI
│   │   │   ├── run_backtest.py          # Event-driven historical backtesting CLI
│   │   │   └── run_paper.py             # Paper execution & risk operations CLI
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
│   │   │   ├── backtest.py              # BacktestRun & BacktestTradeLog models
│   │   │   ├── paper.py                 # PaperAccount, Order, Fill, Position, Risk models
│   │   │   └── system.py                # SystemAuditLog model
│   │   ├── schemas/
│   │   │   └── health.py                # Health & readiness validation schemas
│   │   └── main.py                      # Application factory & lifespan manager
│   ├── alembic/
│   │   ├── versions/
│   │   │   ├── 0001_initial_schema.py   # Baseline system audit schema
│   │   │   ├── 0002_market_candles_schema.py # TimescaleDB hypertable candles schema
│   │   │   ├── 0003_strategy_experiments_schema.py # Experiment ledger & signals schema
│   │   │   ├── 0004_backtest_schema.py  # Backtest runs & trades persistent schema
│   │   │   └── 0005_paper_execution_schema.py # Paper trading & risk management schema
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
│   │   ├── test_backtest_execution.py   # Event-driven next-bar fills, fees & slippage tests
│   │   ├── test_backtest_validation.py  # Splits, holdouts, walk-forward & regimes tests
│   │   ├── test_backtest_api.py         # Backtest simulation & performance REST API tests
│   │   ├── test_paper_broker.py         # PaperBroker execution, balances, partial fills tests
│   │   ├── test_paper_risk.py           # CentralRiskGate, limits, and invariant safety tests
│   │   ├── test_paper_api.py            # Paper trading and risk management REST API tests
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
    │   │   ├── StrategiesPage.tsx       # Quantitative strategies & experiment ledger
    │   │   ├── BacktestPage.tsx         # Historical backtest engine & stress test UI
    │   │   ├── SystemHealthPage.tsx     # Real-time health diagnostic dashboard
    │   │   └── NotFoundPage.tsx         # 404 handler
    │   ├── services/
    │   │   └── api.ts                   # Typed API service client
    │   ├── types/
    │   │   └── index.ts                 # Strict TypeScript interface contracts
    │   ├── App.tsx                      # Client router with /market-data & /backtests
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

## 📈 Event-Driven Backtesting Simulation CLI

ALPHA Quant provides a high-fidelity event-driven historical simulation CLI with configurable capital, maker/taker fee schedules, adverse slippage penalties, liquidity limits, and automated stress testing:

```powershell
cd backend
# Run Trend Following backtest with default cost schedule and stress tests:
$env:DATABASE_URL="sqlite+aiosqlite:///alpha_quant.db"
.venv\Scripts\python app\cli\run_backtest.py --strategy trend_following --symbol BTCUSDT --interval 1m

# Run Mean Reversion backtest with custom fee schedules and slippage:
.venv\Scripts\python app\cli\run_backtest.py --strategy mean_reversion --symbol BTCUSDT --interval 1m --initial-cash 25000 --taker-fee-bps 7.5 --slippage-bps 4.0

# Run Momentum backtest and export detailed JSON execution report:
.venv\Scripts\python app\cli\run_backtest.py --strategy momentum --symbol BTCUSDT --interval 1m --output-json backtest_results.json
```

---

## 🛡️ Paper Execution & Central Risk Operations CLI

ALPHA Quant includes a dedicated CLI for inspecting virtual paper accounts, evaluating pre-trade risk controls, submitting simulated orders, and executing emergency halts:

```powershell
cd backend
# Inspect virtual cash, positions, unrealized P&L, and Central Risk Gate status:
$env:DATABASE_URL="sqlite+aiosqlite:///alpha_quant.db"
.venv\Scripts\python app\cli\run_paper.py --action status --symbol BTCUSDT

# Submit a simulated BUY market order through the Central Risk Gate:
.venv\Scripts\python app\cli\run_paper.py --action order --side buy --type market --quantity 0.01 --symbol BTCUSDT

# Trigger an emergency stop to halt all new simulated entries:
.venv\Scripts\python app\cli\run_paper.py --action emergency-stop --reason "Manual risk test"

# Clear emergency stop and resume simulated trading:
.venv\Scripts\python app\cli\run_paper.py --action resume --confirmation CONFIRM_RESUME

# Perform ledger reconciliation:
.venv\Scripts\python app\cli\run_paper.py --action reconcile --symbol BTCUSDT
```

---

## 🧪 Verification & Testing Commands

### Backend Automated Test Suite
Run all 94 automated tests (paper broker execution, risk gate invariants, live trading safety, insufficient balances, partial fills, event-driven next-bar fills, adverse slippage, ledger invariants, liquidity constraints, train/validation/holdout splits, walk-forward generator, market regimes, feature formulas, look-ahead prevention, strategies, REST/WS adapters, database idempotency, and API endpoints):
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
| `POST` | `/api/v1/backtests` | Launch Backtest | Runs deterministic event-driven backtest; supports `?async_mode=true` queue. (Protected) |
| `GET` | `/api/v1/backtests` | List Backtests | Queries historical backtest runs filtered by strategy or symbol. |
| `GET` | `/api/v1/backtests/{id}` | Backtest Details | Returns full equity curve snapshots, fill logs, and stress scenario results. |
| `GET` | `/api/v1/analytics/performance` | Performance Analytics | Computes aggregated Sharpe, Drawdown, and return metrics across backtests. |
| `GET` | `/api/v1/portfolio` | Unified Portfolio Overview | Virtual cash balance, positions, cost basis, exposure %, and P&L. |
| `GET` | `/api/v1/orders` | Paginated Orders Ledger | Paginated orders with status, symbol, side, limit, and offset filtering. |
| `GET` | `/api/v1/fills` | Paginated Fills Ledger | Paginated execution fills with prices, adverse slippage, and fee breakdowns. |
| `GET` | `/api/v1/risk/status` | Central Risk Gate Telemetry | Live telemetry for drawdown, daily loss limit, feed health, and emergency stop. |
| `GET` | `/api/v1/events` | Paginated System Events | Paginated audit trail of risk breaches, emergency pauses, and lifecycle transitions. |
| `POST` | `/api/v1/paper-trading/start` | Start Paper Trading | Initiates automated 9-stage lifecycle scheduler loop with task ownership. (Protected) |
| `POST` | `/api/v1/paper-trading/stop` | Stop Paper Trading | Gracefully halts automated paper loop and drains running tasks. (Protected) |
| `GET` | `/api/v1/paper-trading/status` | Orchestrator Telemetry | Operational stats: status, task ID, worker ID, cycles, signals, and orders. |
| `POST` | `/api/v1/risk/reset` | Operator Risk Reset | Authorizes reset of tripped controls using confirmation token `CONFIRM_RESET`. (Protected) |
| `GET` | `/api/v1/tasks/{task_id}` | Background Task Status | Queries status and result of asynchronous background backtest simulations. |
| `WS` | `/api/v1/ws/live` | WebSocket Live Stream | Real-time telemetry feed delivering snapshots, ticks, cycle logs, and alerts. |
| `GET` | `/api/v1/live/fallback` | Live REST Fallback | Polling fallback for clients unable to maintain persistent WebSocket streams. |

---

## 🛡️ Phase 6 Acceptance Criteria Checklist

- [x] **API Endpoints Finalized**:
  - `GET /health` and `/ready` with multi-dependency validation.
  - `GET /api/v1/market/candles` and `GET /api/v1/market/status`.
  - `GET /api/v1/strategies`.
  - `POST /api/v1/backtests` (sync and background async modes) and `GET /api/v1/backtests/{run_id}`.
  - `GET /api/v1/portfolio` (unified simulated portfolio overview).
  - `GET /api/v1/orders` (paginated simulated orders ledger).
  - `GET /api/v1/fills` (paginated simulated fills ledger).
  - `GET /api/v1/analytics/performance` (aggregated performance metrics).
  - `GET /api/v1/risk/status` (Central Risk Gate telemetry and thresholds).
  - `GET /api/v1/events` (paginated system and risk audit log).
  - `POST /api/v1/paper-trading/start` and `POST /api/v1/paper-trading/stop` (orchestrator lifecycle controls).
  - `POST /api/v1/risk/reset` (operator authorized risk control reset).
- [x] **Authentication & Authorization**:
  - Mutating operations (`POST /backtests`, `/paper-trading/start`, `/paper-trading/stop`, `/risk/reset`, `/paper/orders`, `/paper/risk/*`) protected by `verify_admin_key`.
  - Supports `X-API-Key` header and `Authorization: Bearer <token>`.
  - Rejects unauthenticated/unauthorized mutating requests with HTTP 401.
- [x] **9-Stage Orchestration Lifecycle Manager**:
  - Coordinates (1) market data health, (2) feature readiness, (3) strategy scheduling, (4) signal validation, (5) risk checks, (6) paper order submission, (7) fill processing, (8) portfolio updates, and (9) event persistence.
  - Explicit task ownership with unique `worker_id` and `task_id`.
  - Duplicate scheduler prevention returning HTTP 409 Conflict.
- [x] **Background Task Queue**:
  - `BackgroundTaskManager` executes long-running backtest simulations asynchronously (`?async_mode=true`).
  - Queryable via `GET /api/v1/tasks/{task_id}` with status and progress tracking.
- [x] **Live Updates Streaming**:
  - WebSocket streaming endpoint `/api/v1/ws/live` with handshake snapshot, ping/pong keepalives, and reconnection support.
  - REST fallback `/api/v1/live/fallback` for clients without persistent socket support.
- [x] **Operational Reliability**:
  - Readiness probe `/ready` rejects traffic (HTTP 503 `not_ready`) if database OR market data feed is down.
  - Graceful shutdown drains lifecycle tasks, closes live WebSockets, and releases database connections.
  - Startup recovery preserves persisted risk controls across server restarts.
- [x] **Strict Paper-Only Trading Guarantee**:
  - Zero live exchange trading capabilities.
  - Storage or request of exchange API credentials strictly prohibited.
  - `is_live=True` rejected with 422 Unprocessable Entity.
- [x] **All tests pass**:
  - **108/108** automated unit, integration, and API tests pass in 13.33s.
  - Frontend TypeScript compiles in strict mode with 0 errors.
  - Frontend production build compiles in 1.95s.


