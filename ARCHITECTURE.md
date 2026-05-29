# ARCHITECTURE.md — BrewBot

Detailed technical reference. Read alongside `CLAUDE.md`.

---

## Data Flow Overview

```
Employee                    BrewBot (app.py)              DB (db.py)
   │                              │                           │
   │── /crowdbrew ──────────────→ │                           │
   │                              │── open opt-in modal ──→  │
   │←── modal shown ─────────────  │                           │
   │                              │                           │
   │── submit modal ────────────→ │                           │
   │                              │── upsert employee ──────→ │
   │←── "You're in!" DM ─────────  │                           │
   │                              │                           │
   │          [APScheduler: cycle start]                      │
   │                              │── get opted-in list ────→ │
   │                              │←── employee rows ─────── │
   │                              │── run_matching_cycle() → matching.py
   │                              │←── pairs list ─────────  │
   │                              │── write matches ────────→ │
   │←── match intro DM ──────────  │                           │
   │                              │                           │
   │          [APScheduler: 48hr nudge]                       │
   │                              │── get pending matches ──→ │
   │←── nudge DM ────────────────  │── update status nudged →  │
   │                              │                           │
   │── "We Already Met" btn ────→ │                           │
   │                              │── update status ────────→ │
   │←── feedback modal ──────────  │                           │
   │── submit feedback ─────────→ │── write completion ─────→ │
   │←── reward placeholder DM ──  │                           │
   │                              │                           │
   │          [APScheduler: cycle end]                        │
   │                              │── get cycle stats ──────→ │
   │                              │── post to admin channel ─  │
```

---

## Database Schema (SQLite)

All tables created automatically by `db.py:init_db()` on first run.

```sql
-- Employees who have opted in (upserted on each /crowdbrew submission)
CREATE TABLE IF NOT EXISTS employees (
    id              TEXT PRIMARY KEY,  -- Slack user ID
    name            TEXT NOT NULL,
    email           TEXT,
    department      TEXT NOT NULL,
    manager         TEXT NOT NULL,
    region          TEXT NOT NULL,
    timezone        TEXT,
    job_level       TEXT,              -- 'junior' | 'mid' | 'senior' | 'lead' | 'exec'
    tenure_months   INTEGER,
    opted_in        INTEGER DEFAULT 1, -- SQLite bool
    opt_in_date     TEXT,              -- ISO8601
    goals           TEXT,              -- free text from modal
    interests       TEXT,              -- free text from modal
    program         TEXT,              -- 'falcon_ignite' | 'xlr8' | 'ma_pilot' | 'open'
    created_at      TEXT DEFAULT (datetime('now'))
);

-- One row per matched pair per cycle
CREATE TABLE IF NOT EXISTS matches (
    id              TEXT PRIMARY KEY,  -- uuid4
    employee_a_id   TEXT NOT NULL REFERENCES employees(id),
    employee_b_id   TEXT NOT NULL REFERENCES employees(id),
    cycle_id        TEXT NOT NULL REFERENCES cycles(id),
    matched_date    TEXT DEFAULT (datetime('now')),
    status          TEXT DEFAULT 'pending',
    -- status: pending | nudged | scheduled | completed | ghosted
    awardco_code_a  TEXT,              -- placeholder, filled manually for now
    awardco_code_b  TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- Post-meeting feedback (one row per match, updated by each party)
CREATE TABLE IF NOT EXISTS completions (
    id              TEXT PRIMARY KEY,  -- uuid4
    match_id        TEXT NOT NULL REFERENCES matches(id),
    completed_date  TEXT,
    confirmed_by_a  INTEGER DEFAULT 0,
    confirmed_by_b  INTEGER DEFAULT 0,
    feedback_a      TEXT,
    feedback_b      TEXT,
    rating_a        INTEGER,           -- 1-5
    rating_b        INTEGER,           -- 1-5
    created_at      TEXT DEFAULT (datetime('now'))
);

-- One row per matching cycle
CREATE TABLE IF NOT EXISTS cycles (
    id              TEXT PRIMARY KEY,  -- uuid4
    program         TEXT DEFAULT 'open',
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    total_opted_in  INTEGER DEFAULT 0,
    total_matched   INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);
```

### Notes on schema choices
- SQLite uses `TEXT` for UUIDs and timestamps (ISO8601 strings). `db.py` handles conversion.
- Employee primary key is Slack user ID (not a generated UUID) — simplifies every lookup.
- `matches` has no unique constraint on `(employee_a_id, employee_b_id)` across cycles — the
  deduplication check in `matching.py` queries history instead. This makes reruns safe.

---

## Matching Algorithm (`matching.py`)

### Hard constraints (edges only added if ALL pass)
1. Different `manager` (normalized lowercase)
2. Different `department` (normalized lowercase)
3. Same `region` (timezone overlap proxy)
4. Not previously matched (check `matches` table)

### Soft scoring (edge weights, all additive)
| Signal | Weight | Logic |
|---|---|---|
| Goals similarity | 0–3 | Keyword overlap between `goals` fields |
| Interests similarity | 0–3 | Keyword overlap between `interests` fields |
| Level diversity | 0–2 | Senior↔Junior scores higher than Mid↔Mid |
| Tenure diversity | 0–2 | Veteran (>18mo) ↔ New hire (<6mo) scores highest |

### Matching approach
- Build a weighted graph where nodes = opted-in employees, edges = valid pairs
- `networkx.max_weight_matching(G, maxcardinality=True)` maximizes total weight while pairing
  as many people as possible
- Leftovers (odd count, or isolated nodes) flagged to admin channel

### `run_matching_cycle(cycle_id: str) -> tuple[list[tuple], list[str]]`
Returns `(pairs, unmatched_ids)`. Writes nothing to DB itself — caller (`app.py`) handles writes.

---

## APScheduler Jobs

All jobs defined in `app.py:start_scheduler()`, fired on app startup.

| Job | Trigger | Action |
|---|---|---|
| `run_cycle_start` | Cron: configurable (e.g. every 2 weeks, Monday 9am) | Run matching, send intro DMs |
| `send_nudges` | Interval: daily | Find `pending` matches >48hr old, send nudge, set `nudged` |
| `send_end_of_cycle_reminders` | Cron: 3 days before cycle `end_date` | DM all non-completed pairs |
| `post_cycle_summary` | Cron: at cycle `end_date` | Post stats to admin channel, ghost stragglers |

For the prototype, cycle timing can be set via environment variables or hardcoded constants
at the top of `app.py`. No admin UI needed.

---

## Slack App Configuration (api.slack.com/apps)

### OAuth Scopes (Bot Token)
```
chat:write
im:write
im:read
users:read
users:read.email
commands
```

### Event Subscriptions
```
message.im        (for future: bot DM responses)
app_home_opened   (optional: home tab)
```

### Slash Commands
```
/crowdbrew     → opt-in flow
/brewstatus    → admin only: current cycle stats
```

### Interactivity
Enable Interactivity. All payloads handled via Socket Mode — no Request URL needed.

### App-Level Token
Scopes required: `connections:write`

---

## `db.py` Interface Contract

Every function in `db.py` should follow this pattern:

```python
def get_opted_in_employees(region: str | None = None) -> list[dict]:
    """Return all opted-in employees, optionally filtered by region."""
    with get_db() as conn:
        ...
```

Key functions to implement:
- `init_db()` — create tables if not exist, called at startup
- `upsert_employee(data: dict) -> None`
- `get_opted_in_employees(region=None) -> list[dict]`
- `get_match_history() -> set[frozenset]` — returns set of frozensets of employee ID pairs
- `create_cycle(program, start_date, end_date) -> str` — returns cycle_id
- `create_match(employee_a_id, employee_b_id, cycle_id) -> str` — returns match_id
- `update_match_status(match_id, status) -> None`
- `get_pending_matches_older_than(hours: int) -> list[dict]`
- `upsert_completion(match_id, confirmed_by, rating, feedback) -> None`
- `get_cycle_stats(cycle_id) -> dict`

---

## `ui.py` Interface Contract

All Block Kit construction. Every function returns a `dict` or `list[dict]`.

Key functions:
- `opt_in_modal() -> dict` — full modal payload for `/crowdbrew`
- `match_intro_dm(partner: dict, calendly_link: str) -> list[dict]` — blocks for match DM
- `nudge_dm(partner_name: str) -> list[dict]`
- `end_of_cycle_reminder_dm(days_left: int) -> list[dict]`
- `completion_feedback_modal(match_id: str) -> dict`
- `reward_placeholder_dm(code: str) -> list[dict]`
- `cycle_summary_block(stats: dict) -> list[dict]` — for admin channel post
- `unmatched_alert_block(names: list[str]) -> list[dict]`

Never build Block Kit dicts inline in `app.py` handlers. Always call a `ui.py` function.
