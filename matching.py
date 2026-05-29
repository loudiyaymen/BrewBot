"""Matching engine for BrewBot — pure functions, no DB or Slack calls."""

import networkx as nx

LEVEL_RANK: dict[str, int] = {
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "lead": 4,
    "exec": 5,
}


def norm(s: str) -> str:
    """Lowercase and strip a string for comparison."""
    return (s or "").strip().lower()


def score_pair(a: dict, b: dict) -> float:
    """Compute soft compatibility score for a candidate pair (higher = better match)."""
    score = 0.0

    goals_a = set(norm(a.get("goals") or "").split())
    goals_b = set(norm(b.get("goals") or "").split())
    score += min(len(goals_a & goals_b), 3)

    interests_a = set(norm(a.get("interests") or "").split())
    interests_b = set(norm(b.get("interests") or "").split())
    score += min(len(interests_a & interests_b), 3)

    level_a = LEVEL_RANK.get(norm(a.get("job_level") or ""), 0)
    level_b = LEVEL_RANK.get(norm(b.get("job_level") or ""), 0)
    score += min(abs(level_a - level_b), 2)

    tenure_a = a.get("tenure_months") or 0
    tenure_b = b.get("tenure_months") or 0
    if (tenure_a < 6 and tenure_b > 18) or (tenure_b < 6 and tenure_a > 18):
        score += 2

    return score


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


def run_matching_cycle(
    opted_in: list[dict],
    match_history: set[frozenset],
) -> tuple[list[tuple], list[str]]:
    """Build graph, run matching, return (pairs_as_employee_dicts, unmatched_ids).

    Pure function — no DB access, no Slack calls. Caller handles all side effects.
    """
    G = build_graph(opted_in, match_history)
    raw_pairs, unmatched_ids = make_pairs(G)

    by_id = {e["id"]: e for e in opted_in}
    pairs = [(by_id[a], by_id[b]) for a, b in raw_pairs]
    return pairs, unmatched_ids


# ── Standalone smoke test ────────────────────────────────────────────────────

if __name__ == "__main__":
    sample: list[dict] = [
        {"id": "U001", "name": "Alice", "department": "engineering", "manager": "M1",
         "region": "americas", "job_level": "junior", "tenure_months": 3,
         "goals": "learn product design", "interests": "hiking reading"},
        {"id": "U002", "name": "Bob", "department": "product", "manager": "M2",
         "region": "americas", "job_level": "senior", "tenure_months": 24,
         "goals": "mentor junior engineers", "interests": "sci-fi reading"},
        {"id": "U003", "name": "Carol", "department": "marketing", "manager": "M3",
         "region": "americas", "job_level": "mid", "tenure_months": 12,
         "goals": "understand engineering", "interests": "hiking photography"},
        {"id": "U004", "name": "Dave", "department": "sales", "manager": "M4",
         "region": "emea", "job_level": "senior", "tenure_months": 30,
         "goals": "cross-functional work", "interests": "travel cooking"},
        {"id": "U005", "name": "Eve", "department": "hr", "manager": "M5",
         "region": "americas", "job_level": "lead", "tenure_months": 48,
         "goals": "learn about tech", "interests": "writing"},
    ]

    pairs, unmatched = run_matching_cycle(sample, set())
    print(f"Pairs ({len(pairs)}):")
    for a, b in pairs:
        print(f"  {a['name']} ↔ {b['name']}  (score: {score_pair(a, b):.1f})")
    print(f"Unmatched ({len(unmatched)}): {unmatched}")

    # Verify hard constraints
    for a, b in pairs:
        assert norm(a["manager"]) != norm(b["manager"]), "Same manager!"
        assert norm(a["department"]) != norm(b["department"]), "Same department!"
        assert norm(a["region"]) == norm(b["region"]), "Different region!"
    print("All hard constraints satisfied.")
