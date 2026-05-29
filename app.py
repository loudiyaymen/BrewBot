"""BrewBot — Slack bot entry point: handlers, scheduler, startup."""

import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import db
import matching
import ui

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger(__name__)

CALENDLY_LINK = os.environ["CALENDLY_LINK"]
ADMIN_CHANNEL_ID = os.environ["ADMIN_CHANNEL_ID"]
CYCLE_DURATION_DAYS = int(os.getenv("CYCLE_DURATION_DAYS", "14"))
CYCLE_START_CRON = os.getenv("CYCLE_START_CRON", "0 9 * * MON")

app = App(token=os.environ["SLACK_BOT_TOKEN"])


# ── /crowdbrew — opt-in flow ─────────────────────────────────────────────────

@app.command("/crowdbrew")
def handle_crowdbrew(ack, command, client):
    """Open the opt-in modal when an employee runs /crowdbrew."""
    ack()
    client.views_open(
        trigger_id=command["trigger_id"],
        view=ui.opt_in_modal(),
    )


@app.view("opt_in_modal")
def handle_opt_in_submit(ack, view, client, body):
    """Persist the opt-in form submission and send a confirmation DM."""
    ack()
    user_id = body["user"]["id"]
    values = view["state"]["values"]

    tenure_map = {"lt6": 3, "6to18": 12, "gt18": 24}
    data = {
        "id": user_id,
        "name": values["block_name"]["input_name"]["value"],
        "department": values["block_department"]["input_department"]["value"],
        "manager": values["block_manager"]["input_manager"]["value"],
        "region": values["block_region"]["input_region"]["selected_option"]["value"],
        "job_level": values["block_level"]["input_level"]["selected_option"]["value"],
        "tenure_months": tenure_map[values["block_tenure"]["input_tenure"]["selected_option"]["value"]],
        "goals": (values["block_goals"]["input_goals"].get("value") or ""),
        "interests": (values["block_interests"]["input_interests"].get("value") or ""),
        "opted_in": 1,
        "opt_in_date": datetime.utcnow().isoformat(),
        "program": "open",
    }

    db.upsert_employee(data)
    log.info("opt-in: %s (%s)", data["name"], user_id)

    try:
        client.chat_postMessage(
            channel=user_id,
            text=(
                f"Hey {data['name']} 👋\n\n"
                "You're in for CrowdBrew! We'll match you with someone from a different team "
                "and send you an intro when the next round kicks off.\n\n"
                "Keep an eye on your DMs."
            ),
        )
    except Exception:
        log.exception("failed to send opt-in DM to %s", user_id)


# ── Matching cycle ───────────────────────────────────────────────────────────

def send_match_intros(pairs: list[tuple], employees_by_id: dict, cycle_id: str) -> None:
    """Write each pair to DB and DM both employees their intro message."""
    for employee_a, employee_b in pairs:
        match_id = db.create_match(employee_a["id"], employee_b["id"], cycle_id)
        for sender, partner in [(employee_a, employee_b), (employee_b, employee_a)]:
            try:
                app.client.chat_postMessage(
                    channel=sender["id"],
                    blocks=ui.match_intro_dm(partner, CALENDLY_LINK, match_id),
                    text=f"☕ You've been matched with {partner['name']} for CrowdBrew!",
                )
            except Exception:
                log.exception("failed to send intro DM to %s", sender["id"])


def run_cycle_start() -> None:
    """Run the matching cycle: pair employees, send intros, alert admin of unmatched."""
    log.info("matching cycle starting")
    start_date = datetime.utcnow().isoformat()
    end_date = (datetime.utcnow() + timedelta(days=CYCLE_DURATION_DAYS)).isoformat()
    cycle_id = db.create_cycle("open", start_date, end_date)

    opted_in = db.get_opted_in_employees()
    if len(opted_in) < 2:
        log.warning("not enough opted-in employees to match (%d)", len(opted_in))
        return

    match_history = db.get_match_history()
    pairs, unmatched_ids = matching.run_matching_cycle(opted_in, match_history)

    employees_by_id = {e["id"]: e for e in opted_in}
    send_match_intros(pairs, employees_by_id, cycle_id)
    db.update_cycle_totals(cycle_id, total_opted_in=len(opted_in), total_matched=len(pairs) * 2)

    if unmatched_ids:
        names = [employees_by_id.get(uid, {}).get("name", uid) for uid in unmatched_ids]
        try:
            app.client.chat_postMessage(
                channel=ADMIN_CHANNEL_ID,
                blocks=ui.unmatched_alert_block(names),
                text=f"⚠️ {len(names)} employee(s) couldn't be matched this round.",
            )
        except Exception:
            log.exception("failed to post unmatched alert to admin channel")

    log.info("cycle %s complete: %d pairs, %d unmatched", cycle_id, len(pairs), len(unmatched_ids))


# ── Scheduled jobs ───────────────────────────────────────────────────────────

def send_nudges() -> None:
    """DM employees whose match is still pending after 48 hours."""
    pending = db.get_pending_matches_older_than(48)
    for match in pending:
        for sender_id, partner_name in [
            (match["employee_a_id"], match["employee_b_name"]),
            (match["employee_b_id"], match["employee_a_name"]),
        ]:
            try:
                app.client.chat_postMessage(
                    channel=sender_id,
                    blocks=ui.nudge_dm(partner_name, match["id"], CALENDLY_LINK),
                    text=f"Hey — just a quick nudge 👋 You and {partner_name} haven't scheduled yet.",
                )
            except Exception:
                log.exception("failed to send nudge to %s", sender_id)
        db.update_match_status(match["id"], "nudged")
    if pending:
        log.info("nudges sent: %d", len(pending))


def send_end_of_cycle_reminders() -> None:
    """DM non-completed pairs 3 days before their cycle ends."""
    matches = db.get_active_matches_near_cycle_end(days_threshold=3)
    for match in matches:
        days_left = match.get("days_left", 3)
        for sender_id, partner_name in [
            (match["employee_a_id"], match["employee_b_name"]),
            (match["employee_b_id"], match["employee_a_name"]),
        ]:
            try:
                app.client.chat_postMessage(
                    channel=sender_id,
                    blocks=ui.end_of_cycle_reminder_dm(
                        partner_name, days_left, CALENDLY_LINK, match["id"]
                    ),
                    text=f"Last call ☕ CrowdBrew round closes in {days_left} days.",
                )
            except Exception:
                log.exception("failed to send end-of-cycle reminder to %s", sender_id)
    if matches:
        log.info("end-of-cycle reminders sent: %d", len(matches))


def post_cycle_summary() -> None:
    """Mark stragglers as ghosted and post cycle stats to the admin channel."""
    cycle = db.get_current_cycle()
    if not cycle:
        log.warning("post_cycle_summary: no active cycle found")
        return
    db.ghost_unresolved_matches(cycle["id"])
    stats = db.get_cycle_stats(cycle["id"])
    try:
        app.client.chat_postMessage(
            channel=ADMIN_CHANNEL_ID,
            blocks=ui.cycle_summary_block(stats),
            text="📊 CrowdBrew — Cycle wrap-up",
        )
    except Exception:
        log.exception("failed to post cycle summary")


# ── Actions & view handlers ──────────────────────────────────────────────────

@app.action("confirm_met")
def handle_confirm_met(ack, action, client, body):
    """Mark match completed and open feedback modal."""
    ack()
    match_id = action["value"]
    db.update_match_status(match_id, "completed")
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view=ui.completion_feedback_modal(match_id),
        )
    except Exception:
        log.exception("failed to open feedback modal for match %s", match_id)


@app.view("completion_feedback_modal")
def handle_feedback_submit(ack, view, client, body):
    """Persist feedback and send reward placeholder DM."""
    ack()
    user_id = body["user"]["id"]
    match_id = view["private_metadata"]
    values = view["state"]["values"]

    rating = int(values["block_rating"]["input_rating"]["selected_option"]["value"])
    feedback = values["block_feedback"]["input_feedback"].get("value") or ""

    db.upsert_completion(match_id, confirmed_by=user_id, rating=rating, feedback=feedback)
    log.info("feedback submitted for match %s by %s", match_id, user_id)

    try:
        partner_name = db.get_partner_name(match_id, user_id)
        client.chat_postMessage(
            channel=user_id,
            blocks=ui.reward_placeholder_dm(partner_name),
            text="Love it — glad you connected! 🎉",
        )
    except Exception:
        log.exception("failed to send reward DM to %s", user_id)


# ── /brewstatus — admin command ──────────────────────────────────────────────

@app.command("/brewstatus")
def handle_brewstatus(ack, command, client):
    """Post current cycle stats ephemerally to the caller."""
    ack()
    caller = command["user_id"]
    cycle = db.get_current_cycle()
    if not cycle:
        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=caller,
            text="No active cycle.",
        )
        return
    stats = db.get_cycle_stats(cycle["id"])
    try:
        client.chat_postEphemeral(
            channel=command["channel_id"],
            user=caller,
            blocks=ui.brewstatus_block(stats),
            text="CrowdBrew — Current Cycle Status",
        )
    except Exception:
        log.exception("failed to post brewstatus to %s", caller)


# ── Scheduler ────────────────────────────────────────────────────────────────

def start_scheduler() -> BackgroundScheduler:
    """Configure and start APScheduler with all four recurring jobs."""
    scheduler = BackgroundScheduler()

    # Standard 5-field cron: "minute hour dom month dow"
    cron_parts = CYCLE_START_CRON.split()
    scheduler.add_job(
        run_cycle_start,
        CronTrigger(
            minute=cron_parts[0],
            hour=cron_parts[1],
            day=cron_parts[2],
            month=cron_parts[3],
            day_of_week=cron_parts[4],
        ),
        id="run_cycle_start",
        replace_existing=True,
    )

    nudge_hours = int(os.getenv("NUDGE_INTERVAL_HOURS", "24"))
    scheduler.add_job(
        send_nudges,
        "interval",
        hours=nudge_hours,
        id="send_nudges",
        replace_existing=True,
    )

    scheduler.add_job(
        send_end_of_cycle_reminders,
        "interval",
        hours=24,
        id="send_end_of_cycle_reminders",
        replace_existing=True,
    )

    scheduler.add_job(
        post_cycle_summary,
        "interval",
        hours=24,
        id="post_cycle_summary",
        replace_existing=True,
    )

    scheduler.start()
    log.info("scheduler started with %d jobs", len(scheduler.get_jobs()))
    return scheduler


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    db.init_db()
    log.info("database initialized at %s", db.DB_PATH)
    start_scheduler()
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    log.info("starting BrewBot")
    handler.start()
