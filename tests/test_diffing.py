from sentinel.diffing import content_hash, diff
from sentinel.models import Item, Snapshot


def _snap(items):
    return Snapshot(source="t", items=items)


def test_new_items_are_detected():
    snap = _snap([Item(id="1", title="A"), Item(id="2", title="B")])
    changes = diff({}, snap)
    assert [c.kind for c in changes] == ["new", "new"]
    assert {c.item.id for c in changes} == {"1", "2"}


def test_unchanged_items_produce_no_changes():
    item = Item(id="1", title="A", url="http://x")
    previous = {"1": content_hash(item)}
    assert diff(previous, _snap([item])) == []


def test_updated_item_is_detected():
    old = Item(id="1", title="A")
    new = Item(id="1", title="A (edited)")
    changes = diff({"1": content_hash(old)}, _snap([new]))
    assert len(changes) == 1
    assert changes[0].kind == "updated"


def test_disappearance_is_not_reported():
    # "1" was seen before but is absent now -> no change emitted.
    previous = {"1": content_hash(Item(id="1", title="A"))}
    assert diff(previous, _snap([])) == []


def test_content_hash_ignores_id():
    assert content_hash(Item(id="1", title="A")) == content_hash(Item(id="2", title="A"))
