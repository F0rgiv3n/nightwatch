from sentinel.models import Item, SourceState
from sentinel.storage import Storage


def test_state_roundtrip(tmp_path):
    s = Storage(tmp_path / "db.sqlite")
    assert s.get_state("src").etag is None
    s.save_state(SourceState("src", etag="abc", last_modified="yesterday"))
    state = s.get_state("src")
    assert state.etag == "abc"
    assert state.last_modified == "yesterday"
    s.close()


def test_history_and_seen(tmp_path):
    s = Storage(tmp_path / "db.sqlite")
    assert not s.has_history("src")
    s.record("src", [Item(id="1", title="A"), Item(id="2", title="B")])
    assert s.has_history("src")
    seen = s.get_seen("src")
    assert set(seen) == {"1", "2"}
    # Re-recording an edited item updates its hash.
    before = seen["1"]
    s.record("src", [Item(id="1", title="A edited")])
    assert s.get_seen("src")["1"] != before
    s.close()
