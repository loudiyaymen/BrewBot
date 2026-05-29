# BrewBot

Slack bot for CrowdBrew — automated coffee chat pairing for ~11,000 employees.

**Stack:** Python · Slack Bolt (Socket Mode) · APScheduler · SQLite · networkx

---

## Deploying to Railway (Recommended — No Technical Setup)

Railway keeps the bot running 24/7 in the cloud. You only need to do this once.

**Before you start**, you'll need:
- A [GitHub](https://github.com) account
- A [Railway](https://railway.app) account (free, sign in with GitHub)
- Your Slack app tokens (see "Create a Slack App" below)

### Step 1 — Push the code to GitHub

Create a new GitHub repository and push this project to it.
If you're unfamiliar with Git, use [GitHub Desktop](https://desktop.github.com) — drag the
folder in, click "Publish repository".

### Step 2 — Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From Scratch**
2. Give it a name ("BrewBot") and pick your workspace
3. In the sidebar: **Socket Mode** → Enable Socket Mode → Generate a token (name it anything) → **Copy and save this token** (starts with `xapp-`)
4. In the sidebar: **OAuth & Permissions** → under *Bot Token Scopes*, add:
   `chat:write`, `im:write`, `im:read`, `users:read`, `users:read.email`, `commands`
5. In the sidebar: **Slash Commands** → Create `/crowdbrew` and `/brewstatus` (Request URL can be anything — Socket Mode ignores it)
6. In the sidebar: **Interactivity & Shortcuts** → turn on Interactivity (URL can be anything)
7. In the sidebar: **Install App** → **Install to Workspace** → **Copy Bot User OAuth Token** (starts with `xoxb-`)
8. Find your admin Slack channel ID: right-click the channel in Slack → **Copy Link** → the ID is the last part (e.g. `C12345678`)

### Step 3 — Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select the repository you just created
3. Railway will detect the `Dockerfile` automatically
4. Click **Variables** → **Add Variable** for each of these:

| Variable | Value |
|---|---|
| `SLACK_BOT_TOKEN` | Your `xoxb-...` token from Step 2 |
| `SLACK_APP_TOKEN` | Your `xapp-...` token from Step 2 |
| `ADMIN_CHANNEL_ID` | Your admin channel ID (e.g. `C12345678`) |
| `CALENDLY_LINK` | Your Calendly scheduling link |

5. Click **New** → **Volume** → mount path: `/data` (this saves the database permanently)
6. Click **Deploy** — Railway builds and starts the bot

The bot is now live. You'll see "⚡️ Bolt app is running!" in the Railway logs.

### Step 4 — Invite the bot to Slack

In Slack, go to your admin channel and type `/invite @BrewBot`.
Repeat for any channel where employees will use `/crowdbrew`.

### Step 5 — Test it

Type `/crowdbrew` in Slack. The opt-in form should appear.

---

## Running Locally (For Developers)

```bash
git clone <repo> && cd brewbot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your tokens (DB_PATH can be omitted locally)
python app.py
```

No ngrok needed — Socket Mode connects outbound to Slack.

---

## Running with Docker (Alternative to Railway)

```bash
docker build -t brewbot .
docker run -d \
  --env-file .env \
  -v brewbot_data:/data \
  --restart unless-stopped \
  brewbot
```

---

## File Reference

| File | Purpose |
|---|---|
| `CLAUDE.md` | Primary context for Claude Code — start here |
| `ARCHITECTURE.md` | DB schema, data flow, scheduler jobs, interface contracts |
| `TASKS.md` | Phased build checklist |
| `MESSAGES.md` | All user-facing copy and tone guide |
| `Dockerfile` | Container definition — used by Railway and Docker |
| `railway.toml` | Railway deployment config |
| `app.py` | Bolt app, handlers, scheduler startup |
| `matching.py` | Matching logic (pure functions, no DB/Slack) |
| `db.py` | SQLite adapter and all query helpers |
| `ui.py` | All Block Kit templates (modals + messages) |

---

## Known Gaps (Prototype)

- **Rewards (Awardco API):** Not integrated. Bot sends placeholder; EX team sends codes manually.
- **Calendly confirmation:** No API integration — scheduling is self-serve via link.
- **Employee data sync:** Employees self-report at opt-in. No SCIM/HR system sync.
- **Supabase/Postgres migration:** Swap `get_db()` in `db.py` + add `DATABASE_URL` env var. Schema is already compatible.
