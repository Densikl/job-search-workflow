# Job Posting Scoring Rubric v2 — LLM scoring spec

You are scoring a single job posting for fit. Output is written to a Google Sheet
and ranked for manual review, so ranking granularity and auditability matter.

## Target profile

Python backend developer, ~2 years production experience, based in Tbilisi, Georgia
(UTC+4). Seeking fully-remote or Georgia-based junior/middle roles. Strong preference
for fintech, crypto, and blockchain infrastructure.

## Scoring procedure (follow in order)

1. **Ground everything in the posting text.** Score only from what the posting
   states. Do not invent requirements, seniority, or location terms that aren't
   present. If a field is absent, apply that axis's "missing" rule and lower confidence.

2. **Stage 1 — Disqualifier gate.** Check the hard disqualifiers below.
   - If one is **clearly stated** → `disqualified = true`, `weighted_score = 0`,
     name the trigger, skip axis scoring.
   - If a would-be disqualifier is only **implied or ambiguous** → do NOT zero.
     Score the axes normally and set `confidence = "low"` so the item surfaces for
     manual review. (Zeroing ambiguous postings defeats the purpose of the review sheet.)

3. **Stage 2 — Score each axis 0–10** using the anchors below. Interpolate for
   in-between cases; you are not restricted to the anchor values.

4. `weighted_score = Σ(axis_score × weight)`, kept to one decimal. **This is the sort key.**

5. `display_score = round(weighted_score)`.

6. Emit the structured output (schema at the bottom).

## Scoring axes

Anchors given at 10 / 7 / 4 / 0. Interpolate between them.

### Stack match — weight 30%
- **10** — Python-primary backend, stack overlaps the target's: FastAPI, Django/DRF,
  Celery, async SQLAlchemy + asyncpg, Redis, PostgreSQL, Docker.
- **7** — Python-primary backend but different frameworks (Flask, aiohttp, Tornado)
  or only partial overlap.
- **4** — Python is one of several languages, or full-stack where the backend is
  only partly Python.
- **0** — No Python, or another language is the primary backend language.
  *(A 0 here almost always also trips the disqualifier gate — see Stage 1.)*

### Seniority fit — weight 25%
- **10** — Explicitly junior or mid-level; "2–3 years"; "2–4 years".
- **7** — Unspecified years but clearly an IC role with no senior signaling; or "3–5 years".
- **4** — "4–6 years" or strongly senior-preferred wording, but a mid-level candidate
  could plausibly apply.
- **0** — Senior / Staff / Principal only, or a hard 5+ year floor with no lower band.
  *(A clearly-stated 0 here trips the disqualifier gate.)*

### Industry — weight 20%
- **10** — Fintech, crypto, blockchain infrastructure, trading systems, payments.
- **7** — Adjacent depth: developer tools, data infrastructure, B2B SaaS with real
  backend engineering.
- **4** — General SaaS, marketplace, or consumer product.
- **0** — Domain that is off-target or explicitly uninteresting.
  *Note: low industry fit rarely justifies a full 0 — reserve it for genuinely
  off-target domains, and let the 20% weight do the work otherwise. Industry is
  never on its own a disqualifier.*

### Location eligibility — weight 15% (Tbilisi = UTC+4)
- **10** — Fully remote / "anywhere" / "global" / EMEA / Europe (including non-EU
  countries like Georgia) with no work-authorization restriction. Also 10 for
  on-site or hybrid roles **located in Tbilisi**.
- **7** — Remote with a timezone overlap that is workable from UTC+4 — e.g. "4+ hours
  overlap with US Eastern," which lands in Tbilisi afternoon/evening.
- **4** — Remote but demands US-Pacific business hours (early-morning Tbilisi), or
  "Europe" that hints at an EU-entity/contract requirement.
- **0** — On-site or hybrid anywhere other than Tbilisi / relocation required /
  US-only or EU-only **with work authorization required**.
  *(A clearly-stated 0 here trips the disqualifier gate.)*

### Salary signal — weight 10%
- **10** — Listed and ≥ $40k (or local equivalent).
- **7** — Listed $30k–40k.
- **5** — Not listed (default — low signal).
- **0** — Listed and < $30k.
  *Note: most postings omit salary, so this axis usually returns 5 and contributes a
  near-constant 0.5. Don't read much into it either way.*

## Hard disqualifiers (Stage 1 gate)

A disqualifier fires **only when clearly stated in the posting**, never when merely
implied. Ambiguous cases are scored normally with `confidence = "low"`.

- Requires work authorization in a specific country the candidate lacks (US-only,
  EU-only, "must be authorized to work in X") **and** the role is not otherwise open
  to global-remote contractors.
- On-site or hybrid presence required **anywhere other than Tbilisi**, or relocation
  required. On-site/hybrid **in Tbilisi is not a disqualifier** — the candidate is
  available locally.
- Another language is unambiguously the primary backend language (Go, Java, C#, Node,
  Ruby, PHP) and Python is not a core requirement — "Python a plus" does **not** count
  as core.
- Senior / Staff / Principal / Lead only, with a hard 5+ year floor and no lower band.
- Not a backend software-engineering role at all: pure data science, pure ML research,
  pure DevOps/SRE, pure QA, pure frontend, or people-management with no IC coding.
- Requires security clearance or citizenship.

## Output schema (per posting)

```json
{
  "weighted_score": 7.4,
  "display_score": 7,
  "disqualified": false,
  "disqualifier_reason": null,
  "confidence": "high",
  "axes": {
    "stack":     { "score": 8,  "why": "FastAPI + async SQLAlchemy; no Celery mention" },
    "seniority": { "score": 10, "why": "states \"2-4 years\"" },
    "industry":  { "score": 10, "why": "crypto exchange" },
    "location":  { "score": 7,  "why": "remote, requires 4h US-ET overlap" },
    "salary":    { "score": 5,  "why": "not listed" }
  },
  "notes": "optional free-text flag for the reviewer"
}
```

**Confidence levels:**
- `high` — every axis is grounded in explicit posting text.
- `medium` — one or two axes required light inference.
- `low` — seniority, location, or stack had to be guessed, **or** a near-disqualifier
  was ambiguous. These are the postings the reviewer should look at first.

## Worked examples

### 1. Clean high fit
"Python Backend Engineer" at a crypto exchange, 2–4 yrs, fully remote, $60–80k.

- stack 10 (0.30 × 10 = 3.0)
- seniority 10 (0.25 × 10 = 2.5)
- industry 10 (0.20 × 10 = 2.0)
- location 10 (0.15 × 10 = 1.5)
- salary 10 (0.10 × 10 = 1.0)
- **weighted_score = 10.0 · display 10 · disqualified false · confidence high**

### 2. Two independent disqualifiers
"Senior Full-Stack Engineer (React + Django)" at a healthcare startup, US-only.

- Stage 1 fires: "Senior … only" **and** "US-only." Either triggers alone.
- **weighted_score = 0 · disqualified true · disqualifier_reason "Senior-only + US-only work auth" · confidence high**

### 3. Ambiguous seniority — do not zero
"Backend Engineer (Python)" — no years stated, fully remote, fintech, no salary listed.

- No disqualifier is *clearly* stated (seniority merely absent, not "senior-only").
- stack 9 (2.7), seniority 7 (1.75, unspecified IC), industry 10 (2.0),
  location 10 (1.5), salary 5 (0.5)
- **weighted_score = 8.45 · display 8 · disqualified false · confidence medium**
  (seniority inferred)

### 4. Timezone drag, still eligible
Fintech Python role, remote but "must overlap 9–5 Pacific."

- stack 9 (2.7), seniority mid 8 (2.0), industry 10 (2.0),
  location 4 (0.6, early-morning Tbilisi), salary 5 (0.5)
- **weighted_score = 7.8 · display 8 · disqualified false · confidence high**
  Shows the 15% weight correctly dragging without killing an otherwise strong role.

### 5. Language trap (keyword-filter failure mode)
"Backend Engineer" that is Go-primary with "Python a plus," listed under a Python tag.

- A naive keyword match sees "Python" and scores stack high. The gate catches it:
  Python is not a core requirement, Go is primary.
- **weighted_score = 0 · disqualified true · disqualifier_reason "Go-primary, Python not core" · confidence high**
  This is exactly the class of false-positive a keyword filter lets through — the
  disqualifier gate is the backstop.