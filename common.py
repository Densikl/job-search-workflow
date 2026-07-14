"""Shared utilities for the job pipeline."""

import re
import sys
from typing import Any

SCHEMA = [
    "title", "company", "url", "source", "salary",
    "location", "posted_at", "description", "tags",
]

KEYWORDS = re.compile(
    r"\b(python|django|fastapi|backend|back-end)\b", re.IGNORECASE
)

UA = {"User-Agent": "Mozilla/5.0 (job-pipeline; personal use)"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def make_posting(**kw: Any) -> dict:
    """Build a schema-conforming posting; missing fields become ''. """
    return {k: str(kw.get(k, "") or "").strip() for k in SCHEMA}
