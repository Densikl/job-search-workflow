"""
write.py — push scored postings to the Google Sheet.

Reads scored JSON from a file argument or stdin, then:
1. Appends rows to the `jobs` tab (sorted by score desc).
2. Adds url_hash rows to the `seen` tab.
3. Adds companies with score >= 8 to `watchlist` (if not already there).

Usage:
    python write.py scored.json
    cat scored.json | python write.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import gspread


def get_client():
    raw = os.environ["GOOGLE_SA_JSON"]
    if raw.strip().startswith("{"):
        return gspread.service_account_from_dict(json.loads(raw))
    return gspread.service_account(filename=raw)


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        data = json.loads(open(sys.argv[1]).read())
    else:
        data = json.load(sys.stdin)

    if not data:
        log("no postings to write")
        return

    data.sort(key=lambda p: p.get("score", 0), reverse=True)

    gc = get_client()
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    # --- jobs tab (only score > 0 — zeroes are noise)
    jobs_ws = sh.worksheet("jobs")
    scorable = [p for p in data if p.get("score", 0) > 0]
    job_rows = []
    for p in scorable:
        job_rows.append([
            now,
            p.get("score", ""),
            p.get("title", ""),
            p.get("company", ""),
            p.get("salary", ""),
            p.get("location", ""),
            p.get("source", ""),
            p.get("url", ""),
            p.get("why_relevant", ""),
            "",  # status — filled manually by Denis
        ])
    if job_rows:
        jobs_ws.append_rows(job_rows, value_input_option="RAW")
    log(f"jobs: appended {len(job_rows)} rows (skipped {len(data) - len(scorable)} zero-score)")

    # --- seen tab
    seen_ws = sh.worksheet("seen")
    seen_rows = []
    for p in data:
        seen_rows.append([
            p.get("url_hash", ""),
            p.get("company", ""),
            p.get("title", ""),
            now,
        ])
    seen_ws.append_rows(seen_rows, value_input_option="RAW")
    log(f"seen: appended {len(seen_rows)} rows")

    # --- watchlist tab (score >= 8, dedupe by company name)
    wl_ws = sh.worksheet("watchlist")
    existing = wl_ws.get_all_values()[1:]
    existing_companies = {r[0].lower().strip() for r in existing if r}

    wl_rows = []
    added_companies: set[str] = set()
    for p in data:
        if p.get("score", 0) >= 8:
            company = p.get("company", "").strip()
            if company.lower() not in existing_companies and company.lower() not in added_companies:
                wl_rows.append([
                    company,
                    now,
                    p.get("why_relevant", ""),
                    "",  # careers_url — filled later
                ])
                added_companies.add(company.lower())

    if wl_rows:
        wl_ws.append_rows(wl_rows, value_input_option="RAW")
        log(f"watchlist: added {len(wl_rows)} companies")
    else:
        log("watchlist: no new companies (none scored >= 8)")


if __name__ == "__main__":
    main()
