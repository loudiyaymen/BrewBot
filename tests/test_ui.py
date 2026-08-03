"""Tests for Block Kit template builders."""

import ui


def _block_ids(view):
    return [b.get("block_id") for b in view["blocks"] if "block_id" in b]


def _find_block(view, block_id):
    return next(b for b in view["blocks"] if b.get("block_id") == block_id)


def test_opt_in_modal_has_all_new_blocks():
    ids = _block_ids(ui.opt_in_modal())
    for expected in ("block_mode", "block_partner", "block_connection_type",
                     "block_goals", "block_interests", "block_frequency",
                     "block_meeting_pref", "block_location", "block_program"):
        assert expected in ids


def test_initial_options_match_a_provided_option():
    """Slack rejects the modal if initial_option isn't an exact copy of an option."""
    modal = ui.opt_in_modal()
    for block in modal["blocks"]:
        element = block.get("element", {})
        initial = element.get("initial_option")
        if initial is not None:
            assert initial in element["options"], (
                f"{block.get('block_id')}: initial_option must exactly equal one of options"
            )


def test_mode_selector_has_three_options():
    modal = ui.opt_in_modal()
    opts = _find_block(modal, "block_mode")["element"]["options"]
    assert {o["value"] for o in opts} == {"matched", "self_select", "group"}


def test_goals_are_checkboxes():
    modal = ui.opt_in_modal()
    goals = _find_block(modal, "block_goals")["element"]
    assert goals["type"] == "checkboxes"
    assert "find_mentor" in {o["value"] for o in goals["options"]}


def test_partner_block_is_optional_users_select():
    modal = ui.opt_in_modal()
    partner = _find_block(modal, "block_partner")
    assert partner["optional"] is True
    assert partner["element"]["type"] == "users_select"


def test_score_bar_rendering():
    assert ui._score_bar(0.0).startswith("░░░░░░░░░░")
    bar = ui._score_bar(6.7)
    assert bar.count("█") == 7 and "67%" in bar
    full = ui._score_bar(10.0)
    assert full.count("█") == 10 and "100%" in full


def test_match_intro_shows_reason_and_score():
    blocks = ui.match_intro_dm({"name": "Sam", "department": "eng"},
                               "https://c", "mid-1", "You share goals.", 8.2)
    text = blocks[0]["text"]["text"]
    assert "Sam" in text and "You share goals." in text and "Match strength" in text


def test_match_intro_omits_score_when_zero():
    blocks = ui.match_intro_dm({"name": "Sam", "department": "eng"}, "https://c", "mid-1")
    assert "Match strength" not in blocks[0]["text"]["text"]


def test_match_intro_has_confirm_button():
    blocks = ui.match_intro_dm({"name": "Sam", "department": "eng"}, "https://c", "mid-42")
    actions = [b for b in blocks if b.get("accessory", {}).get("action_id") == "confirm_met"]
    assert actions and actions[0]["accessory"]["value"] == "mid-42"


def test_group_intro_lists_members():
    members = [{"name": "Gina", "department": "hr"}, {"name": "Greg", "department": "it"}]
    blocks = ui.group_intro_dm(members, "https://c", "grp-1")
    assert "Gina" in blocks[0]["text"]["text"] and "Greg" in blocks[0]["text"]["text"]


def test_round_optin_dm_has_three_buttons():
    blocks = ui.round_optin_dm()
    action_ids = {e["action_id"] for b in blocks if b["type"] == "actions" for e in b["elements"]}
    assert action_ids == {"round_optin_yes", "round_optin_skip", "round_optin_out"}


def test_followup_dm_buttons_carry_completion_id():
    blocks = ui.followup_dm("Sam", "comp-9")
    ids = []
    for b in blocks:
        if b["type"] == "actions":
            ids += [(e["action_id"], e["value"]) for e in b["elements"]]
        elif b.get("accessory"):
            ids.append((b["accessory"]["action_id"], b["accessory"]["value"]))
    assert ("followup_yes", "comp-9") in ids
    assert ("followup_reconnect", "comp-9") in ids


def test_opt_in_confirmation_text_surfaces_history():
    assert "different CrowdStrikers" in ui.opt_in_confirmation_text("Jo", 4)
    assert "different CrowdStrikers" not in ui.opt_in_confirmation_text("Jo", 0)


def test_admin_panel_has_action_buttons():
    blocks = ui.admin_panel_block()
    action_ids = {e["action_id"] for b in blocks if b["type"] == "actions" for e in b["elements"]}
    assert action_ids == {
        "admin_run_matching",
        "admin_export_current",
        "admin_export_all",
        "admin_export_participants",
    }


def test_run_matching_modal_cadence_options():
    modal = ui.run_matching_modal()
    assert modal["callback_id"] == "run_matching_modal"
    cadence = _find_block(modal, "block_cadence")["element"]
    assert {o["value"] for o in cadence["options"]} == {"biweekly", "monthly"}
    # initial_option must exactly equal one of the options (Slack rejects otherwise)
    assert cadence["initial_option"] in cadence["options"]
