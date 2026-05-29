"""Block Kit templates for all BrewBot messages and modals."""

import random

ICEBREAKERS: list[str] = [
    "What's a project you're most proud of lately?",
    "What made you join this company?",
    "What are you learning outside of work right now?",
    "What's one thing you wish more people at this company knew about your team?",
    "If you could swap jobs with anyone here for a week, who would it be?",
]


def opt_in_modal() -> dict:
    """Full modal payload for the /crowdbrew opt-in flow."""
    return {
        "type": "modal",
        "callback_id": "opt_in_modal",
        "title": {"type": "plain_text", "text": "Join CrowdBrew"},
        "submit": {"type": "plain_text", "text": "I'm in!"},
        "close": {"type": "plain_text", "text": "Maybe later"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "☕ *Welcome to CrowdBrew!*\nGet matched with someone from a different team for a virtual coffee chat.",
                },
            },
            {"type": "divider"},
            {
                "type": "input",
                "block_id": "block_name",
                "label": {"type": "plain_text", "text": "Your name"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input_name",
                    "placeholder": {"type": "plain_text", "text": "e.g. Jane Smith"},
                },
            },
            {
                "type": "input",
                "block_id": "block_department",
                "label": {"type": "plain_text", "text": "Department"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input_department",
                    "placeholder": {"type": "plain_text", "text": "e.g. Engineering, Product, Marketing"},
                },
            },
            {
                "type": "input",
                "block_id": "block_manager",
                "label": {"type": "plain_text", "text": "Manager's name"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input_manager",
                    "placeholder": {"type": "plain_text", "text": "e.g. John Doe"},
                },
            },
            {
                "type": "input",
                "block_id": "block_region",
                "label": {"type": "plain_text", "text": "Region"},
                "element": {
                    "type": "static_select",
                    "action_id": "input_region",
                    "placeholder": {"type": "plain_text", "text": "Select your region"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Americas"}, "value": "americas"},
                        {"text": {"type": "plain_text", "text": "EMEA"}, "value": "emea"},
                        {"text": {"type": "plain_text", "text": "APAC"}, "value": "apac"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_level",
                "label": {"type": "plain_text", "text": "Job level"},
                "element": {
                    "type": "static_select",
                    "action_id": "input_level",
                    "placeholder": {"type": "plain_text", "text": "Select your level"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Junior"}, "value": "junior"},
                        {"text": {"type": "plain_text", "text": "Mid"}, "value": "mid"},
                        {"text": {"type": "plain_text", "text": "Senior"}, "value": "senior"},
                        {"text": {"type": "plain_text", "text": "Lead"}, "value": "lead"},
                        {"text": {"type": "plain_text", "text": "Exec"}, "value": "exec"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_tenure",
                "label": {"type": "plain_text", "text": "How long have you been here?"},
                "element": {
                    "type": "static_select",
                    "action_id": "input_tenure",
                    "placeholder": {"type": "plain_text", "text": "Select tenure"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Less than 6 months"}, "value": "lt6"},
                        {"text": {"type": "plain_text", "text": "6–18 months"}, "value": "6to18"},
                        {"text": {"type": "plain_text", "text": "18+ months"}, "value": "gt18"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_goals",
                "label": {"type": "plain_text", "text": "What are you hoping to get from CrowdBrew? (optional)"},
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input_goals",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "e.g. Learn about product, find a mentor"},
                },
            },
            {
                "type": "input",
                "block_id": "block_interests",
                "label": {"type": "plain_text", "text": "Interests outside of work (optional)"},
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input_interests",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "e.g. hiking, sci-fi, side projects"},
                },
            },
        ],
    }


def match_intro_dm(partner: dict, calendly_link: str, match_id: str) -> list[dict]:
    """Blocks for the match introduction DM sent to both employees."""
    icebreakers = random.sample(ICEBREAKERS, min(3, len(ICEBREAKERS)))
    goals_snippet = (partner.get("goals") or "").strip()
    goals_text = f"> {goals_snippet}" if goals_snippet else "_No goals shared — ask them directly!_"

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"☕ *Your CrowdBrew match is here!*\n\n"
                    f"You've been paired with *{partner['name']}* ({partner['department']}).\n\n"
                    f"A bit about them:\n{goals_text}"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Grab 20–30 minutes whenever works for both of you:"},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "📅 Schedule with Calendly →"},
                "url": calendly_link,
                "action_id": "open_calendly",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Some conversation starters if you want them:\n"
                + "\n".join(f"• {q}" for q in icebreakers),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Once you've met, hit the button below so we can send your coffee reimbursement.",
            },
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "✓ We Already Met!"},
                "action_id": "confirm_met",
                "value": match_id,
                "style": "primary",
            },
        },
    ]


def nudge_dm(partner_name: str, match_id: str, calendly_link: str) -> list[dict]:
    """Blocks for the 48-hour nudge DM."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"Hey — just a quick nudge 👋\n\n"
                    f"You and *{partner_name}* haven't scheduled your CrowdBrew chat yet.\n"
                    f"It's a short one — even 20 minutes makes a difference."
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📅 Schedule with Calendly →"},
                    "url": calendly_link,
                    "action_id": "open_calendly_nudge",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✓ We Already Met!"},
                    "action_id": "confirm_met",
                    "value": match_id,
                    "style": "primary",
                },
            ],
        },
    ]


def end_of_cycle_reminder_dm(
    partner_name: str, days_left: int, calendly_link: str, match_id: str = ""
) -> list[dict]:
    """Blocks for the end-of-cycle reminder DM sent 3 days before close."""
    day_str = f"{days_left} day{'s' if days_left != 1 else ''}"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"Last call ☕\n\n"
                    f"The current CrowdBrew round closes in *{day_str}*.\n"
                    f"If you and *{partner_name}* haven't met yet, now's a great time."
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📅 Schedule with Calendly →"},
                    "url": calendly_link,
                    "action_id": "open_calendly_reminder",
                },
                *(
                    [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✓ We Already Met!"},
                            "action_id": "confirm_met",
                            "value": match_id,
                            "style": "primary",
                        }
                    ]
                    if match_id
                    else []
                ),
            ],
        },
    ]


def completion_feedback_modal(match_id: str) -> dict:
    """Modal for post-meeting feedback, opened after clicking 'We Already Met'."""
    return {
        "type": "modal",
        "callback_id": "completion_feedback_modal",
        "private_metadata": match_id,
        "title": {"type": "plain_text", "text": "How did it go?"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Skip"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Glad you connected! Quick feedback helps us improve CrowdBrew.",
                },
            },
            {
                "type": "input",
                "block_id": "block_rating",
                "label": {"type": "plain_text", "text": "How was your chat?"},
                "element": {
                    "type": "static_select",
                    "action_id": "input_rating",
                    "placeholder": {"type": "plain_text", "text": "Rate your experience"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "⭐⭐⭐⭐⭐  Amazing"}, "value": "5"},
                        {"text": {"type": "plain_text", "text": "⭐⭐⭐⭐  Good"}, "value": "4"},
                        {"text": {"type": "plain_text", "text": "⭐⭐⭐  Okay"}, "value": "3"},
                        {"text": {"type": "plain_text", "text": "⭐⭐  Meh"}, "value": "2"},
                        {"text": {"type": "plain_text", "text": "⭐  Didn't click"}, "value": "1"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_feedback",
                "label": {"type": "plain_text", "text": "Anything else? (optional)"},
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input_feedback",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "What went well? What could be better?"},
                },
            },
        ],
    }


def reward_placeholder_dm(partner_name: str) -> list[dict]:
    """Blocks for the reward placeholder DM sent after a chat is confirmed."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "Love it — glad you connected! 🎉\n\n"
                    "Your $10 coffee reimbursement code is on its way.\n"
                    "The CrowdBrew team will send it to you shortly.\n\n"
                    "Thanks for making the program work. See you next round."
                ),
            },
        }
    ]


def cycle_summary_block(stats: dict) -> list[dict]:
    """Blocks for the end-of-cycle summary posted to the admin channel."""
    total_opted_in = stats.get("total_opted_in", 0)
    total_matched = stats.get("total_matched", 0)
    total_completed = stats.get("total_completed", 0)
    total_ghosted = stats.get("total_ghosted", 0)
    avg_rating = stats.get("avg_rating")

    match_pct = round(total_matched / total_opted_in * 100) if total_opted_in else 0
    complete_pct = round(total_completed / (total_matched // 2) * 100) if total_matched else 0
    rating_text = f"{avg_rating}/5" if avg_rating else "n/a"

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"📊 *CrowdBrew — Cycle Wrap-Up*\n\n"
                    f"• Opted in: {total_opted_in}\n"
                    f"• Successfully matched: {total_matched} ({match_pct}%)\n"
                    f"• Completed their chat: {total_completed} ({complete_pct}%)\n"
                    f"• Ghosted / no response: {total_ghosted}\n"
                    f"• Average rating: {rating_text}"
                ),
            },
        }
    ]


def unmatched_alert_block(names: list[str]) -> list[dict]:
    """Blocks for the unmatched-employees alert posted to the admin channel."""
    names_list = "\n".join(f"• {n}" for n in names)
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"⚠️ *Unmatched employees — {len(names)} employee(s)*\n\n"
                    f"The following couldn't be matched this round "
                    f"(odd count, no valid pairs, or region with too few participants):\n\n"
                    f"{names_list}\n\n"
                    f"Please reach out to them directly if needed."
                ),
            },
        }
    ]


def brewstatus_block(stats: dict) -> list[dict]:
    """Blocks for the /brewstatus ephemeral response (admin only)."""
    start = (stats.get("start_date") or "—")[:10]
    end = (stats.get("end_date") or "—")[:10]
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*CrowdBrew — Current Cycle Status*\n\n"
                    f"Cycle started: {start}\n"
                    f"Closes: {end}\n\n"
                    f"• Opted in: {stats.get('total_opted_in', 0)}\n"
                    f"• Matched: {stats.get('total_matched', 0)}\n"
                    f"• Completed: {stats.get('total_completed', 0)}\n"
                    f"• Pending: {stats.get('total_pending', 0)}\n"
                    f"• Nudged (no response): {stats.get('total_nudged', 0)}"
                ),
            },
        }
    ]
