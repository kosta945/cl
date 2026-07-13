# LinkedIn Prospect Activity Rank

Rates a list of LinkedIn prospects as **GREEN** (active), **ORANGE** (sort of
active), or **RED** (not active), using a fast deterministic rule engine
first and falling back to Claude only for rows where the signals are
missing or contradict each other.

Activity data comes from either a CSV you supply yourself (Sales Navigator
export, manual notes, browser copy-paste) or from the
[Apify `bovi/linkedin-profile-scraper` actor](https://apify.com/bovi/linkedin-profile-scraper),
wired up in `fetch_apify.py`. This repo doesn't do its own scraping.

## How it works

1. **Rule engine** (`linkedin_activity_rank/rules.py`) scores each profile
   from structured fields:
   - *Recency*: days since `last_post_date` (≤14d → green, ≤45d → orange,
     else red)
   - *Frequency*: `posts_last_30d` / `comments_or_likes_last_30d` counts
   - If both signals agree, or only one is present, the rule engine is
     confident and Claude is never called.
   - If the two signals flatly contradict each other, the row is marked
     low-confidence.
2. **Claude fallback** (`linkedin_activity_rank/claude_fallback.py`) only
   runs on rows that are low-confidence or have no structured data but do
   have freeform `notes`. It reads the same rubric and returns a rating,
   confidence, and one-sentence reasoning.
3. Rows with literally no data at all default to RED with a
   "no data provided" reasoning — nothing is guessed.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # only needed if you want the Claude fallback
export APIFY_API_TOKEN=apify_api_...  # only needed if you want to fetch via Apify
```

## Usage

### Option A: you already have a CSV of activity data

```bash
python main.py --input examples/sample_input.csv --output results.csv
```

Rule-only mode (no API calls, ambiguous rows default to RED):

```bash
python main.py --input prospects.csv --output results.csv --no-claude
```

### Option B: fetch profile data via Apify first

```bash
# urls.txt: one LinkedIn profile URL per line (see examples/urls.txt)
python fetch_apify.py --urls urls.txt --output prospects.csv
python main.py --input prospects.csv --output results.csv
```

`fetch_apify.py` calls the actor via the official `apify-client` SDK and
normalizes its response into the same CSV schema `main.py` reads (see
"Input CSV schema" below). One thing to flag: **the mapping from the
actor's raw output fields to `last_post_date` / `posts_last_30d` /
`comments_or_likes_last_30d` is a best-effort guess** — this repo was built
in a sandboxed session that couldn't reach apify.com to confirm the
actor's exact response schema, so the candidate field names in
`linkedin_activity_rank/apify_source.py` (`LAST_POST_DATE_KEY_CANDIDATES`,
etc.) are unverified. Two ways to lock this in:

1. Run once with `--dump-raw examples/apify_raw_sample.json`, inspect the
   real field names Apify returns, and update the candidate lists in
   `apify_source.py` to match exactly.
2. Even without that, nothing is lost: the full raw item is always copied
   into the `notes` column, so the Claude fallback can still classify
   correctly off the unstructured JSON even if structured extraction
   misses.

The actor input is also a best-effort guess (`{"profileUrls": [...]}`) —
if the run fails or returns nothing, check the actor's "Input" tab in the
Apify Console for its real input schema and adjust
`fetch_profiles_from_apify()` accordingly.

## Input CSV schema

Only `name` and `profile_url` are required. Provide as many of the other
columns as you have — more structured data means fewer rows need the
Claude fallback.

| column                        | required | example                              |
|--------------------------------|----------|---------------------------------------|
| `name`                          | yes      | `Alice Kim`                           |
| `profile_url`                   | yes      | `https://www.linkedin.com/in/alicekim`|
| `last_post_date`                | no       | `2026-07-05` (YYYY-MM-DD)             |
| `posts_last_30d`                | no       | `6`                                    |
| `comments_or_likes_last_30d`    | no       | `22`                                   |
| `notes`                         | no       | freeform text, e.g. pasted activity-tab snippets |

See `examples/sample_input.csv` for a worked example covering clean green/
orange/red rows, a contradictory row, a notes-only row, and an empty row.

## Output CSV

Same columns as the input, plus:

- `rating` — `GREEN` / `ORANGE` / `RED`
- `confidence` — `HIGH` / `MEDIUM` / `LOW`
- `method` — `rule` or `claude`
- `reasoning` — one-sentence explanation

## Tuning the thresholds

Recency and frequency thresholds are constants at the top of
`linkedin_activity_rank/rules.py` — adjust `RECENCY_GREEN_MAX_DAYS`,
`RECENCY_ORANGE_MAX_DAYS`, `FREQUENCY_GREEN_MIN_POSTS`, etc. to match your
definition of "active."

## Tests

```bash
pip install pytest
pytest
```
