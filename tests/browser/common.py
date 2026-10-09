"""Paths and request helpers shared by the optional browser checks."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
OUTPUT = ROOT / ".runtime" / "test-results"
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


async def no_measurement_writes(page):
    """Keep the real map live without creating monitoring records or reports."""
    for endpoint in ["capnhat", "dulieu/lichsu", "canhbao", "baocao"]:
        await page.route(
            f"**/api/{endpoint}?**",
            lambda route, key=endpoint: route.fulfill(
                json={"DuLieu": {}} if key == "capnhat" else []
            ),
        )
