# BrewBot

Slack bot for CrowdBrew — automated coffee-chat pairing for ~11,000 employees.

**Stack:** Python · Slack Bolt (Socket Mode) · APScheduler · SQLite · networkx

---

## Table of Contents

1. [What you'll need](#1--what-youll-need)
2. [Create the Slack app](#2--create-the-slack-app)
3. [Run it locally](#3--run-it-locally)
4. [Environment variables](#4--environment-variables)
5. [Using the bot in Slack](#5--using-the-bot-in-slack)
6. [Running the tests](#6--running-the-tests)
7. [Deploy to Railway (24/7 hosting)](#7--deploy-to-railway-247-hosting)
8. [Deploy with Docker](#8--deploy-with-docker)
9. [File reference](#9--file-reference)
10. [Known gaps](#10--known-gaps)

---

## 1 — What you'll need

- **Python 3.11+** installed locally (`python3 --version` to check).
- A **Slack workspace** where you have permission to install apps. A free personal
  workspace is perfect for testing — create one at [slack.com/create](https://slack.com/create).
- A **Calendly link** (or any scheduling URL) to hand to matched employees. A free
  Calendly account works.
- *(Optional, production only)* AwardCo SFTP credentials for automated reward points.
  Without them the bot falls back to posting a manual-reward reminder in your admin
  channel — fine for testing.

You do **not** need ngrok or any public URL. BrewBot uses Slack **Socket Mode**, which
connects outbound to Slack.

---

## 2 — Create the Slack app

This takes about 10 minutes and is a one-time setup.

### 2.1 Create the app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From Scratch**.
2. Name it **BrewBot**, pick your workspace, and click **Create App**.

### 2.2 Enable Socket Mode (gives you the App token)

1. Sidebar → **Socket Mode** → toggle **Enable Socket Mode** on.
2. When prompted, generate an app-level token (name it anything, e.g. `socket`).
   Give it the `connections:write` scope.
3. **Copy the token that starts with `xapp-`** and save it somewhere — this is your
   `SLACK_APP_TOKEN`. (You can regenerate it later under **Basic Information →
   App-Level Tokens** if you lose it.)

### 2.3 Add bot permission scopes

Sidebar → **OAuth & Permissions** → scroll to **Bot Token Scopes** → **Add an OAuth
Scope** for each of these:

| Scope | Why BrewBot needs it |
|---|---|
| `chat:write` | Send match intros, nudges, and admin reports |
| `im:write` | Open DM channels with employees |
| `im:read` | Read DM channels it opened |
| `users:read` | Resolve a self-selected partner's name |
| `users:read.email` | Optional — associate opt-ins with work email |
| `files:write` | Upload the CSV data exports from the admin panel |
| `commands` | Register the `/crowdbrew`, `/brewstatus`, and `/brewadmin` commands |

### 2.4 Create the slash commands

Sidebar → **Slash Commands** → **Create New Command**, three times:

| Command | Short description | Request URL |
|---|---|---|
| `/crowdbrew` | Join CrowdBrew and get matched | `https://example.com` (ignored — Socket Mode) |
| `/brewstatus` | Admin: current cycle stats | `https://example.com` (ignored — Socket Mode) |
| `/brewadmin` | Admin: run matching + export data | `https://example.com` (ignored — Socket Mode) |

The Request URL is required by the form but unused in Socket Mode — any valid URL works.

### 2.5 Turn on Interactivity

Sidebar → **Interactivity & Shortcuts** → toggle **Interactivity** on. Leave the
Request URL as any placeholder (`https://example.com`). This is what makes the modal
and buttons work.

### 2.6 Install the app (gives you the Bot token)

1. Sidebar → **Install App** → **Install to Workspace** → **Allow**.
2. **Copy the token that starts with `xoxb-`** — this is your `SLACK_BOT_TOKEN`.

### 2.7 Get your admin channel ID

1. In Slack, create or pick a private channel for admin reports (e.g. `#crowdbrew-admin`).
2. Right-click the channel → **Copy Link**. The ID is the last path segment, e.g.
   `https://…/archives/C12345678` → `C12345678`. This is your `ADMIN_CHANNEL_ID`.
3. Invite the bot to it: in that channel type `/invite @BrewBot`. Do the same in any
   channel where employees will run `/crowdbrew`.

You now have all four required secrets: `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`,
`ADMIN_CHANNEL_ID`, and your `CALENDLY_LINK`.

---

## 3 — Run it locally

```bash
git clone <your-repo-url> && cd BrewBot

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure your secrets
cp .env.example .env                 # then edit .env — see the table below

# Start the bot
python3 app.py
```

When it's working you'll see log lines ending in `starting BrewBot`, and the bot will
show as **online** in Slack. The SQLite database is created automatically as
`brewbot.db` in the project folder (delete that file to start from a clean slate).

Stop the bot with `Ctrl+C`.

---

## 4 — Environment variables

Copy `.env.example` to `.env` and fill these in. Only the first four are required.

| Variable | Required | Description |
|---|:---:|---|
| `SLACK_BOT_TOKEN` | ✅ | Bot token from step 2.6 (`xoxb-…`) |
| `SLACK_APP_TOKEN` | ✅ | App-level token from step 2.2 (`xapp-…`) |
| `ADMIN_CHANNEL_ID` | ✅ | Channel ID for admin reports from step 2.7 (`C…`) |
| `CALENDLY_LINK` | ✅ | Scheduling link sent to matched employees |
| `DB_PATH` | | SQLite file path. Omit locally (defaults to `brewbot.db`); Railway/Docker set it to `/data/brewbot.db` |
| `CYCLE_DURATION_DAYS` | | How long a matching round runs (default `14`) |
| `CYCLE_START_CRON` | | When matching runs, 5-field cron (default `0 9 * * MON` — Monday 9am) |
| `ROUND_OPTIN_CRON` | | When the per-round opt-in prompt goes out (default `0 9 * * FRI` — Friday 9am, ahead of the cycle) |
| `NUDGE_INTERVAL_HOURS` | | How often to re-check for un-scheduled matches (default `24`) |
| `AWARDCO_SFTP_HOST` | | AwardCo SFTP server. Leave blank to fall back to manual reward reminders |
| `AWARDCO_SFTP_USER` | | AwardCo SFTP username |
| `AWARDCO_SFTP_KEY` | | Path to the private key file for the SFTP connection |
| `AWARDCO_PROGRAM_ID` | | AwardCo program ID stamped on reward rows (default `CROWDBREW_EARN`) |

> **Rewards without AwardCo:** if the `AWARDCO_SFTP_*` variables are unset, confirming
> a chat posts a "please issue points manually" note to your admin channel instead of
> dropping an SFTP file. This is the expected behavior for local testing.

---

## 5 — Using the bot in Slack

Once the bot is running (locally or on Railway):

1. **Opt in:** type `/crowdbrew` in any channel the bot is in. Fill out the modal —
   participation mode (match me / someone in mind / group), goals and interests
   (checkboxes), connection type (peer / mentor / mentee), frequency, meeting
   preference, and program.
2. **Get matched:** matching normally runs on the `CYCLE_START_CRON` schedule. To see
   a match immediately during testing, opt in with **two or more** test users who can
   legally be paired (different managers, different departments, same region), then
   trigger a cycle now — see the box below.
3. **Match intro DM:** each person gets a DM naming their partner, a plain-language
   "why you two" reason, a compatibility strength bar, icebreakers, a Calendly button,
   and a **"We Already Met"** button.
4. **Confirm + reward:** clicking **We Already Met** marks the match complete, drops
   the AwardCo reward file (or posts the manual-reward reminder to the admin channel),
   and opens a short feedback modal.
5. **Admin view:** run `/brewstatus` to see the current cycle's opt-in / matched /
   completed counts.

### Admin panel — `/brewadmin`

Run **`/brewadmin` inside the admin channel** (`ADMIN_CHANNEL_ID`) — the bot posts a
control panel with three buttons, so you don't need the terminal:

- **☕ Run matching now** — opens a small dialog to pick the cadence (biweekly /
  monthly), then runs a full cycle (same as the scheduled job) and DMs you a
  confirmation.
- **🔔 Nudge pending matches** — immediately DMs both people in every still-pending
  match a reminder to schedule (the automatic nudge only fires after 48h; this runs it
  on demand for all pending matches). DMs you the count.
- **📄 Export current cycle** — CSV of the latest cycle's matches.
- **🗂️ Export all matches** — CSV of every match across all cycles.
- **👥 Export participants** — CSV of every opted-in employee's profile.

**Matches CSV** (one row per match): both partners + their departments/IDs, matched
date, whether the chat took place and when (from **We Already Met**), match score +
reason, both people's ⭐ rating + "anything else" feedback, and the **7-day follow-up**
responses (did it deliver value / want to reconnect).

**Participants CSV** (one row per employee): name, email, department, manager, region,
level, tenure, program, connection type, frequency, meeting preference, location,
selected goals/interests, opt-in status, and how many unique people they've met.

To download either file: click it in Slack → **⋯ → Save** (desktop) or the ⬇ download
button (browser). Both open directly in Excel / Google Sheets.

> `/brewadmin` only works in the admin channel, and the bot must be a member of it
> (`/invite @BrewBot`). If you added the `files:write` scope after first installing the
> app, **reinstall it** (OAuth & Permissions → Reinstall) so exports can upload.

> **Trigger a cycle on demand (for testing).** The scheduled jobs only fire on their
> cron/interval. To run one right now without waiting, open a Python shell in the
> project folder (with your `.env` loaded and the bot's tokens set) and call the job
> functions directly:
>
> ```bash
> python3 -c "import app; app.run_cycle_start()"          # build matches + send intros
> python3 -c "import app; app.broadcast_round_optin()"    # send the per-round opt-in prompt
> python3 -c "import app; app.send_followup_checkins()"   # send 7-day follow-up DMs
> ```
>
> Group chats need **3 or more** people who chose group mode in the same round to form.

---

## 6 — Running the tests

The project ships with a pytest suite (68 tests) that mocks Slack entirely — no tokens
or network required. Run it after any change.

```bash
pip install -r requirements-dev.txt      # pytest + runtime deps
python3 -m pytest                          # run everything
python3 -m pytest tests/test_matching.py -v   # one module, verbose
python3 -m pytest -k mentor                     # only tests matching "mentor"
```

You can also exercise the pure matching engine directly:

```bash
python3 matching.py     # prints sample pairs, groups, scores, and reasons
```

---

## 7 — Deploy to Railway (24/7 hosting)

Railway keeps the bot running in the cloud. Do this once after you've confirmed things
work locally.

1. Push this project to a GitHub repository (GitHub Desktop works if you're not a Git
   user — drag the folder in and click **Publish repository**).
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub
   repo** → select your repo. Railway auto-detects the `Dockerfile`.
3. **Variables** → add each required variable from [section 4](#4--environment-variables)
   (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `ADMIN_CHANNEL_ID`, `CALENDLY_LINK`, plus any
   AwardCo/schedule overrides you want).
4. **New → Volume** → mount path **`/data`**. This persists the SQLite database across
   restarts. (The Dockerfile points `DB_PATH` at `/data/brewbot.db`.)
5. **Deploy.** When the logs show the bot has started, invite it to your Slack channels
   (`/invite @BrewBot`) and try `/crowdbrew`.

---

## 8 — Deploy with Docker

```bash
docker build -t brewbot .
docker run -d \
  --env-file .env \
  -v brewbot_data:/data \
  --restart unless-stopped \
  brewbot
```

---

## 9 — File reference

| File | Purpose |
|---|---|
| `app.py` | Bolt app, all handlers, scheduler startup |
| `matching.py` | Matching logic — pure functions, no DB/Slack |
| `db.py` | SQLite adapter, migrations, and all query helpers |
| `ui.py` | All Block Kit templates (modals + messages) |
| `awardco.py` | AwardCo SFTP reward file drop with admin fallback |
| `tests/` | pytest suite (Slack mocked) |
| `Dockerfile` | Container definition — used by Railway and Docker |
| `railway.toml` | Railway deployment config |
| `.env.example` | Template for all environment variables |

---

## 10 — Known gaps

- **AwardCo SFTP file format** is provisional (pending the AwardCo Connect call) and
  isolated in `awardco._build_reward_rows()` so it can be adjusted in one place.
- **Calendly** is self-serve via link — no API integration or confirmation callback.
- **Employee data** is self-reported at opt-in; there is no HR/Workday sync.
- **Postgres migration:** swap `get_db()` in `db.py` and add a `DATABASE_URL` env var.
  The schema is already compatible.
