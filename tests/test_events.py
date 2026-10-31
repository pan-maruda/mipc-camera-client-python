from unittest.mock import Mock

import pytest

from mipc_camera_client import MipcCameraClient, MipcError, MipcProtocolError


@pytest.fixture
def client():
    c = MipcCameraClient("192.0.2.10")
    c.sid = "0x12"
    c._sn = "synthetic"
    c.shared_secret = "12345"
    yield c
    c.close()


def ack(method, **data):
    return {"type": method + "_ack", "data": {"result": "", **data}}


def test_queue_lifecycle_routes_id_and_converts_timeouts(client):
    event = {"type": "motion", "msg_id": 1}
    client.run_rpc = Mock(
        side_effect=[
            ack("mmq_create", qid="synthetic-queue"),
            ack("ccm_subscribe"),
            {"type": "ccm_msg", "data": {"items": [event]}},
            ack("mmq_destroy"),
        ]
    )
    with client.event_queue() as queue:
        assert queue.poll(timeout=5) == [event]
    calls = client.run_rpc.call_args_list
    assert calls[0].args == ("mmq_create", {"dtimeout": 30000})
    assert calls[1].args[1]["hqid"] == "synthetic-queue"
    assert calls[2].args[1] == {
        "dqid": "synthetic-queue",
        "dtimeout": 5000,
        "hqid": "synthetic-queue",
    }
    assert calls[2].kwargs["request_timeout"] == 7
    assert calls[3].args[0] == "mmq_destroy"
    with pytest.raises(ValueError):
        queue.poll()
    queue.close()  # Idempotent, no extra request.
    assert client.run_rpc.call_count == 4


def test_empty_poll_is_not_an_error(client):
    client.run_rpc = Mock(
        side_effect=[
            ack("mmq_create", qid=123),
            ack("ccm_subscribe"),
            ack("mmq_pick"),
            ack("mmq_destroy"),
        ]
    )
    with client.event_queue() as queue:
        assert queue.poll() == []


def test_subscribe_failure_cleans_up_once(client):
    client.run_rpc = Mock(
        side_effect=[
            ack("mmq_create", qid=123),
            MipcError("ccm_subscribe"),
            ack("mmq_destroy"),
        ]
    )
    with pytest.raises(MipcError):
        client.event_queue()
    assert client.run_rpc.call_count == 3


@pytest.mark.parametrize(
    "reply",
    [
        {},
        {"type": "ccm_msg", "data": {"items": "not-a-list"}},
        ack("mmq_pick", result="failed"),
    ],
)
def test_malformed_or_failed_poll_never_retries(client, reply):
    client.run_rpc = Mock(
        side_effect=[
            ack("mmq_create", qid=123),
            ack("ccm_subscribe"),
            reply,
            ack("mmq_destroy"),
        ]
    )
    with client.event_queue() as queue:
        with pytest.raises(MipcError):
            queue.poll()
    assert client.run_rpc.call_count == 4


def test_queue_does_not_start_without_login(client):
    client.sid = ""
    client.run_rpc = Mock()
    with pytest.raises(MipcProtocolError):
        client.event_queue()
    client.run_rpc.assert_not_called()


@pytest.mark.parametrize(
    "patch",
    [
        {"type": "device"},
        {"code": "io_alert"},
        {"sn": ""},
        {"msg_id": True},
        {"msg_id": 0},
        {"date": "1793376813"},
        {"date": -1},
        {"sn": None},
    ],
)
def test_motion_parser_rejects_other_or_malformed_events(patch):
    from mipc_camera_client.events import MotionEvent

    item = {
        "type": "alert",
        "code": "motion_alert",
        "sn": "synthetic",
        "msg_id": 7,
        "date": 1793376813,
    }
    item.update(patch)
    assert MotionEvent.from_message(item) is None


def test_motion_parser_uses_verified_pulse_schema_without_executing_content():
    from mipc_camera_client.events import MotionEvent

    item = {
        "type": "alert",
        "code": "motion_alert",
        "sn": "private-serial",
        "msg_id": 7,
        "date": 1793376813,
        "p": [{"n": "msg_id", "v": "7"}, {"n": "content", "v": "untrusted text"}],
    }
    event = MotionEvent.from_message(item)
    assert event.message_id == 7 and event.timestamp == 1793376813
    assert event.serial_number == "private-serial"
    assert "private-serial" not in repr(event)
    assert MotionEvent.from_message(None) is None
