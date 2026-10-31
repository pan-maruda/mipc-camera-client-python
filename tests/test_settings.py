"""Synthetic fixtures based on client schemas, never recorded credentials."""

from unittest.mock import Mock

import pytest

from mipc_camera_client import MipcCameraClient
from mipc_camera_client.settings import MipcError, MipcProtocolError, flatten


@pytest.fixture
def client():
    c = MipcCameraClient("192.0.2.10")
    c.sid = "synthetic-session"
    c._sn = "synthetic-camera"
    c.shared_secret = "12345"
    yield c
    c.close()


def ack(method, **data):
    return {"type": method + "_ack", "data": {"ret": {"code": ""}, **data}}


def test_flatten_matches_browser_zero_index():
    assert flatten(
        {"conf": [{"token": "a"}, {"token": "b"}], "tokens": ["eth0", "ra0"]}
    ) == {
        "dconf__x_countz_": 2,
        "dconf": 1,
        "dconf_token": "a",
        "dconf_1": 1,
        "dconf_1_token": "b",
        "dtokens__x_countz_": 2,
        "dtokens": "eth0",
        "dtokens_1": "ra0",
    }


def test_microphone_preserves_silent_and_extensions(client):
    conf = {"entity": "audio", "token": "mic0", "silent": 1, "level": 20, "extra": 7}
    client.run_rpc = Mock(
        side_effect=[ack("ccm_mic_get", conf=[conf]), ack("ccm_mic_set")]
    )
    client.set_microphone_level(30)
    payload = client.run_rpc.call_args.args[1]
    assert payload["dconf_level"] == 30
    assert payload["dconf_silent"] == 1
    assert payload["dconf_extra"] == 7
    assert conf["level"] == 20
    assert payload["dforce_persistence"] == 1


def test_microphone_preserves_entity_object_observed_on_f300(client):
    conf = {
        "entity": {"name": "Microphone", "use_counts": 1, "token": "mic0"},
        "token": "mic0",
        "silent": 0,
        "level": 20,
    }
    client.run_rpc = Mock(
        side_effect=[ack("ccm_mic_get", conf=[conf]), ack("ccm_mic_set")]
    )
    client.set_microphone_level(30)
    payload = client.run_rpc.call_args.args[1]
    assert payload["dconf_entity"] == 1
    assert payload["dconf_entity_name"] == "Microphone"
    assert payload["dconf_entity_use_counts"] == 1
    assert payload["dconf_entity_token"] == "mic0"


@pytest.mark.parametrize("bad", [-1, 101, True, 1.2, "50"])
def test_invalid_level_never_calls_camera(client, bad):
    client.run_rpc = Mock()
    with pytest.raises(ValueError):
        client.set_microphone_level(bad)
    client.run_rpc.assert_not_called()


def test_failed_get_never_writes(client):
    client.run_rpc = Mock(
        return_value={
            "type": "ccm_img_get_ack",
            "data": {"ret": {"code": "permission.denied"}},
        }
    )
    with pytest.raises(MipcError):
        client.set_imaging("brightness", 50)
    assert client.run_rpc.call_count == 1


@pytest.mark.parametrize(
    "reply",
    [
        {},
        {"type": "wrong", "data": {}},
        {"type": "ccm_misc_get_ack", "data": {"info": {}}},
    ],
)
def test_malformed_ack_fails_closed(client, reply):
    client.run_rpc = Mock(return_value=reply)
    with pytest.raises(MipcError):
        client.get_misc()


def test_recording_preserves_schedule(client):
    task = {
        "keep": 12,
        "sch": {"enable": 1, "full_time": 0, "times": [{"start": 100, "end": 200}]},
    }
    client.run_rpc = Mock(
        side_effect=[ack("ccm_record_task_get", task=task), ack("ccm_record_task_set")]
    )
    client.set_recording_enabled(False)
    payload = client.run_rpc.call_args.args[1]
    assert payload["dtask_sch_enable"] == 0
    assert payload["dtask_sch_times_start"] == 100
    assert payload["dtask_keep"] == 12


def test_imaging_preserves_other_values(client):
    client.run_rpc = Mock(
        side_effect=[
            ack("ccm_img_get", conf={"brightness": 20, "mode": "auto", "extension": 2}),
            ack("ccm_img_set"),
        ]
    )
    client.set_imaging("brightness", 70)
    assert client.run_rpc.call_args.args[1]["dconf_mode"] == "auto"
    assert client.run_rpc.call_args.args[1]["dconf_extension"] == 2


def test_jsonp_is_not_evaluated():
    with pytest.raises(MipcProtocolError):
        MipcCameraClient._parse_jsonp("evil({});")
    assert (
        MipcCameraClient._parse_jsonp(' message({type:"ok",data:{}});\n')["type"]
        == "ok"
    )


def test_timeout_redirects_and_safe_logging(client, caplog):
    response = Mock(status_code=200, text='message({type:"ok"});')
    client._r.request = Mock(return_value=response)
    with caplog.at_level("DEBUG"):
        client.run_rpc("test", {"dpass": "never-log-this", "dsess_nid": "secret"})
    assert "never-log-this" not in caplog.text
    assert "secret" not in caplog.text
    assert client._r.request.call_args.kwargs["timeout"] == 10
    assert client._r.request.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize(
    "host", ["evil/path", "name?query", "user:pass@host", "host:99999", "host#frag"]
)
def test_bad_host(host):
    with pytest.raises(ValueError):
        MipcCameraClient(host)
