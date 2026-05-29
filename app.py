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
