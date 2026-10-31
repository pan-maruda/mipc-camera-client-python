from copy import deepcopy
from threading import RLock
from unittest.mock import Mock

import pytest

from mipc_camera_client import MipcCameraClient, MipcProtocolError
from mipc_camera_client.device_settings import network_interfaces, recording_mode


@pytest.fixture
def client():
    c = MipcCameraClient("192.0.2.10")
    c._lock = RLock()
    c.call = Mock()
    yield c
    c.close()


def test_network_view_drops_credentials_and_handles_malformed_fields():
    raw = {
        "ifs": [
            {
                "token": "ra0",
                "enabled": 1,
                "phy": {"info": {"mac": "AA-BB-CC-DD-EE-FF", "stat": "ok"}},
                "ipv4": {"info": {"ip": {"addr": "192.0.2.10"}}},
                "wifi_client": {
                    "conf": {"key": "secret", "ssid": "private"},
                    "ap_list": ["private"],
                },
            },
            {"token": "eth0", "phy": None, "ipv4": []},
            None,
            {"token": 2},
        ]
    }
    before = deepcopy(raw)
    interfaces = network_interfaces(raw)
    assert interfaces[0].connection == "wifi"
    assert interfaces[0].mac_address == "aa:bb:cc:dd:ee:ff"
    assert interfaces[0].ip_address == "192.0.2.10"
    assert "secret" not in repr(interfaces) and "private" not in repr(interfaces)
    assert interfaces[1].connection == "ethernet"
    assert interfaces[1].ip_address is None
    assert raw == before
    assert network_interfaces({"ifs": None}) == ()
    assert (
        network_interfaces(
            {
                "ifs": [
                    {
                        "token": "other",
                        "enabled": "1",
                        "phy": {"info": {"mac": "bogus"}},
                        "ipv4": {"info": {"ip": {"addr": "999.1.2.3"}}},
                    }
                ]
            }
        )[0].mac_address
        is None
    )


@pytest.mark.parametrize(
    "mode,patch",
    [
        ("off", {"enable": 0}),
        ("continuous", {"enable": 1, "full_time": 1}),
        ("scheduled", {"enable": 1, "full_time": 0}),
    ],
)
def test_recording_modes_preserve_unknown_fields_and_schedule(client, mode, patch):
    original = {
        "token": "p0",
        "keep": 0,
        "future": 9,
        "sch": {"enable": 0, "full_time": 0, "times": [{"future": 1}]},
    }
    client._document = Mock(return_value=original)
    client.set_recording_mode(mode)
    written = client.call.call_args.kwargs["task"]
    assert written["sch"] == original["sch"] | patch
    assert written["keep"] == 0 and written["future"] == 9
    assert original["sch"]["enable"] == 0
    assert recording_mode({"task": written}) == mode


def test_empty_schedule_and_unknown_recording_mode_never_write(client):
    client._document = Mock(return_value={"sch": {"enable": 0, "full_time": 0}})
    for mode in ("scheduled", "bad"):
        with pytest.raises(ValueError):
            client.set_recording_mode(mode)
    client._document.return_value = {"sch": {"enable": 0}}
    with pytest.raises(MipcProtocolError):
        client.set_recording_mode("continuous")
    client.call.assert_not_called()
    for doc in (
        {},
        {"task": {"sch": {"enable": "1"}}},
        {"task": {"sch": {"enable": 1}}},
    ):
        assert recording_mode(doc) is None


def test_motion_action_never_arms_or_changes_other_actions(client):
    motion = {"token": "motion_alert", "enable": 1, "record_enable": 0, "future": 2}
    other = {"token": "io_alert", "enable": 1, "io_out_enable": 1}
    client.get_alert_actions = Mock(
        return_value={"enable": 0, "actions": [motion, other]}
    )
    client.set_motion_alarm_enabled(False)
    client.call.assert_called_once_with(
        "ccm_alert_action_set", actions=motion | {"enable": 0}
    )
    assert motion["enable"] == 1 and other["enable"] == 1


@pytest.mark.parametrize(
    "data",
    [{}, {"actions": []}, {"actions": [{"token": "motion_alert", "enable": 1}] * 2}],
)
def test_motion_unknown_shape_never_writes(client, data):
    client.get_alert_actions = Mock(return_value=data)
    with pytest.raises(MipcProtocolError):
        client.set_motion_alarm_enabled(True)
    client.call.assert_not_called()


def test_motion_boolean_and_frequency_validation(client):
    with pytest.raises(ValueError):
        client.set_motion_alarm_enabled(1)
    client.update_misc = Mock()
    client.set_power_frequency(60)
    client.update_misc.assert_called_with(power_freq=0)
    client.set_power_frequency(50)
    client.update_misc.assert_called_with(power_freq=1)
    for value in (True, "50", 49):
        with pytest.raises(ValueError):
            client.set_power_frequency(value)


def test_timezone_discovery_rejects_bad_shape(client):
    client.get_device_sn = Mock(return_value="synthetic")
    client.get_zone = Mock(
        return_value={
            "address": {
                "zones": [
                    {"utc": "UTC+00:00"},
                    {},
                    {"utc": "UTC+00:00"},
                    {"utc": "UTC+08:00"},
                ]
            }
        }
    )
    assert client.get_timezones() == ("UTC+00:00", "UTC+08:00")
    client.get_zone.return_value = {}
    with pytest.raises(MipcProtocolError):
        client.get_timezones()


def test_explicit_arming_and_restore(client):
    client.set_alarm_armed(True)
    client.call.assert_called_once_with("ccm_alert_action_set", enable=True)
    client.call.reset_mock()
    client.restore(keep_configuration=False)
    client.call.assert_called_once_with("ccm_restore", backup=False)
