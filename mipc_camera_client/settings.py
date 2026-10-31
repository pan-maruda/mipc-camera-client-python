"""Typed, conservative access to settings observed in the MIPC web client.

Getters return complete documents so read/modify/write setters preserve firmware
extensions. No device capabilities are inferred from a model name.
"""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from typing import Any, TypedDict

from .profiles import StreamProfile, stream_profiles


class MipcError(Exception):
    """A camera rejected an RPC (response data is intentionally excluded)."""

    def __init__(self, method: str, code: str = "protocol_error") -> None:
        self.method = method
        self.code = code
        super().__init__(f"{method} failed")


class MipcAuthenticationError(MipcError):
    """Login or session authorization failed."""


class MipcProtocolError(MipcError):
    """A response does not match the expected protocol."""


class MipcTransportError(MipcError):
    """Network failure; query strings and credentials are excluded."""


class MipcUnsupportedError(MipcError):
    """The device HTTP interface does not implement the requested operation."""

    def __init__(self, method: str, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(method, f"http_{status_code}")


class DeviceInfo(TypedDict, total=False):
    sn: str
    nick: str
    img_ver: str
    type: str
    p: list[dict[str, str]]
    model: str
    mfc: str
    bimg_ver: str
    wifi: str
    os: str
    sensor: str


class AudioConfig(TypedDict, total=False):
    token: str
    entity: dict[str, Any] | str
    silent: int
    level: int


class ImagingConfig(TypedDict, total=False):
    mode: str
    brightness: int
    contrast: int
    color_saturation: int
    sharpness: int


class DiskStatus(TypedDict, total=False):
    token: str
    stat: str
    size: int
    used_size: int
    available_size: int
    conf: dict[str, Any]


class AlertConfig(TypedDict, total=False):
    io_in_mode: str
    io_out_mode: str
    motion_level: int
    motion_level_night: int


class OsdConfig(TypedDict, total=False):
    text: str
    text_enable: int
    week: int
    date: dict[str, Any]


class MiscConfig(TypedDict, total=False):
    flip: int
    power_freq: int


class SettingsMixin:
    """Requires run_rpc(), nid(), get_device_sn() and a reentrant _lock."""

    def _checked(self, method: str, payload: dict) -> dict:
        response = self.run_rpc(method, payload)
        return self._checked_response(method, response)

    def _checked_response(self, method: str, response: dict) -> dict:
        """Validate a reply, including error envelopes on binary endpoints."""
        expected = method.removesuffix("_req") + "_ack"
        if not isinstance(response, dict) or response.get("type") != expected:
            raise MipcProtocolError(method)
        data = response.get("data")
        if not isinstance(data, dict):
            raise MipcProtocolError(method)
        if isinstance(data.get("ret"), dict):
            code = data["ret"].get("code")
            session_error = data["ret"].get("sub")
        else:
            code = data.get("result")
            session_error = code
        if code != "":
            # Error code spelling varies across firmware. Unknown failures are
            # never treated as success or permission to send a write.
            if session_error in (
                "accounts.nid.invalid",
                "accounts.lid.invalid",
                "accounts.sid.invalid",
                "ccms.session.invalid",
                "InvalidSession",
            ):
                raise MipcAuthenticationError(method, str(code))
            raise MipcError(method, str(code))
        return data

    def _authenticated(
        self,
        method: str,
        _target_serial: str | None = None,
        _queue_id: str | int | None = None,
        **fields: Any,
    ) -> dict:
        with self._lock:
            sn = _target_serial if _target_serial is not None else self.get_device_sn()
            if not isinstance(sn, str) or not sn:
                raise ValueError("Expected a device serial")
            if not self.sid or not sn:
                raise MipcAuthenticationError(method)
            payload = {
                "dsess": 1,
                "dsess_nid": self.nid(),
                "dsess_sn": sn,
                **flatten(fields),
            }
            if _queue_id is not None:
                payload["hqid"] = _queue_id
            return self._checked(method, payload)

    def _document(self, method: str, key: str, **fields: Any) -> dict:
        value = self._authenticated(method, **fields).get(key)
        if not isinstance(value, dict):
            raise MipcProtocolError(method)
        return deepcopy(value)

    def get_device_info(self, select: str | None = None) -> DeviceInfo:
        return self._authenticated("ccm_dev_info_get", select=select)

    def get_microphones(self) -> list[AudioConfig]:
        conf = self._authenticated("ccm_mic_get").get("conf")
        if not isinstance(conf, list) or not all(isinstance(v, dict) for v in conf):
            raise MipcProtocolError("ccm_mic_get")
        return deepcopy(conf)

    def get_speaker(self, token: str = "ao0") -> AudioConfig:
        return self._document("ccm_speaker_get", "conf", token=token)

    def get_imaging(self, token: str = "vs0") -> ImagingConfig:
        return self._document("ccm_img_get", "conf", token=token)

    def get_misc(self) -> MiscConfig:
        return self._document("ccm_misc_get", "info")

    def get_osd(self) -> OsdConfig:
        return self._document("ccm_osd_get", "osd")

    def get_alert_config(self) -> AlertConfig:
        return self._document("ccm_alert_dev_get", "conf")

    def get_alert_actions(self) -> dict[str, Any]:
        return self._authenticated("ccm_alert_action_get")

    def get_motion_mask(self) -> dict[str, Any]:
        return self._document("ccm_motion_mask_get", "conf")

    def get_recording(self) -> dict[str, Any]:
        return self._authenticated("ccm_record_task_get")

    def get_disks(self) -> list[DiskStatus]:
        data = self._authenticated("ccm_disk_get")
        disks = data.get("disks")
        if disks is None and "stat" in data:
            disks = [{k: v for k, v in data.items() if k not in ("ret", "result")}]
        if not isinstance(disks, list) or not all(isinstance(v, dict) for v in disks):
            raise MipcProtocolError("ccm_disk_get")
        return deepcopy(disks)

    def get_video_sources(self) -> list[dict[str, Any]]:
        sources = self._authenticated("ccm_video_srcs_get").get("vss")
        if not isinstance(sources, list) or not all(
            isinstance(v, dict) for v in sources
        ):
            raise MipcProtocolError("ccm_video_srcs_get")
        return deepcopy(sources)

    def get_stream_profiles(self) -> list[StreamProfile]:
        """Discover playback quality tokens; no encoder settings are changed."""
        return stream_profiles(self.get_device_info())

    def probe_stream_profiles(
        self, decoder: Callable[[str], tuple[int, int]]
    ) -> list[StreamProfile]:
        """Measure advertised streams using a caller-supplied bounded decoder.

        The decoder receives a private local media URL and returns frame width,
        height. No media dependency is required by the SDK. Failed/invalid probes
        retain the advertised profile with unknown dimensions; names are never
        converted into assumed resolutions. This opens streams, not encoder writes.
        """
        profiles = []
        for profile in self.get_stream_profiles():
            try:
                dimensions = decoder(self.get_stream_url(profile.token))
                if not isinstance(dimensions, (tuple, list)) or len(dimensions) != 2:
                    raise ValueError("Invalid frame dimensions")
                width, height = dimensions
                if any(
                    type(n) is not int or not 1 <= n <= 16384 for n in (width, height)
                ):
                    raise ValueError("Invalid frame dimensions")
                profile = replace(profile, width=width, height=height)
            except MipcAuthenticationError:
                raise
            except (MipcError, OSError, ValueError, StopIteration):
                pass
            profiles.append(profile)
        return profiles

    def get_network(
        self,
        *,
        tokens: list[str] | None = None,
        items: list[str] | None = None,
        scan: bool = False,
    ) -> dict[str, Any]:
        """Read configuration; wireless scanning is opt-in via scan=True."""
        if type(scan) is not bool:
            raise ValueError("scan must be a boolean")
        tokens = ["eth0", "ra0"] if tokens is None else tokens
        items = ["all"] * len(tokens) if items is None else items
        if (
            not isinstance(tokens, list)
            or not isinstance(items, list)
            or len(tokens) != len(items)
            or not tokens
            or not all(isinstance(v, str) and v for v in tokens + items)
        ):
            raise ValueError("Expected matching token and item lists")
        return self._document(
            "ccm_net_get", "info", tokens=tokens, items=items, force_scan=scan
        )

    def get_ntp(self) -> dict[str, Any]:
        return self._document("ccm_ntp_get", "info")

    def get_date(self) -> dict[str, Any]:
        return self._document("ccm_date_get", "utc_date")

    @staticmethod
    def _range(value: int, low: int, high: int) -> int:
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"Expected an integer in {low}..{high}")
        return value

    def set_microphone_level(self, level: int, token: str | None = None) -> None:
        self._range(level, 0, 100)
        with self._lock:
            configs = self.get_microphones()
            matches = [c for c in configs if token is None or c.get("token") == token]
            if not matches or (token is None and len(matches) != 1):
                raise ValueError("Choose a microphone token returned by the camera")
            conf = matches[0]
            if not all(k in conf for k in ("entity", "token", "silent", "level")):
                raise MipcProtocolError("ccm_mic_get")
            conf["level"] = level
            self._authenticated("ccm_mic_set", conf=conf, force_persistence=1)

    def set_speaker_level(self, level: int, token: str = "ao0") -> None:
        self._range(level, 0, 100)
        with self._lock:
            conf = self.get_speaker(token)
            if conf.get("token", token) != token or "level" not in conf:
                raise MipcProtocolError("ccm_speaker_get")
            conf["token"] = token
            conf["level"] = level
            self._authenticated("ccm_speaker_set", conf=conf, force_persistence=1)

    def set_imaging(self, field: str, value: int | str, token: str = "vs0") -> None:
        if field not in (
            "brightness",
            "contrast",
            "color_saturation",
            "sharpness",
            "mode",
        ):
            raise ValueError("Unsupported imaging field")
        if field == "mode":
            if value not in ("auto", "day", "night"):
                raise ValueError("Unsupported day/night mode")
        else:
            self._range(value, 0, 100)
        with self._lock:
            conf = self.get_imaging(token)
            if field not in conf:
                raise MipcProtocolError("ccm_img_get")
            conf[field] = value
            self._authenticated("ccm_img_set", token=token, conf=conf)

    def set_flip(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise ValueError("Expected a boolean")
        with self._lock:
            info = self.get_misc()
            if info.get("flip") not in (0, 1):
                raise MipcProtocolError("ccm_misc_get")
            info["flip"] = int(enabled)
            self._authenticated("ccm_misc_set", info=info)

    def set_osd_enabled(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise ValueError("Expected a boolean")
        with self._lock:
            osd = self.get_osd()
            if osd.get("text_enable") not in (0, 1):
                raise MipcProtocolError("ccm_osd_get")
            osd["text_enable"] = int(enabled)
            self._authenticated("ccm_osd_set", osd=osd)

    def set_recording_enabled(self, enabled: bool) -> None:
        """Enable the existing SD task; does not select continuous recording.

        Preserves its existing full_time/schedule mode. Prefer set_recording_mode
        when you want an explicit off/continuous/scheduled choice.
        """
        if type(enabled) is not bool:
            raise ValueError("Expected a boolean")
        with self._lock:
            data = self.get_recording()
            task = deepcopy(data.get("task"))
            if (
                not isinstance(task, dict)
                or not isinstance(task.get("sch"), dict)
                or task["sch"].get("enable") not in (0, 1)
            ):
                raise MipcProtocolError("ccm_record_task_get")
            task["sch"]["enable"] = int(enabled)
            self._authenticated("ccm_record_task_set", task=task)


def flatten(fields: dict, prefix: str = "") -> dict:
    """MIPC HTTP object encoding; array count and object markers are required."""
    result = {}
    for key, value in fields.items():
        name = prefix + (("_" if prefix else "d") + str(key) if str(key) != "0" else "")
        if isinstance(value, dict):
            result[name] = 1
            result.update(flatten(value, name))
        elif isinstance(value, list):
            result[name + "__x_countz_"] = len(value)
            for index, item in enumerate(value):
                # Index zero has no suffix; subsequent items use _1, _2, ...
                result.update(flatten({str(index): item}, name))
        elif value is not None:
            result[name] = int(value) if isinstance(value, bool) else value
    return result
