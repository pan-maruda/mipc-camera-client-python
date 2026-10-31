from unittest.mock import Mock, call

import pytest

from mipc_camera_client import (
    MipcAuthenticationError,
    MipcCameraClient,
    MipcError,
    MipcProtocolError,
)
from mipc_camera_client.catalog import ENDPOINTS
from mipc_camera_client.settings import flatten


@pytest.fixture
def client():
    c = MipcCameraClient("192.0.2.10:7080")
    c.sid = "synthetic-session"
    c._sn = "synthetic-camera"
    c.shared_secret = "12345"
    yield c
    c.close()


def ack(method, **data):
    return {
        "type": method.removesuffix("_req") + "_ack",
        "data": {"ret": {"code": ""}, "result": "", **data},
    }


@pytest.mark.parametrize("value", [0, 1, False, True])
def test_android_external_switch_flag_is_typed(client, value):
    client.run_rpc = Mock(return_value=ack("ccm_exsw_get", enable=value))
    assert client.get_external_switch_enabled() is bool(value)


@pytest.mark.parametrize("value", [None, "1", 2, []])
def test_android_external_switch_rejects_unknown_values(client, value):
    client.run_rpc = Mock(return_value=ack("ccm_exsw_get", enable=value))
    with pytest.raises(MipcProtocolError):
        client.get_external_switch_enabled()


def test_android_read_helpers_and_literal_talk_field(client):
    client.run_rpc = Mock(
        side_effect=[
            ack("ccm_sleep_get", sleep_enable=1),
            ack("ccm_crop_zoom_get", crop_zoom_conf={"x": 1}),
            ack("ccm_talk", uri={"url": "rtmp://192.0.2.10/talk"}),
        ]
    )
    assert client.get_sleep_config()["sleep_enable"] == 1
    assert client.get_crop_zoom()["crop_zoom_conf"] == {"x": 1}
    client.call("ccm_talk", setup={"trans": {"proto": "rtmp"}}, slient=1)
    assert client.run_rpc.call_args.args[1]["dslient"] == 1


def test_alert_actions_updates_each_token_as_object_before_arming(client):
    actions = [{"token": "motion", "enable": 1}, {"token": "input", "enable": 0}]
    client.call = Mock()
    client.set_alert_actions(enabled=True, actions=actions)
    assert client.call.call_args_list == [
        call("ccm_alert_action_set", actions=actions[0]),
        call("ccm_alert_action_set", actions=actions[1]),
        call("ccm_alert_action_set", enable=True),
    ]


def test_alert_actions_empty_list_only_changes_arming(client):
    client.call = Mock()
    client.set_alert_actions(enabled=False, actions=[])
    client.call.assert_called_once_with("ccm_alert_action_set", enable=False)


@pytest.mark.parametrize(
    "actions", [[{}], [{"token": ""}], [{"token": 7}], [{"token": "valid"}, {}]]
)
def test_alert_actions_validates_all_tokens_before_any_write(client, actions):
    client.call = Mock()
    with pytest.raises(ValueError):
        client.set_alert_actions(enabled=True, actions=actions)
    client.call.assert_not_called()


def test_alert_actions_stops_on_partial_failure_without_replay_or_arming(client):
    actions = [{"token": "first"}, {"token": "second"}, {"token": "third"}]
    client.call = Mock(side_effect=[{}, MipcError("ccm_alert_action_set")])
    with pytest.raises(MipcError):
        client.set_alert_actions(enabled=True, actions=actions)
    assert client.call.call_count == 2
    assert client.call.call_args.kwargs == {"actions": actions[1]}


@pytest.mark.parametrize(
    "method", [n for n, e in ENDPOINTS.items() if e["scope"] == "device"]
)
def test_catalog_dispatches_to_configured_device_rpc(client, method):
    client.run_rpc = Mock(return_value=ack(method))
    client.call(method)
    name, payload = client.run_rpc.call_args.args
    assert name == method
    if method.startswith("mmq_"):
        assert "dsess" not in payload
    else:
        assert payload["dsess_sn"] == "synthetic-camera"
        assert payload["dsess_nid"]


@pytest.mark.parametrize(
    "method",
    [n for n, e in ENDPOINTS.items() if e["scope"] != "device"]
    + ["unknown", "../ccm_reboot", "https://vendor.invalid"],
)
def test_call_excludes_cloud_and_unknown_methods(client, method):
    client.run_rpc = Mock()
    with pytest.raises(ValueError):
        client.call(method)
    client.run_rpc.assert_not_called()


def test_cannot_override_session(client):
    client.run_rpc = Mock()
    with pytest.raises(ValueError):
        client.call("ccm_misc_get", sess={"sn": "other"})
    client.run_rpc.assert_not_called()


def test_box_target_stays_explicit(client):
    client.run_rpc = Mock(return_value=ack("ccm_box_get"))
    client.get_box_recordings("box", "ipc", start_time=100, end_time=200)
    data = client.run_rpc.call_args.args[1]
    assert data["dsess_sn"] == "box"
    assert data["dsn"] == "ipc"
    assert data["dstart_time"] == 100


def test_nested_document_update_keeps_extensions(client):
    original = {
        "text": "Camera",
        "date": {"date_enable": 1, "time_enable": 1, "extension": 99},
    }
    client.run_rpc = Mock(
        side_effect=[ack("ccm_osd_get", osd=original), ack("ccm_osd_set")]
    )
    client.update_osd(date={"date_enable": 0})
    data = client.run_rpc.call_args.args[1]
    assert data["dosd_date_date_enable"] == 0
    assert data["dosd_date_time_enable"] == 1
    assert data["dosd_date_extension"] == 99
    assert original["date"]["date_enable"] == 1


def test_unknown_document_field_never_written(client):
    client.run_rpc = Mock(return_value=ack("ccm_misc_get", info={"flip": 0}))
    with pytest.raises(ValueError):
        client.update_misc(guessed_setting=1)
    assert client.run_rpc.call_count == 1


def test_wrong_document_type_never_written(client):
    client.run_rpc = Mock(return_value=ack("ccm_misc_get", info={"flip": 0}))
    with pytest.raises(ValueError):
        client.update_misc(flip="enabled")
    assert client.run_rpc.call_count == 1


def test_network_does_not_scan_by_default(client):
    client.run_rpc = Mock(return_value=ack("ccm_net_get", info={"ifs": []}))
    client.get_network()
    data = client.run_rpc.call_args.args[1]
    assert data["dforce_scan"] == 0
    assert data["dtokens__x_countz_"] == 2
    assert data["dtokens"] == "eth0"
    assert data["dtokens_1"] == "ra0"


@pytest.mark.parametrize(
    "sub",
    [
        "accounts.sid.invalid",
        "accounts.nid.invalid",
        "accounts.lid.invalid",
        "ccms.session.invalid",
        "InvalidSession",
    ],
)
def test_observed_expired_session_codes(client, sub):
    client.run_rpc = Mock(
        return_value={
            "type": "ccm_misc_get_ack",
            "data": {"ret": {"code": "failed", "sub": sub}},
        }
    )
    with pytest.raises(MipcAuthenticationError):
        client.get_misc()
    assert client.run_rpc.call_count == 1  # No hidden retries or writes.


def test_live_f300_invalid_session_response_never_replays_writes(client):
    client.run_rpc = Mock(
        return_value={
            "type": "ccm_misc_set_ack",
            "data": {"ret": {"code": "Receiver", "sub": "InvalidSession"}},
        }
    )
    with pytest.raises(MipcAuthenticationError) as error:
        client.call("ccm_misc_set", info={"flip": 1})
    assert error.value.code == "Receiver"
    client.run_rpc.assert_called_once()


def test_other_receiver_errors_remain_device_errors(client):
    client.run_rpc = Mock(
        return_value={
            "type": "ccm_misc_get_ack",
            "data": {"ret": {"code": "Receiver", "sub": "ccm.system.err"}},
        }
    )
    with pytest.raises(MipcError) as error:
        client.get_misc()
    assert not isinstance(error.value, MipcAuthenticationError)


def test_snapshot_xml_invalid_session_is_auth_failure(client):
    client.run_rpc = Mock(
        return_value=(
            b"<message><type>ccm_pic_get_ack</type><data><ccm_pic_get_ack>"
            b"<ret><code>Receiver</code><sub>InvalidSession</sub></ret>"
            b"</ccm_pic_get_ack></data></message>"
        )
    )
    with pytest.raises(MipcAuthenticationError):
        client.get_image()
    client.run_rpc.assert_called_once()


@pytest.mark.parametrize(
    "body",
    [
        b"not an image",
        b"<message>",
        b"<message><type>wrong_ack</type><data><ccm_pic_get_ack><ret><code>Receiver</code><sub>InvalidSession</sub></ret></ccm_pic_get_ack></data></message>",
        b"<message><type>ccm_pic_get_ack</type><data><ccm_pic_get_ack><ret><code></code></ret></ccm_pic_get_ack></data></message>",
        b'<!DOCTYPE message [<!ENTITY x "InvalidSession">]><message>&x;</message>',
        b" " * 65537,
        '<!DOCTYPE message [<!ENTITY x "InvalidSession">]><message>&x;</message>'.encode(
            "utf-16"
        ),
        b'<message encoding="unrecognized-charset"></message>',
    ],
)
def test_non_jpeg_snapshot_does_not_become_success_or_auth_retry(client, body):
    client.run_rpc = Mock(return_value=body)
    with pytest.raises(MipcProtocolError):
        client.get_image()


@pytest.mark.parametrize(
    "url",
    [
        "rtmp://vendor.invalid/live",
        "rtsp://192.0.2.10/live",
        "rtmp://192.0.2.10:bad/live",
        "file:///etc/passwd",
        "rtmp://192.0.2.10:/live",
    ],
)
def test_stream_validation(client, url):
    client.run_rpc = Mock(return_value=ack("ccm_play", uri={"url": url}))
    with pytest.raises(MipcProtocolError):
        client.get_stream_url()


def test_local_and_explicit_remote_streams(client):
    client.run_rpc = Mock(
        return_value=ack("ccm_play", uri={"url": "rtmp://192.0.2.10:1935/live"})
    )
    assert client.get_rtmp_stream() == "rtmp://192.0.2.10:1935/live"
    client.run_rpc = Mock(
        return_value=ack("ccm_play", uri={"url": "rtmp://vendor.invalid/live"})
    )
    assert client.get_stream_url(allow_remote=True) == "rtmp://vendor.invalid/live"


def test_probes_never_call_writes_or_scan(client):
    def rpc(method, data):
        assert method.endswith("_get")
        assert data.get("dforce_scan", 0) == 0
        if method == "ccm_misc_get":
            return ack(method, info={"flip": 0})
        return {"type": method + "_ack", "data": {"ret": {"code": "not_supported"}}}

    client.run_rpc = Mock(side_effect=rpc)
    report = client.probe_capabilities(["misc", "imaging"])
    assert report.readable == frozenset({"misc"})
    assert report.rejected == {"imaging": "MipcError"}
    assert client.run_rpc.call_count == 2


def test_secret_password_fields_are_encrypted(client):
    client.run_rpc = Mock(return_value=ack("ccm_pwd_set"))
    client.change_device_password("admin", "old-secret", "new-secret")
    payload = client.run_rpc.call_args.args[1]
    assert payload["duser__x_countz_"] == 1
    assert payload["duser_username"] == "admin"
    assert "old-secret" not in str(payload)
    assert "new-secret" not in str(payload)


def test_logout_clears_sid_even_if_rejected(client):
    client.run_rpc = Mock(side_effect=MipcError("cacs_logout_req"))
    with pytest.raises(MipcError):
        client.logout()
    assert client.sid == ""


def test_local_password_change_encrypts_fields_and_requires_relogin(client):
    client.run_rpc = Mock(return_value=ack("cacs_passwd_req"))
    client.change_password("old-secret", "new-secret")
    method, payload = client.run_rpc.call_args.args
    assert method == "cacs_passwd_req"
    assert payload["dguest"] == 0
    assert "old-secret" not in str(payload)
    assert "new-secret" not in str(payload)
    assert client.sid == ""


def test_speaker_level_adds_explicit_token_if_response_omits_it(client):
    client.run_rpc = Mock(
        side_effect=[ack("ccm_speaker_get", conf={"level": 20}), ack("ccm_speaker_set")]
    )
    client.set_speaker_level(30)
    payload = client.run_rpc.call_args.args[1]
    assert payload["dconf_token"] == "ao0"
    assert payload["dconf_level"] == 30


def test_flatten_skips_none_and_keeps_zero_false_empty():
    assert flatten({"start": 0, "flag": False, "text": "", "missing": None}) == {
        "dstart": 0,
        "dflag": 0,
        "dtext": "",
    }
