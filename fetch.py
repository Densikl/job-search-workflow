"""
fetch.py — pull postings from aggregators, normalize, dedupe, emit JSON.

Usage:
    python fetch.py                 # fetch + dedupe against the sheet
    python fetch.py --no-dedupe     # fetch only (works before Step 0 is done)

Output: JSON array of NEW postings on stdout. Logs go to stderr,
so `python fetch.py > new.json` stays clean.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import httpx
from dotenv import load_dotenv

from common import KEYWORDS, log

load_dotenv()

# ---------------------------------------------------------------- dedupe

def canonical_url(url: str) -> str:
    """Strip query strings, fragments, trailing slashes, force https.

    The same job arrives from different boards with different tracking
    params — ?utm_source=... must not defeat dedupe.
    """
    parts = urlsplit(url.strip())
    return urlunsplit(("https", parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()[:16]


def company_title_key(p: dict) -> str:
    """Second dedupe layer: catches the same role cross-posted to two
    boards under different URLs."""
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    return f"{norm(p['company'])}::{norm(p['title'])}"


def load_seen() -> tuple[set[str], set[str]]:
    """Read seen url-hashes and company::title keys from the sheet."""
    import gspread  # local import: --no-dedupe must work without creds

    raw = os.environ["GOOGLE_SA_JSON"]
    gc = (
        gspread.service_account_from_dict(json.loads(raw))
        if raw.strip().startswith("{")
        else gspread.service_account(filename=raw)
    )
    ws = gc.open_by_key(os.environ["SHEET_ID"]).worksheet("seen")
    rows = ws.get_all_values()[1:]  # skip header
    hashes = {r[0] for r in rows if r}
    ct_keys = {
        company_title_key({"company": r[1], "title": r[2]})
        for r in rows
        if len(r) >= 3
    }
    return hashes, ct_keys


# ---------------------------------------------------------------- sources

from sources import fetch_remoteok, fetch_remotive, fetch_wwr_rss, fetch_jobicy

SOURCES = {
    "remoteok": fetch_remoteok,
    "remotive": fetch_remotive,
    "wwr": fetch_wwr_rss,
    "jobicy": fetch_jobicy,
}

# ---------------------------------------------------------------- main

def relevant(p: dict) -> bool:
    hay = f"{p['title']} {p['description']}"
    return bool(KEYWORDS.search(hay))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-dedupe", action="store_true",
                    help="skip reading the seen tab (pre-Step-0 testing)")
    args = ap.parse_args()

    all_postings: list[dict] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for name, fn in SOURCES.items():
            try:
                got = fn(client)
                log(f"[{name}] fetched {len(got)}")
                all_postings.extend(got)
            except Exception as e:
                # One dead source must not kill the nightly run
                log(f"[{name}] FAILED: {e}")

    postings = [p for p in all_postings if relevant(p)]
    log(f"after keyword filter: {len(postings)} / {len(all_postings)}")

    # dedupe within this batch (same job from two sources)
    batch: dict[str, dict] = {}
    ct_in_batch: set[str] = set()
    for p in postings:
        h = url_hash(p["url"])
        ct = company_title_key(p)
        if h in batch or ct in ct_in_batch:
            continue
        batch[h] = p
        ct_in_batch.add(ct)

    # dedupe against history
    if args.no_dedupe:
        log("dedupe vs sheet: SKIPPED (--no-dedupe)")
        fresh = list(batch.values())
    else:
        seen_hashes, seen_ct = load_seen()
        fresh = [
            p for h, p in batch.items()
            if h not in seen_hashes and company_title_key(p) not in seen_ct
        ]
        log(f"new vs seen tab: {len(fresh)} / {len(batch)}")

    for p in fresh:
        p["url"] = canonical_url(p["url"])
        p["url_hash"] = url_hash(p["url"])
        p["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    print(json.dumps(fresh, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
