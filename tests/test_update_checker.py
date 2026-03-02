import json

import screenalert_core.utils.update_checker as update_checker


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_check_for_updates_available(monkeypatch):
    monkeypatch.setattr(
        update_checker,
        "urlopen",
        lambda req, timeout=0: _FakeResponse({"tag_name": "v9.9.9", "html_url": "https://example/release"}),
    )
    info = update_checker.check_for_updates(timeout_sec=0.1)
    assert info is not None
    assert info.is_update_available is True
    assert info.latest_version == "v9.9.9"


def test_check_for_updates_handles_errors(monkeypatch):
    def raise_error(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(update_checker, "urlopen", raise_error)
    info = update_checker.check_for_updates(timeout_sec=0.1)
    assert info is None
