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
                "block_id": "block_mode",
                "label": {"type": "plain_text", "text": "How would you like to participate?"},
                "element": {
                    "type": "radio_buttons",
                    "action_id": "input_mode",
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "☕ Match me with someone new"},
                        "description": {"type": "plain_text", "text": "I'll be paired based on my goals and interests"},
                        "value": "matched",
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "☕ Match me with someone new"},
                            "description": {"type": "plain_text", "text": "I'll be paired based on my goals and interests"},
                            "value": "matched",
                        },
                        {
                            "text": {"type": "plain_text", "text": "👋 I already have someone in mind"},
                            "description": {"type": "plain_text", "text": "I'll choose them and we'll both be confirmed"},
                            "value": "self_select",
                        },
                        {
                            "text": {"type": "plain_text", "text": "👥 Put me in a group chat (3–4 people)"},
                            "description": {"type": "plain_text", "text": "Great for meeting multiple people at once"},
                            "value": "group",
                        },
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_partner",
                "optional": True,
                "label": {"type": "plain_text", "text": "Who would you like to meet with?"},
                "hint": {"type": "plain_text", "text": "Only used if you picked 'someone in mind' above."},
                "element": {
                    "type": "users_select",
                    "action_id": "input_partner",
                    "placeholder": {"type": "plain_text", "text": "Search for a CrowdStriker…"},
                },
            },
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
                "block_id": "block_connection_type",
                "label": {"type": "plain_text", "text": "What kind of connection are you looking for?"},
                "element": {
                    "type": "static_select",
                    "action_id": "input_connection_type",
                    "placeholder": {"type": "plain_text", "text": "Pick one"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Peer chat — someone at a similar level"}, "value": "peer"},
                        {"text": {"type": "plain_text", "text": "I want to learn — connect me with someone more experienced"}, "value": "mentee"},
                        {"text": {"type": "plain_text", "text": "I want to share — connect me with someone earlier in their career"}, "value": "mentor"},
                        {"text": {"type": "plain_text", "text": "Either works for me"}, "value": "open"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_goals",
                "optional": True,
                "label": {"type": "plain_text", "text": "What are you hoping to get from this chat?"},
                "element": {
                    "type": "checkboxes",
                    "action_id": "input_goals",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Learn about a different part of the business"}, "value": "cross_functional"},
                        {"text": {"type": "plain_text", "text": "Find a mentor or advisor"}, "value": "find_mentor"},
                        {"text": {"type": "plain_text", "text": "Share my experience with someone newer"}, "value": "be_mentor"},
                        {"text": {"type": "plain_text", "text": "Explore a career pivot or new direction"}, "value": "career_pivot"},
                        {"text": {"type": "plain_text", "text": "Get advice on a specific challenge"}, "value": "get_advice"},
                        {"text": {"type": "plain_text", "text": "Collaborate on something"}, "value": "collaborate"},
                        {"text": {"type": "plain_text", "text": "Just meet someone new"}, "value": "networking"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_interests",
                "optional": True,
                "label": {"type": "plain_text", "text": "What topics would you love to talk about?"},
                "element": {
                    "type": "checkboxes",
                    "action_id": "input_interests",
                    "options": [
                        {"text": {"type": "plain_text", "text": "Career growth and development"}, "value": "career"},
                        {"text": {"type": "plain_text", "text": "Leadership and management"}, "value": "leadership"},
                        {"text": {"type": "plain_text", "text": "Technical skills and engineering"}, "value": "technical"},
                        {"text": {"type": "plain_text", "text": "Product and strategy"}, "value": "product"},
                        {"text": {"type": "plain_text", "text": "Sales and customer success"}, "value": "sales"},
                        {"text": {"type": "plain_text", "text": "Culture and belonging"}, "value": "culture"},
                        {"text": {"type": "plain_text", "text": "Work-life balance and wellbeing"}, "value": "wellbeing"},
                        {"text": {"type": "plain_text", "text": "Innovation and new ideas"}, "value": "innovation"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_frequency",
                "label": {"type": "plain_text", "text": "How often would you like to be matched?"},
                "element": {
                    "type": "static_select",
                    "action_id": "input_frequency",
                    "initial_option": {"text": {"type": "plain_text", "text": "Every 2 weeks"}, "value": "biweekly"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Every 2 weeks"}, "value": "biweekly"},
                        {"text": {"type": "plain_text", "text": "Once a month"}, "value": "monthly"},
                        {"text": {"type": "plain_text", "text": "Just this once"}, "value": "once"},
                        {"text": {"type": "plain_text", "text": "Surprise me"}, "value": "random"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_meeting_pref",
                "label": {"type": "plain_text", "text": "How would you prefer to meet?"},
                "element": {
                    "type": "static_select",
                    "action_id": "input_meeting_pref",
                    "initial_option": {"text": {"type": "plain_text", "text": "Either works"}, "value": "either"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Virtual only"}, "value": "virtual"},
                        {"text": {"type": "plain_text", "text": "In-person if possible"}, "value": "inperson"},
                        {"text": {"type": "plain_text", "text": "Either works"}, "value": "either"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "block_location",
                "optional": True,
                "label": {"type": "plain_text", "text": "Your city / office (for in-person)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "input_location",
                    "placeholder": {"type": "plain_text", "text": "e.g. Austin, Sunnyvale, London"},
                },
            },
            {
                "type": "input",
                "block_id": "block_program",
                "label": {"type": "plain_text", "text": "Which program are you joining through?"},
                "element": {
                    "type": "static_select",
                    "action_id": "input_program",
                    "initial_option": {"text": {"type": "plain_text", "text": "Open / Anyone"}, "value": "open"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "Falcon Ignite"}, "value": "falcon_ignite"},
                        {"text": {"type": "plain_text", "text": "XLR8 / Accelerate"}, "value": "xlr8"},
                        {"text": {"type": "plain_text", "text": "M&A Onboarding"}, "value": "ma_pilot"},
                        {"text": {"type": "plain_text", "text": "Open / Anyone"}, "value": "open"},
                    ],
                },
            },
        ],
    }


def _score_bar(match_score: float) -> str:
    """Render a 0–10 score as a 10-cell █/░ bar with a percentage."""
    filled = max(0, min(10, round(match_score)))
    return "█" * filled + "░" * (10 - filled) + f"  {int(match_score * 10)}%"


def match_intro_dm(
    partner: dict,
    calendly_link: str,
    match_id: str,
    match_reason: str = "",
    match_score: float = 0.0,
) -> list[dict]:
    """Blocks for the match introduction DM sent to both employees."""
    icebreakers = random.sample(ICEBREAKERS, min(3, len(ICEBREAKERS)))
    reason_text = f"\n\n_{match_reason}_" if match_reason else ""
    score_line = f"\n\n*Match strength:* {_score_bar(match_score)}" if match_score else ""

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"☕ *Your CrowdBrew match is here!*\n\n"
                    f"You've been paired with *{partner['name']}* ({partner['department']})."
                    f"{reason_text}"
                    f"{score_line}"
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


def group_intro_dm(members: list[dict], calendly_link: str, group_id: str) -> list[dict]:
    """Blocks for the group-chat introduction DM sent to each group member."""
    names = ", ".join(f"*{m['name']}* ({m['department']})" for m in members)
    icebreakers = random.sample(ICEBREAKERS, min(3, len(ICEBREAKERS)))
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"👥 *Your CrowdBrew group is here!*\n\n"
                    f"You've been grouped with {names}.\n\n"
                    f"Start a group DM and find a time that works for everyone."
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Grab 20–30 minutes together whenever works:"},
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
    ]


def round_optin_dm() -> list[dict]:
    """Blocks for the per-round opt-in prompt sent at the start of each cycle."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "☕ *A new CrowdBrew round is starting!*\n\nAre you in for this round?",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Yes, match me!"},
                    "action_id": "round_optin_yes",
                    "style": "primary",
                    "value": "yes",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "⏸ Skip this round"},
                    "action_id": "round_optin_skip",
                    "value": "skip",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Opt out"},
                    "action_id": "round_optin_out",
                    "value": "out",
                },
            ],
        },
    ]


def followup_dm(partner_name: str, completion_id: str) -> list[dict]:
    """Blocks for the follow-up check-in DM sent a week after a chat is confirmed."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"👋 Hey! Just checking in on your CrowdBrew with *{partner_name}*.\n\n"
                    f"Did the chat deliver what you were looking for?"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Yes!"},
                    "action_id": "followup_yes",
                    "style": "primary",
                    "value": completion_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🤔 Partially"},
                    "action_id": "followup_partial",
                    "value": completion_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Not really"},
                    "action_id": "followup_no",
                    "value": completion_id,
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Want to connect with them again sometime?"},
            "accessory": {
                "type": "button",
                "text": {"type": "plain_text", "text": "👍 Yes"},
                "action_id": "followup_reconnect",
                "value": completion_id,
            },
        },
    ]


def opt_in_confirmation_text(name: str, unique_matches: int = 0) -> str:
    """Text for the post-opt-in confirmation DM, surfacing never-repeat match history."""
    text = (
        f"Hey {name} 👋\n\n"
        "You're in for CrowdBrew! We'll match you with someone from a different team "
        "and send you an intro when the next round kicks off.\n\n"
        "Keep an eye on your DMs."
    )
    if unique_matches > 0:
        text += (
            f"\n\nYou've connected with *{unique_matches} different CrowdStrikers* so far 🎉 "
            "Your next match will be someone completely new."
        )
    return text


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


def admin_panel_block() -> list[dict]:
    """Blocks for the /brewadmin control panel posted to the admin channel."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "🛠️ *CrowdBrew Admin Panel*\n\n"
                    "Trigger a matching round or export program data."
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "☕ Run matching now"},
                    "action_id": "admin_run_matching",
                    "style": "primary",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔔 Nudge pending matches"},
                    "action_id": "admin_nudge_now",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📄 Export current cycle"},
                    "action_id": "admin_export_current",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🗂️ Export all matches"},
                    "action_id": "admin_export_all",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "👥 Export participants"},
                    "action_id": "admin_export_participants",
                },
            ],
        },
    ]


def run_matching_modal() -> dict:
    """Modal for choosing the cadence before triggering a matching run."""
    return {
        "type": "modal",
        "callback_id": "run_matching_modal",
        "title": {"type": "plain_text", "text": "Run matching"},
        "submit": {"type": "plain_text", "text": "Run now"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Start a new CrowdBrew round. Pick which cadence this run is for.",
                },
            },
            {
                "type": "input",
                "block_id": "block_cadence",
                "label": {"type": "plain_text", "text": "Cadence for this run"},
                "element": {
                    "type": "static_select",
                    "action_id": "input_cadence",
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "Biweekly"},
                        "value": "biweekly",
                    },
                    "options": [
                        {"text": {"type": "plain_text", "text": "Biweekly"}, "value": "biweekly"},
                        {"text": {"type": "plain_text", "text": "Monthly"}, "value": "monthly"},
                    ],
                },
            },
        ],
    }
