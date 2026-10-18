"""
Vercel Serverless Python ASGI Entrypoint for ALPHA Quant.
Seeds writable /tmp/alpha_quant_v4.db from the bundled baseline SQLite database on cold start,
and exposes the top-level FastAPI application instance (`app`).
"""

import os
from pathlib import Path
import shutil
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Configure serverless-safe writable SQLite database in /tmp
TMP_DIR = Path("/tmp")
if TMP_DIR.is_dir():
    tmp_db = TMP_DIR / "alpha_quant_v4.db"
    bundled_db = BACKEND_DIR / "alpha_quant.db"
    if not tmp_db.exists() and bundled_db.exists():
        try:
            shutil.copy2(bundled_db, tmp_db)
        except Exception:
            pass
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_db.as_posix()}"
    os.environ["DATABASE_SYNC_URL"] = f"sqlite:///{tmp_db.as_posix()}"

os.environ["ENABLE_LIVE_FEED_STREAMING"] = "false"
os.environ["BINANCE_REST_BASE_URL"] = "https://data-api.binance.vision"
os.environ["ENVIRONMENT"] = "development"

from app.main import app  # noqa: E402

