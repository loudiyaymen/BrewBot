"""Matching engine for BrewBot — pure functions, no DB or Slack calls."""

import networkx as nx

LEVEL_RANK: dict[str, int] = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "exec": 5,
}

# Rough ceiling of score_pair used to normalize into a 0–10 strength for the DM.
# goals(3) + interests(3) + level diversity(2) + tenure diversity(2) + mentor bonus(5)
MAX_SCORE = 15.0


def norm(s: str) -> str:
    """Lowercase and strip a string for comparison."""
    return (s or "").strip().lower()


def _goals(e: dict) -> set[str]:
    """Structured goal tags for an employee, falling back to free-text words."""
    if e.get("goals_list"):
        return {norm(g) for g in e["goals_list"]}
    return set(norm(e.get("goals") or "").split())


def _interests(e: dict) -> set[str]:
    """Structured interest tags for an employee, falling back to free-text words."""
    if e.get("interests_list"):
        return {norm(i) for i in e["interests_list"]}
    return set(norm(e.get("interests") or "").split())


def _mentor_complement(a: dict, b: dict) -> bool:
    """True if one wants to mentor (share) and the other wants to be mentored (learn)."""
    ca, cb = a.get("connection_type"), b.get("connection_type")
    return (ca == "mentor" and cb == "mentee") or (ca == "mentee" and cb == "mentor")


def _tenure_diverse(a: dict, b: dict) -> bool:
    """True if one is new (<6mo) and the other seasoned (>18mo)."""
    ta = a.get("tenure_months") or 0
    tb = b.get("tenure_months") or 0
    return (ta < 6 and tb > 18) or (tb < 6 and ta > 18)


def score_pair(a: dict, b: dict) -> float:
    """Compute soft compatibility score for a candidate pair (higher = better match)."""
    score = 0.0

    score += min(len(_goals(a) & _goals(b)), 3)
    score += min(len(_interests(a) & _interests(b)), 3)

    level_a = LEVEL_RANK.get(norm(a.get("job_level") or ""), 0)
    level_b = LEVEL_RANK.get(norm(b.get("job_level") or ""), 0)
    score += min(abs(level_a - level_b), 2)

    if _tenure_diverse(a, b):
        score += 2

    # Mentor/mentee pairing is the strongest signal; a small nudge if either is open.
    if _mentor_complement(a, b):
        score += 5
    elif a.get("connection_type") == "open" or b.get("connection_type") == "open":
        score += 1

    return score


def explain_pair(a: dict, b: dict) -> str:
    """Build a short human-readable 'why you two' line from the same match signals."""
    reasons: list[str] = []

    if _mentor_complement(a, b):
        reasons.append("one of you is looking to mentor and the other to learn")

    shared_goals = _goals(a) & _goals(b)
    if shared_goals:
        reasons.append("you're hoping to get similar things out of the chat")

    shared_interests = _interests(a) & _interests(b)
    if shared_interests:
        reasons.append("you share interests to talk about")

    if _tenure_diverse(a, b):
        reasons.append("you bring different amounts of time at the company")

    if norm(a.get("department") or "") != norm(b.get("department") or ""):
        reasons.append(
            f"you work in different areas ({a.get('department')} and {b.get('department')})"
        )

    if not reasons:
        return "You were paired to meet someone new from a different team."

    joined = reasons[0]
    if len(reasons) > 1:
        joined = ", ".join(reasons[:-1]) + f", and {reasons[-1]}"
    return "You two were matched because " + joined + "."


def normalized_score(a: dict, b: dict) -> float:
    """Map score_pair onto a 0–10 scale for the compatibility strength bar."""
    return min(score_pair(a, b) / MAX_SCORE * 10.0, 10.0)


def build_graph(
    employees: list[dict],
    match_history: set[frozenset],
) -> nx.Graph:
    """Build a weighted compatibility graph; edges only exist for valid pairs."""
    G = nx.Graph()
    G.add_nodes_from(e["id"] for e in employees)

    for i, a in enumerate(employees):
        for b in employees[i + 1:]:
            if norm(a["manager"]) == norm(b["manager"]):
                continue
            if norm(a["department"]) == norm(b["department"]):
                continue
            if norm(a["region"]) != norm(b["region"]):
                continue
            # Program filter: only match within the same program, unless one is open.
            prog_a, prog_b = norm(a.get("program") or "open"), norm(b.get("program") or "open")
            if prog_a != prog_b and prog_a != "open" and prog_b != "open":
                continue
            # Location filter: if both insist on in-person, they must share a city/office.
            if (
                a.get("meeting_preference") == "inperson"
                and b.get("meeting_preference") == "inperson"
                and norm(a.get("location") or "") != norm(b.get("location") or "")
            ):
                continue
            if frozenset({a["id"], b["id"]}) in match_history:
                continue
            # +1 floor so every valid edge has positive weight for max-cardinality matching
            G.add_edge(a["id"], b["id"], weight=score_pair(a, b) + 1)

    return G


def make_pairs(G: nx.Graph) -> tuple[list[tuple], list]:
    """Run max-weight matching and return (matched_edges, unmatched_node_ids)."""
    matched_edges = nx.max_weight_matching(G, maxcardinality=True, weight="weight")
    matched_nodes = {n for edge in matched_edges for n in edge}
    unmatched = [n for n in G.nodes if n not in matched_nodes]
    return list(matched_edges), unmatched


def make_groups(employees: list[dict], group_size: int = 3) -> list[list[dict]]:
    """Chunk employees who opted for group matching into groups of `group_size`.

    Leftovers that can't form a full group are distributed round-robin into the
    existing groups. Returns an empty list if there aren't enough people for one group.
    """
    groups: list[list[dict]] = []
    pool = list(employees)

    while len(pool) >= group_size:
        groups.append(pool[:group_size])
        pool = pool[group_size:]

    if pool and groups:
        for i, leftover in enumerate(pool):
            groups[i % len(groups)].append(leftover)

    return groups


def run_matching_cycle(
    opted_in: list[dict],
    match_history: set[frozenset],
    group_size: int = 3,
) -> tuple[list[dict], list[list[dict]], list[str]]:
    """Split out group participants, pair the rest, and return match metadata.

    Pure function — no DB access, no Slack calls. Caller handles all side effects.

    Returns:
        pairs:     list of {"a": emp, "b": emp, "score": 0-10, "reason": str}
        groups:    list of employee-dict lists (for group-mode participants)
        unmatched: list of employee ids from the 1:1 pool with no partner
    """
    group_wanted = [e for e in opted_in if e.get("connection_type") == "group"
                    or e.get("mode") == "group"]
    group_ids = {e["id"] for e in group_wanted}
    pool = [e for e in opted_in if e["id"] not in group_ids]

    groups = make_groups(group_wanted, group_size) if group_wanted else []

    G = build_graph(pool, match_history)
    raw_pairs, unmatched_ids = make_pairs(G)

    by_id = {e["id"]: e for e in pool}
    pairs: list[dict] = []
    for a_id, b_id in raw_pairs:
        a, b = by_id[a_id], by_id[b_id]
        pairs.append({
            "a": a,
            "b": b,
            "score": normalized_score(a, b),
            "reason": explain_pair(a, b),
        })

    # People who wanted a group but couldn't form one fall back to being unmatched.
    if group_wanted and not groups:
        unmatched_ids += [e["id"] for e in group_wanted]

    return pairs, groups, unmatched_ids


# ── Standalone smoke test ────────────────────────────────────────────────────

if __name__ == "__main__":
    sample: list[dict] = [
        {"id": "U001", "name": "Alice", "department": "engineering", "manager": "M1",
         "region": "americas", "job_level": "junior", "tenure_months": 3,
         "goals_list": ["find_mentor"], "interests_list": ["career"],
         "connection_type": "mentee", "program": "open"},
        {"id": "U002", "name": "Bob", "department": "product", "manager": "M2",
         "region": "americas", "job_level": "senior", "tenure_months": 24,
         "goals_list": ["be_mentor"], "interests_list": ["career", "leadership"],
         "connection_type": "mentor", "program": "open"},
        {"id": "U003", "name": "Carol", "department": "marketing", "manager": "M3",
         "region": "americas", "job_level": "mid", "tenure_months": 12,
         "goals_list": ["networking"], "interests_list": ["culture"],
         "connection_type": "peer", "program": "open"},
        {"id": "U004", "name": "Dave", "department": "sales", "manager": "M4",
         "region": "emea", "job_level": "senior", "tenure_months": 30,
         "goals_list": ["collaborate"], "interests_list": ["sales"],
         "connection_type": "open", "program": "open"},
        {"id": "U005", "name": "Eve", "department": "hr", "manager": "M5",
         "region": "americas", "job_level": "lead", "tenure_months": 48,
         "goals_list": ["get_advice"], "interests_list": ["wellbeing"],
         "connection_type": "open", "program": "falcon_ignite"},
    ]

    pairs, groups, unmatched = run_matching_cycle(sample, set())
    print(f"Pairs ({len(pairs)}):")
    for p in pairs:
        print(f"  {p['a']['name']} ↔ {p['b']['name']}  "
              f"(strength: {p['score']:.1f}/10)")
        print(f"    reason: {p['reason']}")
    print(f"Groups ({len(groups)}): {[[e['name'] for e in g] for g in groups]}")
    print(f"Unmatched ({len(unmatched)}): {unmatched}")

    # Verify hard constraints
    for p in pairs:
        a, b = p["a"], p["b"]
        assert norm(a["manager"]) != norm(b["manager"]), "Same manager!"
        assert norm(a["department"]) != norm(b["department"]), "Same department!"
        assert norm(a["region"]) == norm(b["region"]), "Different region!"
        pa, pb = norm(a["program"]), norm(b["program"])
        assert pa == pb or pa == "open" or pb == "open", "Program mismatch!"
    print("All hard constraints satisfied.")

    # Mentor/mentee complementary pair should score highest.
    assert normalized_score(sample[0], sample[1]) > normalized_score(sample[2], sample[3]), \
        "Mentor/mentee pair should outrank a plain pair"
    print("Mentor/mentee scoring verified.")

    # Group matching smoke test.
    group_sample = [dict(e, connection_type="group") for e in sample]
    _, gr, _ = run_matching_cycle(group_sample, set())
    assert gr and sum(len(g) for g in gr) == len(group_sample), "Group split lost people"
    print(f"Group matching verified: {[[e['name'] for e in g] for g in gr]}")
