# LinkedIn Prospect Activity Rank

Rates a list of LinkedIn prospects as **GREEN** (active), **ORANGE** (sort of
active), or **RED** (not active), using a fast deterministic rule engine
first and falling back to Claude only for rows where the signals are
missing or contradict each other.

This tool does **not** scrape LinkedIn — that violates LinkedIn's Terms of
Service and is unreliable to automate. You supply whatever activity data
you've already gathered (Sales Navigator export, manual notes, browser
copy-paste, etc.) as a CSV, and the workflow classifies it.

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
```

## Usage

```bash
python main.py --input examples/sample_input.csv --output results.csv
```

Rule-only mode (no API calls, ambiguous rows default to RED):

```bash
python main.py --input prospects.csv --output results.csv --no-claude
```

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
