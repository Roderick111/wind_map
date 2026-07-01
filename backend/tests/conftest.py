"""Pytest configuration — isolate tests from the dev database."""

from __future__ import annotations

import os
from pathlib import Path

# Must run before wind_track imports settings (conftest loads first).
_TEST_DB = Path(__file__).resolve().parent / ".test_wind_track.db"
os.environ["WIND_TRACK_DB_PATH"] = str(_TEST_DB)