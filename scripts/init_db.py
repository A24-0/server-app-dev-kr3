"""Run once to create SQLite tables (also runs automatically on app startup)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from database import init_db  # noqa: E402

if __name__ == "__main__":
    init_db()
    print("Tables created (IF NOT EXISTS).")
