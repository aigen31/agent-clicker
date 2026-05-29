import logging

from agent_clicker.observability.broadcaster import LogBroadcaster
from agent_clicker.observability.logging import record_to_dict


def test_broadcaster_buffers_and_snapshot() -> None:
    b = LogBroadcaster(buffer_size=3)
    for i in range(5):
        b.publish_nowait({"i": i})
    snap = b.snapshot()
    assert [r["i"] for r in snap] == [2, 3, 4]


def test_record_to_dict_has_required_fields() -> None:
    rec = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1, msg="hello", args=(), exc_info=None
    )
    d = record_to_dict(rec)
    assert d["msg"] == "hello"
    assert d["level"] == "INFO"
    assert "ts" in d
