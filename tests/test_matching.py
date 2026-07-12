"""Tests for the matching engine (pure functions)."""

import matching
from conftest import make_employee


def test_norm():
    assert matching.norm("  Hello ") == "hello"
    assert matching.norm(None) == ""


def test_score_shared_goals_and_interests():
    a = make_employee(id="A", goals_list=["find_mentor", "networking"], interests_list=["career"])
    b = make_employee(id="B", goals_list=["find_mentor"], interests_list=["career", "culture"])
    # 1 shared goal + 1 shared interest, both open (+1)
    assert matching.score_pair(a, b) >= 2


def test_mentor_mentee_bonus_is_strongest():
    mentee = make_employee(id="A", connection_type="mentee")
    mentor = make_employee(id="B", connection_type="mentor")
    peer1 = make_employee(id="C", connection_type="peer")
    peer2 = make_employee(id="D", connection_type="peer")
    assert matching.score_pair(mentee, mentor) >= 5
    assert matching.score_pair(mentee, mentor) > matching.score_pair(peer1, peer2)


def test_open_connection_gets_small_bonus_not_mentor_bonus():
    a = make_employee(id="A", connection_type="open")
    b = make_employee(id="B", connection_type="peer")
    assert matching.score_pair(a, b) == 1  # only the open +1


def test_tenure_diversity_bonus():
    new = make_employee(id="A", tenure_months=2, connection_type="peer")
    seasoned = make_employee(id="B", tenure_months=30, connection_type="peer")
    assert matching.score_pair(new, seasoned) >= 2


def test_goals_fall_back_to_free_text():
    a = make_employee(id="A", goals_list=[], goals="hiking reading")
    b = make_employee(id="B", goals_list=[], goals="reading writing")
    assert matching._goals(a) == {"hiking", "reading"}
    assert len(matching._goals(a) & matching._goals(b)) == 1


def test_explain_pair_mentions_signals():
    a = make_employee(id="A", connection_type="mentee", department="engineering",
                      goals_list=["career_pivot"], tenure_months=2)
    b = make_employee(id="B", connection_type="mentor", department="product",
                      goals_list=["career_pivot"], tenure_months=30)
    reason = matching.explain_pair(a, b)
    assert "mentor" in reason and "learn" in reason
    assert "engineering" in reason and "product" in reason


def test_explain_pair_default_when_no_signals():
    a = make_employee(id="A", department="eng", connection_type="peer")
    b = make_employee(id="B", department="eng", connection_type="peer")
    reason = matching.explain_pair(a, b)
    assert reason == "You were paired to meet someone new from a different team."


def test_normalized_score_capped_at_ten():
    a = make_employee(id="A", connection_type="mentee", tenure_months=2,
                      goals_list=["a", "b", "c", "d"], interests_list=["x", "y", "z", "w"],
                      job_level="junior")
    b = make_employee(id="B", connection_type="mentor", tenure_months=40,
                      goals_list=["a", "b", "c", "d"], interests_list=["x", "y", "z", "w"],
                      job_level="exec")
    assert 0 <= matching.normalized_score(a, b) <= 10


# ── Hard constraints in build_graph ──────────────────────────────────────────

def _pair_ids(pairs):
    return {frozenset((p["a"]["id"], p["b"]["id"])) for p in pairs}


def test_same_manager_never_matched():
    a = make_employee(id="A", manager="M", department="eng")
    b = make_employee(id="B", manager="M", department="product")
    pairs, _, unmatched = matching.run_matching_cycle([a, b], set())
    assert not pairs and set(unmatched) == {"A", "B"}


def test_same_department_never_matched():
    a = make_employee(id="A", manager="M1", department="eng")
    b = make_employee(id="B", manager="M2", department="eng")
    pairs, _, _ = matching.run_matching_cycle([a, b], set())
    assert not pairs


def test_different_region_never_matched():
    a = make_employee(id="A", manager="M1", department="eng", region="americas")
    b = make_employee(id="B", manager="M2", department="product", region="emea")
    pairs, _, _ = matching.run_matching_cycle([a, b], set())
    assert not pairs


def test_program_filter_blocks_cross_program_unless_open():
    a = make_employee(id="A", manager="M1", department="eng", program="falcon_ignite")
    b = make_employee(id="B", manager="M2", department="product", program="xlr8")
    pairs, _, _ = matching.run_matching_cycle([a, b], set())
    assert not pairs

    c = make_employee(id="C", manager="M3", department="sales", program="open")
    pairs2, _, _ = matching.run_matching_cycle([a, c], set())
    assert _pair_ids(pairs2) == {frozenset(("A", "C"))}


def test_location_filter_blocks_inperson_different_city():
    a = make_employee(id="A", manager="M1", department="eng",
                      meeting_preference="inperson", location="Austin")
    b = make_employee(id="B", manager="M2", department="product",
                      meeting_preference="inperson", location="London")
    pairs, _, _ = matching.run_matching_cycle([a, b], set())
    assert not pairs


def test_location_filter_allows_inperson_same_city():
    a = make_employee(id="A", manager="M1", department="eng",
                      meeting_preference="inperson", location="Austin")
    b = make_employee(id="B", manager="M2", department="product",
                      meeting_preference="inperson", location="austin")  # case-insensitive
    pairs, _, _ = matching.run_matching_cycle([a, b], set())
    assert _pair_ids(pairs) == {frozenset(("A", "B"))}


def test_match_history_prevents_repeat():
    a = make_employee(id="A", manager="M1", department="eng")
    b = make_employee(id="B", manager="M2", department="product")
    history = {frozenset(("A", "B"))}
    pairs, _, _ = matching.run_matching_cycle([a, b], history)
    assert not pairs


def test_run_cycle_returns_score_and_reason():
    a = make_employee(id="A", manager="M1", department="eng", connection_type="mentee")
    b = make_employee(id="B", manager="M2", department="product", connection_type="mentor")
    pairs, _, _ = matching.run_matching_cycle([a, b], set())
    assert len(pairs) == 1
    assert pairs[0]["score"] > 0 and pairs[0]["reason"]


# ── Group matching ───────────────────────────────────────────────────────────

def test_make_groups_chunks_and_distributes_leftovers():
    people = [make_employee(id=f"U{i}") for i in range(7)]
    groups = matching.make_groups(people, group_size=3)
    # 7 people -> two groups of 3, leftover distributed -> sizes 4 and 3
    assert sum(len(g) for g in groups) == 7
    assert len(groups) == 2
    assert sorted(len(g) for g in groups) == [3, 4]


def test_make_groups_too_few_returns_empty():
    assert matching.make_groups([make_employee(id="U1")], group_size=3) == []


def test_group_participants_pulled_out_of_pairing():
    pool = [
        make_employee(id="P1", manager="M1", department="eng"),
        make_employee(id="P2", manager="M2", department="product"),
        make_employee(id="G1", manager="M3", department="hr", mode="group"),
        make_employee(id="G2", manager="M4", department="it", mode="group"),
        make_employee(id="G3", manager="M5", department="legal", mode="group"),
    ]
    pairs, groups, _ = matching.run_matching_cycle(pool, set())
    paired_ids = {p["a"]["id"] for p in pairs} | {p["b"]["id"] for p in pairs}
    assert not ({"G1", "G2", "G3"} & paired_ids)
    assert groups and {e["id"] for e in groups[0]} == {"G1", "G2", "G3"}


def test_group_wanted_but_too_few_falls_back_to_unmatched():
    pool = [
        make_employee(id="P1", manager="M1", department="eng"),
        make_employee(id="P2", manager="M2", department="product"),
        make_employee(id="G1", manager="M3", department="hr", mode="group"),
    ]
    pairs, groups, unmatched = matching.run_matching_cycle(pool, set())
    assert groups == []
    assert "G1" in unmatched
