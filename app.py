"""BrewBot — Slack bot entry point: handlers, scheduler, startup."""

import logging
import os
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import awardco
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
# Per-round opt-in prompt goes out ahead of the cycle (default: Friday 9am before it).
ROUND_OPTIN_CRON = os.getenv("ROUND_OPTIN_CRON", "0 9 * * FRI")

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


def _selected_value(block: dict, action_id: str, default=None):
    """Read a static_select/radio value from a modal state block, or default."""
    opt = block.get(action_id, {}).get("selected_option")
    return opt["value"] if opt else default


def _checkbox_values(block: dict, action_id: str) -> list[str]:
    """Read the list of selected checkbox values from a modal state block."""
    opts = block.get(action_id, {}).get("selected_options") or []
    return [o["value"] for o in opts]


@app.view("opt_in_modal")
def handle_opt_in_submit(ack, view, client, body):
    """Persist the opt-in form submission and send a confirmation DM."""
    ack()
    user_id = body["user"]["id"]
    values = view["state"]["values"]

    tenure_map = {"lt6": 3, "6to18": 12, "gt18": 24}
    mode = _selected_value(values["block_mode"], "input_mode", "matched")
    partner_id = values["block_partner"]["input_partner"].get("selected_user")

    data = {
        "id": user_id,
        "name": values["block_name"]["input_name"]["value"],
        "department": values["block_department"]["input_department"]["value"],
        "manager": values["block_manager"]["input_manager"]["value"],
        "region": values["block_region"]["input_region"]["selected_option"]["value"],
        "job_level": values["block_level"]["input_level"]["selected_option"]["value"],
        "tenure_months": tenure_map[values["block_tenure"]["input_tenure"]["selected_option"]["value"]],
        "goals_list": _checkbox_values(values["block_goals"], "input_goals"),
        "interests_list": _checkbox_values(values["block_interests"], "input_interests"),
        "connection_type": _selected_value(values["block_connection_type"], "input_connection_type", "open"),
        "match_frequency": _selected_value(values["block_frequency"], "input_frequency", "biweekly"),
        "meeting_preference": _selected_value(values["block_meeting_pref"], "input_meeting_pref", "either"),
        "location": (values["block_location"]["input_location"].get("value") or None),
        "program": _selected_value(values["block_program"], "input_program", "open"),
        "mode": mode,
        "opted_in": 1,
        "opt_in_date": datetime.utcnow().isoformat(),
    }

    # Self-select participants are matched immediately and skip the automated pool
    # this round (round_optin=0), so they aren't double-matched.
    if mode == "self_select" and partner_id and partner_id != user_id:
        data["round_optin"] = 0

    db.upsert_employee(data)
    log.info("opt-in: %s (%s) mode=%s", data["name"], user_id, mode)

    if mode == "self_select" and partner_id and partner_id != user_id:
        _handle_self_select(client, user_id, data["name"], partner_id)
        return

    try:
        unique_matches = db.get_unique_match_count(user_id)
        client.chat_postMessage(
            channel=user_id,
            text=ui.opt_in_confirmation_text(data["name"], unique_matches),
        )
    except Exception:
        log.exception("failed to send opt-in DM to %s", user_id)


def _handle_self_select(client, user_id: str, user_name: str, partner_id: str) -> None:
    """Create a self-selected match immediately and DM both participants."""
    cycle = db.get_current_cycle()
    if not cycle:
        start = datetime.utcnow().isoformat()
        end = (datetime.utcnow() + timedelta(days=CYCLE_DURATION_DAYS)).isoformat()
        cycle_id = db.create_cycle("open", start, end)
    else:
        cycle_id = cycle["id"]

    # The picked partner may not have opted in yet — make sure a row exists for the FK.
    partner_name = "your chosen partner"
    try:
        info = client.users_info(user=partner_id)
        partner_name = info["user"]["profile"].get("real_name") or info["user"]["name"]
    except Exception:
        log.info("could not resolve name for self-select partner %s", partner_id)
    db.ensure_employee_stub(partner_id, partner_name)

    match_id = db.create_match(user_id, partner_id, cycle_id, match_type="self_select")
    initiator = {"id": user_id, "name": user_name, "department": "your pick"}
    partner = {"id": partner_id, "name": partner_name, "department": ""}
    for sender, other in [(user_id, partner), (partner_id, initiator)]:
        try:
            client.chat_postMessage(
                channel=sender,
                blocks=ui.match_intro_dm(other, CALENDLY_LINK, match_id),
                text="☕ Your CrowdBrew match is set!",
            )
        except Exception:
            log.exception("failed to send self-select intro to %s", sender)


# ── Matching cycle ───────────────────────────────────────────────────────────

def send_match_intros(pairs: list[dict], cycle_id: str) -> None:
    """Write each pair to DB and DM both employees their intro (with score + reason)."""
    for pair in pairs:
        employee_a, employee_b = pair["a"], pair["b"]
        score, reason = pair["score"], pair["reason"]
        match_id = db.create_match(
            employee_a["id"], employee_b["id"], cycle_id,
            match_type="matched", match_score=score, match_reason=reason,
        )
        for sender, partner in [(employee_a, employee_b), (employee_b, employee_a)]:
            try:
                app.client.chat_postMessage(
                    channel=sender["id"],
                    blocks=ui.match_intro_dm(partner, CALENDLY_LINK, match_id, reason, score),
                    text=f"☕ You've been matched with {partner['name']} for CrowdBrew!",
                )
            except Exception:
                log.exception("failed to send intro DM to %s", sender["id"])


def send_group_intros(groups: list[list[dict]], cycle_id: str) -> None:
    """Record each group as pairwise matches and DM every member the group intro."""
    for group in groups:
        group_id = str(uuid.uuid4())
        # Record group membership as pairwise match rows so history/rewards still work.
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                db.create_match(a["id"], b["id"], cycle_id, match_type="group", group_id=group_id)
        for member in group:
            others = [m for m in group if m["id"] != member["id"]]
            try:
                app.client.chat_postMessage(
                    channel=member["id"],
                    blocks=ui.group_intro_dm(others, CALENDLY_LINK, group_id),
                    text="👥 Your CrowdBrew group is here!",
                )
            except Exception:
                log.exception("failed to send group intro to %s", member["id"])


def broadcast_round_optin() -> None:
    """DM prior participants the per-round opt-in prompt before matching runs."""
    for emp in db.get_opted_in_employees():
        try:
            app.client.chat_postMessage(
                channel=emp["id"],
                blocks=ui.round_optin_dm(),
                text="A new CrowdBrew round is starting — are you in? ☕",
            )
        except Exception:
            log.exception("failed to send round opt-in prompt to %s", emp["id"])


def run_cycle_start(cycle_type: str = "biweekly") -> None:
    """Run the matching cycle: pair employees, send intros, alert admin of unmatched."""
    log.info("matching cycle starting (%s)", cycle_type)
    start_date = datetime.utcnow().isoformat()
    end_date = (datetime.utcnow() + timedelta(days=CYCLE_DURATION_DAYS)).isoformat()
    cycle_id = db.create_cycle("open", start_date, end_date)

    opted_in = db.get_opted_in_employees_for_cycle(cycle_type)
    if len(opted_in) < 2:
        log.warning("not enough opted-in employees to match (%d)", len(opted_in))
        return

    match_history = db.get_match_history()
    pairs, groups, unmatched_ids = matching.run_matching_cycle(opted_in, match_history)

    employees_by_id = {e["id"]: e for e in opted_in}
    send_match_intros(pairs, cycle_id)
    send_group_intros(groups, cycle_id)

    grouped_count = sum(len(g) for g in groups)
    total_matched = len(pairs) * 2 + grouped_count
    db.update_cycle_totals(cycle_id, total_opted_in=len(opted_in), total_matched=total_matched)

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

    log.info(
        "cycle %s complete: %d pairs, %d groups, %d unmatched",
        cycle_id, len(pairs), len(groups), len(unmatched_ids),
    )


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


def send_followup_checkins() -> None:
    """DM both parties a follow-up check-in 7 days after their chat was confirmed."""
    completions = db.get_completions_needing_followup(days=7)
    for c in completions:
        for user_id, partner_name in [
            (c["employee_a_id"], c["employee_b_name"]),
            (c["employee_b_id"], c["employee_a_name"]),
        ]:
            try:
                app.client.chat_postMessage(
                    channel=user_id,
                    blocks=ui.followup_dm(partner_name, c["completion_id"]),
                    text=f"How did your CrowdBrew with {partner_name} go? ☕",
                )
            except Exception:
                log.exception("failed to send follow-up to %s", user_id)
        db.mark_followup_sent(c["completion_id"])
    if completions:
        log.info("follow-up check-ins sent: %d", len(completions))


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

def issue_reward(match_id: str) -> None:
    """Drop the AwardCo reward file for a confirmed match, falling back to admin."""
    reward = db.get_match_for_reward(match_id)
    if not reward:
        return
    employee_ids = [reward["employee_a_id"], reward["employee_b_id"]]
    if awardco.issue_points(match_id, employee_ids):
        return
    # SFTP unconfigured or failed → ask the EX team to issue codes manually.
    try:
        app.client.chat_postMessage(
            channel=ADMIN_CHANNEL_ID,
            text=(
                f"⚠️ CrowdBrew reward needs manual issuance for match `{match_id}` "
                f"(AwardCo SFTP unavailable). Employees: {', '.join(employee_ids)} — "
                f"10 CrowdPoints each."
            ),
        )
    except Exception:
        log.exception("failed to post reward fallback to admin channel")


@app.action("confirm_met")
def handle_confirm_met(ack, action, client, body):
    """Mark match completed, issue the reward, and open the feedback modal."""
    ack()
    match_id = action["value"]
    db.update_match_status(match_id, "completed")
    issue_reward(match_id)
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view=ui.completion_feedback_modal(match_id),
        )
    except Exception:
        log.exception("failed to open feedback modal for match %s", match_id)


# ── Per-round opt-in buttons ─────────────────────────────────────────────────

@app.action("round_optin_yes")
@app.action("round_optin_skip")
@app.action("round_optin_out")
def handle_round_optin(ack, action, client, body):
    """Record a per-round opt-in choice (yes / skip / opt-out)."""
    ack()
    user_id = body["user"]["id"]
    db.set_round_optin(user_id, action["value"])
    replies = {
        "yes": "You're in for this round! 🎉 We'll send your match soon.",
        "skip": "No problem — we'll skip you this round and check back next time.",
        "out": "You've been opted out of CrowdBrew. Run `/crowdbrew` anytime to rejoin.",
    }
    try:
        client.chat_postMessage(channel=user_id, text=replies.get(action["value"], "Got it!"))
    except Exception:
        log.exception("failed to ack round opt-in for %s", user_id)


# ── Follow-up check-in buttons ───────────────────────────────────────────────

@app.action("followup_yes")
@app.action("followup_partial")
@app.action("followup_no")
def handle_followup_response(ack, action, client, body):
    """Record how a chat delivered against the employee's goals."""
    ack()
    user_id = body["user"]["id"]
    completion_id = action["value"]
    response = action["action_id"].replace("followup_", "")  # yes / partial / no
    db.record_followup(completion_id, user_id, response, reconnect=False)
    try:
        client.chat_postMessage(channel=user_id, text="Thanks for the feedback — it helps us make better matches! 🙏")
    except Exception:
        log.exception("failed to ack follow-up for %s", user_id)


@app.action("followup_reconnect")
def handle_followup_reconnect(ack, action, client, body):
    """Record that the employee wants to reconnect with their match."""
    ack()
    user_id = body["user"]["id"]
    completion_id = action["value"]
    db.record_followup(completion_id, user_id, "reconnect", reconnect=True)
    try:
        client.chat_postMessage(channel=user_id, text="Love it — we'll keep that in mind for future rounds! 👍")
    except Exception:
        log.exception("failed to ack reconnect for %s", user_id)


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

def _cron(expr: str) -> CronTrigger:
    """Build a CronTrigger from a standard 5-field 'minute hour dom month dow' string."""
    m, h, dom, mon, dow = expr.split()
    return CronTrigger(minute=m, hour=h, day=dom, month=mon, day_of_week=dow)


def start_scheduler() -> BackgroundScheduler:
    """Configure and start APScheduler with all recurring jobs."""
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        run_cycle_start,
        _cron(CYCLE_START_CRON),
        id="run_cycle_start",
        replace_existing=True,
    )

    # Per-round opt-in prompt, sent ahead of the cycle so people can respond in time.
    scheduler.add_job(
        broadcast_round_optin,
        _cron(ROUND_OPTIN_CRON),
        id="broadcast_round_optin",
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

    scheduler.add_job(
        send_followup_checkins,
        "interval",
        hours=24,
        id="send_followup_checkins",
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
