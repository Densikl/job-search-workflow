# Job Pipeline — Project Context

A Claude Code–driven pipeline that finds Python backend jobs nightly, scores them
for fit, and stores them in a Google Sheet for review. No auto-applying. The human
stays the reviewer: the pipeline stops at "here's a ranked shortlist."

## Owner profile

See `rubric.md` for the target profile that drives scoring. Copy
`rubric.md.example` to `rubric.md` and customize it before running the pipeline.

## Doctrine (guiding principles — do not violate)

1. **Aggregators are primary.** Wide net across job boards, not a curated company list.
2. **The agent's job is filtering, not discovery.** Fetching is deterministic Python;
   LLM tokens are spent only on judgment (scoring). Never "browse job boards" agentically.
3. **The watchlist grows from hits, not guesses.** Companies enter the `watchlist` tab
   when their postings score ≥8 or get applied to — never enumerated upfront.
4. **Teach iteratively.** Scoring criteria live in `rubric.md`, start short, evolve via
   reviewed PRs — never edited silently by the nightly run.
5. **Short sessions, one task per session.**
6. **Every posting appears once, ever.** Dedupe is sacred: canonical-URL hash +
   normalized company::title key, state lives in the Sheet's `seen` tab.

## Project structure

```
fetch.py           deterministic fetcher: aggregators → normalized JSON → dedupe
                     vs `seen` tab → NEW postings as JSON on stdout (logs on stderr)
write.py           scored JSON → append score>0 to `jobs`, ALL to `seen`, ≥8 to `watchlist`
rubric.md.example  scoring rubric template — copy to rubric.md and customize
rubric.md          [gitignored] personal scoring criteria (axes, disqualifiers)
test_sheets.py     verifies service-account access, creates tabs, appends test row
requirements.txt   httpx, gspread, feedparser
.env               GOOGLE_SA_JSON (single-quoted raw JSON) + SHEET_ID (not committed)
new.json           [transient] raw fetch output
scored.json        [transient] fetch output with score + why_relevant added
```

## Architecture

```
fetch.py   deterministic: aggregators → normalized JSON → dedupe vs `seen` tab
             → NEW postings as JSON on stdout (logs on stderr)
[Claude]   scores each posting 0–10 against rubric.md, adds one-line reason
write.py   scored JSON → append score>0 to `jobs` tab sorted by score,
             ALL to `seen`, add ≥8 companies to `watchlist`
```

Google Sheet tabs (created by test_sheets.py):
- `jobs`:      found_at, score, title, company, salary, location, source, url, why_relevant, status
- `seen`:      url_hash, company, title, first_seen
- `watchlist`: company, added_at, reason, careers_url

`status` in `jobs` is filled manually by the reviewer
(applied / skipped-senior / skipped-stack / skipped-region / interview).
A future weekly task reads these verdicts and proposes rubric changes as a PR.

## Conventions

- Env vars: `GOOGLE_SA_JSON` (path to service-account key file OR raw JSON string —
  both supported everywhere), `SHEET_ID`
- stdout = data (JSON), stderr = logs. `python fetch.py > new.json` must stay clean.
- One dead source must never kill the run: every fetcher wrapped in try/except, logs and continues.
- Normalized posting schema (every source function returns exactly these keys):
  `title, company, url, source, salary, location, posted_at, description, tags`
- Scored postings add: `score` (0–10), `why_relevant`, `url_hash`, `fetched_at`
- `--no-dedupe` flag on fetch.py allows running without Google creds.

## Current state

DONE:
- `test_sheets.py` — verifies service-account access, auto-creates missing tabs
  with headers, appends a test row. Works.
- `fetch.py` + `sources.py` + `common.py` — four sources (RemoteOK, Remotive, WWR,
  Jobicy), schema with `tags` field. Fetchers live in `sources.py`, shared utils
  in `common.py`. Keyword filter checks title + description only (not tags — too
  noisy from RemoteOK). Typical run: ~300 fetched, ~70 after filter.
- `rubric.md` — scoring rubric v1: axes (stack, seniority, industry, location,
  salary), hard disqualifiers, worked examples.
- `write.py` — reads scored JSON, appends score>0 to `jobs` (sorted by score desc),
  ALL postings to `seen` (dedupe must cover zeroes too), score≥8 companies to
  `watchlist`. Zero-score postings are noise and never reach the review tab.
- `requirements.txt` — httpx, gspread, feedparser.
- `.env` — `GOOGLE_SA_JSON` (raw JSON, single-quoted) + `SHEET_ID`.
- First dress rehearsal completed: full chain ran end-to-end, 6 postings scored >0
  out of 162.

NOT DONE:
- HH.ru source (returns 403, likely geo-blocked from outside Russia/CIS)
- Later sources (researched, APIs confirmed working):
  - Arbeitnow: public JSON API, EU-leaning, category filter broken server-side
  - Himalayas: public JSON API, huge catalog (~103k), filter broken server-side
  - python.org RSS: tiny volume, easy to add
  - HN "Who is Hiring" via Algolia API: high signal but unstructured text, needs parsing

## Immediate TODO (in order)

1. Later (after ~1 week of real reviews): second weekly Routine that reads `status`
   verdicts, compares to its own scores, proposes rubric.md changes as a PR on a
   `claude/` branch. The owner merges or rejects.

## Nightly Routine prompt (draft — refine during rehearsal)

> Run `pip install -r requirements.txt`, then `python fetch.py > new.json`.
> Read new.json. Score each posting 0–10 against rubric.md; add a one-line
> why_relevant for each. Write the scored array to scored.json, then run
> `python write.py scored.json`. If any step fails, stop and report the error
> clearly. Do not edit rubric.md. Do not browse the web.
