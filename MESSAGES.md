# MESSAGES.md — BrewBot Voice & Copy Guide

All user-facing text should feel like it came from a thoughtful colleague, not a corporate bot.
Warm. Brief. Human. Never robotic or over-excited.

Reference these when implementing `ui.py`.

---

## Tone Principles

- **Warm but not sycophantic.** No "Amazing!" or "Fantastic news!"
- **Brief.** Employees are busy. Get to the point.
- **Optional ≠ ignored.** When something is optional (icebreakers, feedback), frame it as a gift, not a checkbox.
- **Never fake urgency.** Nudges are friendly, not pressure.

---

## Opt-In Confirmation DM

```
Hey {name} 👋

You're in for CrowdBrew! We'll match you with someone from a different team
and send you an intro when the next round kicks off.

Keep an eye on your DMs.
```

---

## Match Intro DM

```
☕ Your CrowdBrew match is here!

You've been paired with *{partner_name}* ({partner_department}).

A bit about them:
> {partner_goals_snippet}

Grab 20–30 minutes whenever works for both of you:
[📅 Schedule with Calendly →] (button)

Some conversation starters if you want them:
• {icebreaker_1}
• {icebreaker_2}
• {icebreaker_3}

Once you've met, hit the button below so we can send your coffee reimbursement.

[✓ We Already Met!] (button)
```

**Icebreaker examples** (rotate or randomize from a small pool in `ui.py`):
- "What's a project you're most proud of lately?"
- "What made you join this company?"
- "What are you learning outside of work right now?"
- "What's one thing you wish more people at this company knew about your team?"
- "If you could swap jobs with anyone here for a week, who would it be?"

---

## 48-Hour Nudge DM

```
Hey — just a quick nudge 👋

You and *{partner_name}* haven't scheduled your CrowdBrew chat yet.
It's a short one — even 20 minutes makes a difference.

[📅 Schedule with Calendly →] (button)
[✓ We Already Met!] (button, in case you did and forgot to confirm)
```

---

## End-of-Cycle Reminder DM

```
Last call ☕

The current CrowdBrew round closes in *{days_left} days*.
If you and *{partner_name}* haven't met yet, now's a great time.

[📅 Schedule with Calendly →] (button)
[✓ We Already Met!] (button)
```

---

## Reward Placeholder DM

```
Love it — glad you connected! 🎉

Your $10 coffee reimbursement code is on its way.
The CrowdBrew team will send it to you shortly.

Thanks for making the program work. See you next round.
```

---

## Cycle Summary (Admin Channel)

```
📊 *CrowdBrew — Cycle {cycle_id} Wrap-Up*

• Opted in: {total_opted_in}
• Successfully matched: {total_matched} ({match_pct}%)
• Completed their chat: {total_completed} ({complete_pct}%)
• Ghosted / no response: {total_ghosted}
• Unmatched (odd-out or isolated): {unmatched_count}

Unmatched employees:
{unmatched_list}

Average rating (where provided): {avg_rating}/5
```

---

## Unmatched Alert (Admin Channel)

```
⚠️ *Unmatched employees — Cycle {cycle_id}*

The following {count} employee(s) couldn't be matched this round
(odd count, no valid pairs, or region with too few participants):

{names_list}

Please reach out to them directly if needed.
```

---

## /brewstatus Response (Ephemeral, Admin Only)

```
*CrowdBrew — Current Cycle Status*

Cycle started: {start_date}
Closes: {end_date} ({days_remaining} days left)

• Opted in: {total_opted_in}
• Matched: {total_matched}
• Completed: {total_completed}
• Pending: {total_pending}
• Nudged (no response): {total_nudged}
```
