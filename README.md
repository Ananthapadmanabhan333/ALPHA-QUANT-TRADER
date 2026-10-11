# ALPHA Quant — Institutional Trading Platform

[![Phase](https://img.shields.io/badge/Phase-1%3A%20Foundation-gold.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-emerald.svg)](#)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)](#)
[![TypeScript](https://img.shields.io/badge/TypeScript-Strict%20Mode-blue.svg)](#)
[![Database](https://img.shields.io/badge/Database-TimescaleDB%20%2F%20Postgres-336791.svg)](#)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](#)

---

## 🏛️ Phase 1: Foundation Overview

**ALPHA Quant** is an enterprise-scale quantitative intelligence, algorithmic factor modeling, and trading execution platform designed for institutional workflows. 

**Phase 1** establishes the mission-critical foundation:
- Robust, reproducible **monorepo architecture**.
- Production-grade **FastAPI backend** with application factory, lifespan management, structured JSON logging, central RFC-compliant exception handling, and versioned `/api/v1` routing.
- **SQLAlchemy 2.x async engine** paired with **Alembic migration versioning** targeted at PostgreSQL and TimescaleDB hypertables.
- **Service health checks**, readiness probes, persistent volume storage, and graceful shutdown lifecycle hooks.
- **Cinematic React + Vite frontend** operating in **TypeScript strict mode**, featuring Tailwind CSS, institutional black-and-gold styling, basic routing, and honest empty states.
- **Strict Zero-Synthetic Data Policy**: No fabricated trading metrics, no mocked profit tickers, and no fake live endpoints.

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
│   │   │   │   │   └── system.py        # /api/v1/system/status & audit-logs
│   │   │   │   └── router.py            # Central v1 routing table
│   │   │   └── deps.py                  # Database session dependency injection
│   │   ├── core/
│   │   │   ├── config.py                # Pydantic Settings & environment validation
│   │   │   ├── exceptions.py            # Central domain exceptions
│   │   │   ├── handlers.py              # Global exception handlers (JSON formatted)
│   │   │   └── logging.py               # Structlog structured logging engine
│   │   ├── db/
│   │   │   ├── base.py                  # SQLAlchemy 2.x DeclarativeBase & Mixins
│   │   │   └── session.py               # Async engine, sessionmaker & health checks
│   │   ├── models/
│   │   │   ├── base.py                  # Model registry
│   │   │   └── system.py                # SystemAuditLog database model
│   │   ├── schemas/
│   │   │   └── health.py                # Pydantic validation schemas
│   │   └── main.py                      # Application factory & lifespan manager
│   ├── alembic/
│   │   ├── versions/
│   │   │   └── 0001_initial_schema.py   # Baseline schema migration
│   │   ├── env.py                       # Alembic migration runner
│   │   └── script.py.mako
│   ├── tests/
│   │   ├── conftest.py                  # Isolated async test engine & fixtures
│   │   ├── test_config.py               # Settings and configuration validation tests
│   │   ├── test_db.py                   # Live connection probe & CRUD tests
│   │   ├── test_exceptions.py           # Domain exception & 422 validation tests
│   │   ├── test_health.py               # Liveness & readiness probe tests
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
    │   │   ├── PortfolioPage.tsx        # Portfolio empty state (Phase 2 preview)
    │   │   ├── StrategiesPage.tsx       # Strategies empty state (Phase 3 preview)
    │   │   ├── SystemHealthPage.tsx     # Real-time health diagnostic dashboard
    │   │   └── NotFoundPage.tsx         # 404 handler
    │   ├── services/
    │   │   └── api.ts                   # Typed API service client
    │   ├── types/
    │   │   └── index.ts                 # Strict TypeScript interface contracts
    │   ├── App.tsx                      # Client router
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

Copy the example configuration to create your local `.env`:
```powershell
Copy-Item .env.example .env
```
*(The `.gitignore` strictly protects `.env` from accidental commits).*

### 2. Infrastructure via Docker Compose (Recommended)

Start the persistent TimescaleDB database container:
```powershell
docker-compose up -d timescaledb
```

To run the complete stack (TimescaleDB + Backend + Frontend):
```powershell
docker-compose up --build -d
```

### 3. Backend Setup & Local Execution

Create the Python virtual environment and install pinned dependencies:
```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

#### Run Database Migrations
Apply Alembic migrations to update the database to the head revision:
```powershell
.venv\Scripts\alembic upgrade head
```

#### Launch Backend Server
Start the FastAPI server via Uvicorn:
```powershell
.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Interactive Swagger Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Root Health Probe: [http://localhost:8000/health](http://localhost:8000/health)
- Root Readiness Probe: [http://localhost:8000/ready](http://localhost:8000/ready)
- Versioned System Status: [http://localhost:8000/api/v1/system/status](http://localhost:8000/api/v1/system/status)

### 4. Frontend Setup & Local Execution

Navigate to the frontend directory and install dependencies:
```powershell
cd frontend
npm install
```

#### Launch Vite Development Server
```powershell
npm run dev
```
The application shell will be accessible at: [http://localhost:5173](http://localhost:5173)

---

## 🧪 Verification & Testing Commands

### Backend Automated Test Suite
Run all unit, configuration, exception, and API integration tests:
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
| `GET` | `/` | Root Information | Returns service name, version, status, and API routes. |
| `GET` | `/health` | Root Liveness Probe | Confirms worker process responsiveness (200 OK). |
| `GET` | `/ready` | Root Readiness Probe | Verifies live database pool connectivity (`SELECT 1`). |
| `GET` | `/api/v1/health` | API v1 Liveness | Versioned liveness check. |
| `GET` | `/api/v1/health/readiness` | API v1 Readiness | Versioned database readiness verification. |
| `GET` | `/api/v1/system/status` | System Status | Comprehensive uptime, dialect, and database latency. |
| `GET` | `/api/v1/system/audit-logs` | System Audit Trail | Honest audit logs (empty array until real events logged). |

---

## 🛡️ Phase 1 Acceptance Criteria Checklist

- [x] **Backend starts**: FastAPI application factory initializes cleanly with lifespan management.
- [x] **Frontend starts**: React 18 + Vite development server serves the branded shell on `:5173`.
- [x] **Database becomes healthy**: Connection pooling and async probe verify query readiness.
- [x] **Database migrations apply successfully**: Alembic revision `0001_initial_schema` creates tables with indexes.
- [x] **Health endpoints work**: `/health`, `/ready`, `/api/v1/health`, and `/api/v1/system/status` operational.
- [x] **Frontend compiles with TypeScript strict mode**: `tsc --noEmit` exits with 0 errors.
- [x] **Tests run from documented commands**: `pytest` executes 16 automated test suites (100% pass rate).
- [x] **No secrets are committed**: Secrets strictly isolated in `.env` (ignored by git).
- [x] **Zero Synthetic Data Policy**: Honest empty states displayed until live feeds connect.
