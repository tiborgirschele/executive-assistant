
from app.intelligence.household_graph import build_household_graph, ensure_profile_isolation

def test_household_graph_keeps_profiles_isolated():
    graph = build_household_graph(
        principals=[
            {"person_id":"tibor@example.com","tenant":"ea_bot","role":"principal"},
            {"person_id":"liz@example.com","tenant":"ea_bot","role":"family"},
        ]
    )
    assert ensure_profile_isolation(graph) is True
