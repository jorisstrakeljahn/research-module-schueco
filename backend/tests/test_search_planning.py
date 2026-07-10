from app.research.planning import contextual_query, plan_deep_research_seeds


def test_region_context_is_added_without_changing_global_query():
    assert contextual_query("adaptive facade", "global") == "adaptive facade"
    assert "Germany" in contextual_query("adaptive facade", "dach")


def test_holistic_plan_adds_six_backend_managed_pestel_lenses():
    focused = plan_deep_research_seeds(
        query="adaptive facade",
        keywords=["vacuum glazing"],
        region="europe",
        holistic_pestel=True,
    )
    assert len(focused) == 8
    assert focused[0].startswith("adaptive facade Europe")
    assert "vacuum glazing" in focused
    assert any("regulation standards" in seed for seed in focused)
