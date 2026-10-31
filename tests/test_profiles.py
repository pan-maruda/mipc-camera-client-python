from unittest.mock import Mock

import pytest

from mipc_camera_client import MipcCameraClient
from mipc_camera_client.profiles import StreamProfile, stream_profiles


def test_discovery_uses_device_advertisements_without_guessed_profiles():
    info = {
        "p": [
            {"n": "p2", "v": "CIF"},
            {"n": "p0", "v": "HD1080p"},
            {"n": "p1", "v": "D1"},
            {"n": "model", "v": "f300"},
        ]
    }
    assert stream_profiles(info) == [
        StreamProfile("p0", "HD1080p"),
        StreamProfile("p1", "D1"),
        StreamProfile("p2", "CIF"),
    ]
    c = MipcCameraClient("192.0.2.10")
    c.get_device_info = Mock(return_value=info)
    c.call = Mock()
    try:
        assert c.get_stream_profiles() == stream_profiles(info)
        c.get_device_info.assert_called_once_with()
        c.call.assert_not_called()
    finally:
        c.close()


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        {"p": None},
        {
            "p": [
                None,
                {"n": []},
                {"n": "p0", "v": None},
                {"n": "p1", "v": ""},
                {"n": "p2", "v": "x" * 65},
                {"n": "p4", "v": "unknown"},
            ]
        },
    ],
)
def test_malformed_or_missing_advertisements_do_not_invent_choices(value):
    assert stream_profiles(value) == []


def test_conflicting_duplicates_are_not_advertised():
    assert stream_profiles(
        {
            "p": [
                {"n": "p0", "v": "HD"},
                {"n": "p0", "v": "SD"},
                {"n": "p1", "v": " D1 "},
                {"n": "p1", "v": "D1"},
            ]
        }
    ) == [StreamProfile("p1", "D1")]


def test_probe_measures_each_advertised_token_without_assuming_dimensions():
    c = MipcCameraClient("192.0.2.10")
    c.get_stream_profiles = Mock(
        return_value=[
            StreamProfile("p0", "HD1080p"),
            StreamProfile("p1", "D1"),
            StreamProfile("p2", "CIF"),
        ]
    )
    c.get_stream_url = Mock(side_effect=lambda token: "rtmp://192.0.2.10/" + token)
    decode = Mock(side_effect=[(1920, 1080), (640, 360), (640, 360)])
    try:
        profiles = c.probe_stream_profiles(decode)
        assert [(p.width, p.height) for p in profiles] == [
            (1920, 1080),
            (640, 360),
            (640, 360),
        ]
        assert [call.args[0] for call in c.get_stream_url.call_args_list] == [
            "p0",
            "p1",
            "p2",
        ]
    finally:
        c.close()


@pytest.mark.parametrize(
    "result", [(True, 360), (0, 360), (640, 999999), None, OSError("synthetic")]
)
def test_failed_probe_leaves_dimensions_unknown(result):
    c = MipcCameraClient("192.0.2.10")
    c.get_stream_profiles = Mock(return_value=[StreamProfile("p1", "D1")])
    c.get_stream_url = Mock(return_value="rtmp://192.0.2.10/p1")
    decode = (
        Mock(side_effect=result)
        if isinstance(result, Exception)
        else Mock(return_value=result)
    )
    try:
        assert c.probe_stream_profiles(decode) == [StreamProfile("p1", "D1")]
    finally:
        c.close()


def test_probe_auth_failure_is_not_hidden_as_an_unknown_resolution():
    from mipc_camera_client import MipcAuthenticationError

    c = MipcCameraClient("192.0.2.10")
    c.get_stream_profiles = Mock(return_value=[StreamProfile("p0", "HD1080p")])
    c.get_stream_url = Mock(side_effect=MipcAuthenticationError("ccm_play"))
    try:
        with pytest.raises(MipcAuthenticationError):
            c.probe_stream_profiles(Mock())
    finally:
        c.close()
