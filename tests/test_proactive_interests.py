from core.proactive.interests import InterestStore


def test_interest_store_round_trip(tmp_path):
    store = InterestStore(str(tmp_path / "proactive.db"))
    store.add("Formula 1", ["Formula 1", "Max Verstappen", "Red Bull"], interval_seconds=300)
    items = store.list()
    assert len(items) == 1
    assert items[0].topic == "Formula 1"
    assert "Max Verstappen" in items[0].keywords
    assert store.due()[0].topic == "Formula 1"
    store.mark_checked("Formula 1")
    assert store.due() == []
