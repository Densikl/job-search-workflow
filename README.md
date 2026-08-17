# job-posting-workflow

A nightly pipeline that finds Python backend jobs across multiple aggregators, scores each one for fit using an LLM, and writes a ranked shortlist to Google Sheets. No auto-applying. The human stays the reviewer — the pipeline stops at "here's what's worth looking at today."

---

## Why this exists

Job boards are noisy. A keyword search for "Python backend" returns senior-only roles, Go-primary stacks with Python listed as a bonus, LATAM-only postings, and optometrist listings that somehow got tagged "python." Checking four boards manually every morning is tedious and inconsistent.

This pipeline handles the tedious part deterministically and uses the LLM only for the judgment call: *given this specific posting and this specific candidate profile, is this worth reviewing?*

---

## Architecture

```
fetch.py  ──►  [Claude, scoring against rubric.md]  ──►  write.py  ──►  Google Sheets
```

Three stages with a clean boundary between each:

**Stage 1 — Fetch** (`fetch.py`)  
Plain Python. Pulls from four aggregators via their public JSON/RSS APIs, applies a keyword filter against title and description, then deduplicates against the `seen` tab in the Sheet. Outputs only *new* postings as JSON to stdout. Logs go to stderr, so `python fetch.py > new.json` stays clean.

**Stage 2 — Score** (LLM, via `claude -p` or manually)  
Reads `new.json` and `rubric.md`, scores each posting 0–10 across five weighted axes, writes `scored.json`. The LLM's only job here is judgment — it doesn't browse the web or discover anything; fetching is handled deterministically in Stage 1.

**Stage 3 — Write** (`write.py`)  
Reads `scored.json`, appends non-zero scorers to the `jobs` tab sorted by score, records everything in `seen` (dedup must cover zeroes too), and adds high-scorers (≥ 8) to `watchlist`.

---

## Sources

| Source | Format | Notes |
|--------|--------|-------|
| RemoteOK | JSON API | High volume, noisy tags — keyword filter runs on title + description only |
| Remotive | JSON API | Cleaner categorization |
| WeWorkRemotely | RSS | Reliable, lower volume |
| Jobicy | JSON API | Good global coverage |

Each fetcher is wrapped in `try/except` — one dead source never kills the run.

Typical numbers: ~300 fetched across all sources → ~70 after keyword filter → ~65 new vs the seen tab.

---

## Scoring rubric

The rubric lives in `rubric.md` — a versioned, auditable spec the LLM reads at runtime. Changes to the rubric take effect on the next run with no code changes, and the history is in git.

**Two-stage procedure:**

1. **Disqualifier gate** — fires only when a disqualifier is *clearly stated* in the posting (wrong primary language, on-site non-local, senior-only with a hard year floor, required work authorization). Ambiguous cases are scored normally with `confidence="low"` so they surface for manual review. Zeroing ambiguous postings defeats the purpose of having a review sheet.

2. **Weighted axis scoring** — five axes, each scored 0–10:

| Axis | Weight | What it measures |
|------|--------|-----------------|
| Stack match | 30% | Python-primary? FastAPI, async, PostgreSQL, Redis? |
| Seniority fit | 25% | Junior/mid-level, or plausibly open to it? |
| Industry | 20% | Fintech, crypto, payments, or adjacent? |
| Location eligibility | 15% | Fully remote, or workable from your timezone? |
| Salary signal | 10% | Listed and ≥ $40k? (most postings omit this) |

`weighted_score = Σ(axis_score × weight)`. `display_score = round(weighted_score)`. Postings with `display_score > 0` go to the `jobs` tab; zero-scorers go only to `seen`.

---

## Google Sheets output

Three tabs, created automatically by `test_sheets.py`:

**`jobs`** — the review queue, sorted by score descending.  
`found_at | score | confidence | title | company | salary | location | source | url | why_relevant | status`

`status` is filled manually while reviewing: `applied`, `skipped-senior`, `skipped-stack`, `skipped-region`, `interview`.

**`seen`** — every posting ever processed, regardless of score. The deduplication source of truth.  
`url_hash | company | title | first_seen`

**`watchlist`** — companies whose postings scored ≥ 8, for direct monitoring.  
`company | added_at | reason | careers_url`

---

## Deduplication

Two layers, both checked:

1. **URL hash** — SHA-256 of the canonical URL (tracking params stripped, https forced, trailing slash removed). The same job linked from two boards with different `?utm_source=` params won't appear twice.

2. **`company::title` key** — normalized (lowercase, non-alphanumeric stripped). Catches cross-postings where the URL differs but the role is identical.

Both layers are checked against the current batch *and* the `seen` tab from all previous runs.

---

## Setup

### Prerequisites

- Python 3.11+
- A Google Cloud service account with the Sheets API enabled
- The service account key JSON
- A Google Sheet with the ID from its URL
- Claude Code CLI installed and authenticated (for scheduling)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/job-posting-workflow
cd job-posting-workflow
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure credentials

Create `.env` in the project root:

```bash
GOOGLE_SA_JSON='{"type":"service_account","project_id":"..."}' # raw JSON, single-quoted
SHEET_ID=your_sheet_id_from_the_url
```

`GOOGLE_SA_JSON` accepts either raw JSON (as above) or a path to the key file — both work everywhere in the codebase.

### 3. Verify Sheets access

```bash
python test_sheets.py
```

This creates the three tabs with correct headers and appends a test row. If it completes without error, the pipeline has write access.

### 4. Customize the rubric

```bash
cp rubric.md.example rubric.md
```

Edit `rubric.md` to match your profile — location, stack, seniority target, industry preferences. Look for `<YOUR_...>` placeholders and `<!-- Customize -->` comments. The worked examples at the bottom help calibrate the scoring weights to your actual priorities.

---

## Running the pipeline

**Fetch only (no credentials needed):**
```bash
python fetch.py --no-dedupe
```

**Full pipeline:**
```bash
python fetch.py > new.json
# Score new.json with Claude against rubric.md → scored.json
python write.py scored.json
```

For the scoring step, pass `nightly_prompt.md` to Claude Code:
```bash
claude -p "$(cat nightly_prompt.md)" --allowedTools "Read,Write"
```

---

## Scheduling (macOS)

`run_pipeline.sh` chains all three stages but has no scheduling logic — it just runs when called. The schedule lives in the launchd plist (`com.yourname.jobpipeline.plist`), which tells macOS to call the script at 08:00 daily. launchd also catches up if the machine was asleep at the scheduled time, which plain `cron` does not.

```bash
# 1. Replace every YOUR_USERNAME in the plist with your actual username (`whoami`)
# 2. Rename and copy it
cp com.yourname.jobpipeline.plist ~/Library/LaunchAgents/com.$(whoami).jobpipeline.plist
launchctl load ~/Library/LaunchAgents/com.$(whoami).jobpipeline.plist
```

Output appends to `pipeline.log` in the project directory.

---

## Design decisions worth noting

**LLM tokens only on judgment, not discovery.** The fetching layer is deterministic Python with no AI involvement. This keeps runs fast, predictable, and cheap. The LLM reads a structured document and returns structured output — it isn't browsing or reasoning about where to look.

**The rubric is a file, not a prompt string.** Keeping `rubric.md` in version control means scoring criteria are auditable and changes are reviewed as PRs. A nightly run that silently edits its own rubric would be hard to trust.

**Disqualifiers require explicit evidence.** A posting that doesn't mention seniority doesn't get zeroed for "might be senior-only." Ambiguous postings score normally with `confidence="low"` so they appear in the review queue rather than disappearing. False negatives (missed good roles) are worse than false positives (roles that turn out to be wrong on inspection).

**stdout = data, stderr = logs.** `python fetch.py > new.json` works because every informational message goes to stderr. This makes the stages composable as a Unix pipeline without any intermediate file format negotiation.

**Dedup covers zeroes.** `write.py` records every posting to `seen`, including disqualified ones. A role that scores 0 today would score 0 again tomorrow — adding it to `seen` prevents it from reappearing in the review queue on every run.

---

## What's not here yet

- **HH.ru** — returns 403 from outside Russia/CIS. Geo-blocked.
- **Arbeitnow, Himalayas, python.org RSS, HN "Who Is Hiring"** — APIs confirmed working, not yet integrated.
- **Rubric feedback loop** — a weekly routine that reads the `status` verdicts the reviewer fills in, compares them to the original scores, and proposes `rubric.md` edits as a PR. Planned after enough reviews accumulate to make the signal meaningful.
