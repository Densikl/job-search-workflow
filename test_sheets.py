"""
Step 0 verification: can we talk to the spreadsheet?

Usage:
    export GOOGLE_SA_JSON=/path/to/service-account-key.json
    export SHEET_ID=<the long id from the spreadsheet URL>
    python test_sheets.py

Done when: you see "OK" and a test row appears in the `jobs` tab.
"""

import json
import os
import sys
from datetime import datetime, timezone

import gspread

REQUIRED_TABS = ["jobs", "seen", "watchlist"]

JOBS_HEADER = [
    "found_at", "score", "title", "company", "salary",
    "location", "source", "url", "why_relevant", "status",
]
SEEN_HEADER = ["url_hash", "company", "title", "first_seen"]
WATCHLIST_HEADER = ["company", "added_at", "reason", "careers_url"]


def get_client() -> gspread.Client:
    """Auth via service account. Reads key from GOOGLE_SA_JSON.

    Accepts either a file path or the raw JSON string — the latter is how
    the Routine will pass it as an environment variable later, so we
    support both from day one.
    """
    raw = os.environ.get("GOOGLE_SA_JSON")
    if not raw:
        sys.exit("Set GOOGLE_SA_JSON (path to key file, or the JSON itself)")

    if raw.strip().startswith("{"):
        creds = json.loads(raw)
        return gspread.service_account_from_dict(creds)
    return gspread.service_account(filename=raw)


def main() -> None:
    sheet_id = os.environ.get("SHEET_ID")
    if not sheet_id:
        sys.exit("Set SHEET_ID (from the spreadsheet URL)")

    gc = get_client()
    try:
        ss = gc.open_by_key(sheet_id)
    except gspread.exceptions.APIError as e:
        sys.exit(
            f"API error: {e}\n"
            "Most likely fix: share the sheet with the service account "
            "email (Editor role) — it's in the key file under client_email."
        )

    existing = {ws.title for ws in ss.worksheets()}
    print(f"Connected to: {ss.title}")
    print(f"Tabs found: {sorted(existing)}")

    # Create any missing tabs and write headers into empty ones
    headers = {"jobs": JOBS_HEADER, "seen": SEEN_HEADER, "watchlist": WATCHLIST_HEADER}
    for tab in REQUIRED_TABS:
        if tab not in existing:
            ws = ss.add_worksheet(title=tab, rows=1000, cols=len(headers[tab]))
            print(f"Created missing tab: {tab}")
        else:
            ws = ss.worksheet(tab)
        if not ws.row_values(1):
            ws.append_row(headers[tab])
            print(f"Wrote header row to: {tab}")

    # The actual test: append one row to `jobs`
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ss.worksheet("jobs").append_row(
        [now, "", "TEST ROW — delete me", "test", "", "", "test", "", "", ""]
    )
    print("OK — test row appended to `jobs`. Step 0 complete.")


if __name__ == "__main__":
    main()
