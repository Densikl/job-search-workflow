"""
fetch.py — pull postings from aggregators, normalize, dedupe, emit JSON.

Deterministic by design: no LLM here. The agent's job is filtering,
not discovery — this script IS the wide net.

Usage:
    python fetch.py                 # fetch + dedupe against the sheet
    python fetch.py --no-dedupe     # fetch only (works before Step 0 is done)

Output: JSON array of NEW postings on stdout. Logs go to stderr,
so `python fetch.py > new.json` stays clean.

Sources implemented: RemoteOK (official public JSON API, keyless).
Next up (same pattern, one function each): Remotive, WWR RSS, HH.ru.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

# ---------------------------------------------------------------- schema

# Every source function must return a list of dicts with exactly these keys.
SCHEMA = [
    "title", "company", "url", "source", "salary",
    "location", "posted_at", "description", "tags",
]

# Cheap pre-filter: a posting must mention at least one of these to be
# worth sending to the scoring step. Keep it loose — the rubric decides,
# this just cuts obvious noise (design jobs, sales, etc.).
KEYWORDS = re.compile(
    r"\b(python|django|fastapi|backend|back-end)\b", re.IGNORECASE
)

UA = {"User-Agent": "Mozilla/5.0 (job-pipeline; personal use)"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def make_posting(**kw: Any) -> dict:
    """Build a schema-conforming posting; missing fields become ''. """
    return {k: str(kw.get(k, "") or "").strip() for k in SCHEMA}


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

def fetch_remoteok(client: httpx.Client) -> list[dict]:
    """RemoteOK official public JSON API. Query ?tag=python and ?tag=backend
    separately, merge by job id to avoid duplicates."""
    seen_ids: set[str] = set()
    out = []

    for tag in ("python", "backend"):
        try:
            r = client.get(f"https://remoteok.com/api?tag={tag}", headers=UA)
            r.raise_for_status()
            items = [x for x in r.json() if isinstance(x, dict) and x.get("id")]
        except Exception as e:
            log(f"[remoteok/{tag}] request failed: {e}")
            continue

        for x in items:
            jid = str(x["id"])
            if jid in seen_ids:
                continue
            seen_ids.add(jid)

            salary = ""
            lo, hi = x.get("salary_min"), x.get("salary_max")
            if lo or hi:
                salary = f"${lo or '?'}–${hi or '?'}"
            posted = (x.get("date") or "")[:10]
            tags_list = x.get("tags") or []
            out.append(
                make_posting(
                    title=x.get("position"),
                    company=x.get("company"),
                    url=x.get("url"),
                    source="remoteok",
                    salary=salary,
                    location=x.get("location") or "Remote",
                    posted_at=posted,
                    description=(x.get("description") or "")[:2000],
                    tags=", ".join(tags_list) if isinstance(tags_list, list) else str(tags_list),
                )
            )
    return out


def fetch_remotive(client: httpx.Client) -> list[dict]:
    """Remotive public JSON API — software-dev category, no key needed."""
    r = client.get(
        "https://remotive.com/api/remote-jobs",
        params={"category": "software-dev", "limit": 200},
        headers=UA,
    )
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
    out = []
    for x in jobs:
        tags_list = x.get("tags") or []
        out.append(
            make_posting(
                title=x.get("title"),
                company=x.get("company_name"),
                url=x.get("url"),
                source="remotive",
                salary=x.get("salary") or "",
                location=x.get("candidate_required_location") or "Remote",
                posted_at=(x.get("publication_date") or "")[:10],
                description=(x.get("description") or "")[:2000],
                tags=", ".join(tags_list) if isinstance(tags_list, list) else str(tags_list),
            )
        )
    return out


def fetch_wwr_rss(client: httpx.Client) -> list[dict]:
    """We Work Remotely — back-end programming RSS feed, parsed with feedparser."""
    import feedparser

    r = client.get(
        "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
        headers=UA,
    )
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    out = []
    for entry in feed.entries:
        title_raw = entry.get("title", "")
        company, _, title = title_raw.partition(": ")
        if not title:
            title, company = company, ""

        posted = ""
        if entry.get("published_parsed"):
            from time import strftime, gmtime
            posted = strftime("%Y-%m-%d", entry.published_parsed)

        region = entry.get("region", "")
        out.append(
            make_posting(
                title=title.strip(),
                company=company.strip(),
                url=entry.get("link", ""),
                source="wwr",
                salary="",
                location=region or "Remote",
                posted_at=posted,
                description=(entry.get("summary") or "")[:2000],
                tags=entry.get("category", ""),
            )
        )
    return out


SOURCES = {
    "remoteok": fetch_remoteok,
    "remotive": fetch_remotive,
    "wwr": fetch_wwr_rss,
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

    postings = [p for p in all_postings if relevant(p)ok]
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
