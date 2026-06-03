import pytest

from sentinel.config import load_config


def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(text)
    return p


def test_env_substitution_and_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "secret-topic")
    monkeypatch.delenv("NTFY_SERVER", raising=False)
    cfg = load_config(
        _write(
            tmp_path,
            """
            user_agent: "test"
            notify:
              type: ntfy
              topic: "${NTFY_TOPIC}"
              server: "${NTFY_SERVER:-https://ntfy.sh}"
            sources:
              - name: q
                type: hackernews
                query: python
            """,
        )
    )
    assert cfg.notifier.url == "https://ntfy.sh/secret-topic"
    assert len(cfg.sources) == 1
    assert cfg.sources[0].name == "q"


def test_default_interval_applied(tmp_path, monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "t")
    cfg = load_config(
        _write(
            tmp_path,
            """
            default_interval: 42
            notify:
              type: ntfy
              topic: "${NTFY_TOPIC}"
            sources:
              - name: q
                type: hackernews
                query: python
            """,
        )
    )
    assert cfg.sources[0].interval == 42


def test_missing_notify_raises(tmp_path):
    with pytest.raises(ValueError, match="notify"):
        load_config(_write(tmp_path, "sources: [{name: q, type: hackernews, query: x}]"))


def test_unknown_source_type_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "t")
    with pytest.raises(ValueError, match="Unknown source type"):
        load_config(
            _write(
                tmp_path,
                """
                notify: {type: ntfy, topic: "${NTFY_TOPIC}"}
                sources:
                  - name: bad
                    type: telepathy
                """,
            )
        )
