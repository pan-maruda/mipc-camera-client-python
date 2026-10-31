"""Local device operations observed in the Windows client's protocol calls.

These functions negotiate media URLs; they do not embed a player, codecs, or
the vendor's native two-way-audio plugin. Full camera documents remain dicts
because firmware-specific extension fields must survive read/modify/write.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from threading import Event
from typing import Any
from urllib.parse import urlsplit

from .audio import AudioSendResult
from .device_settings import NetworkInterface, network_interfaces, recording_mode
from .settings import MipcProtocolError


def merge_document(base: dict, changes: Mapping[str, Any]) -> dict:
    result = deepcopy(base)
    for key, value in changes.items():
        if not isinstance(key, str):
            raise ValueError("Document keys must be strings")
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = merge_document(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


class OperationsMixin:
    """Explicit operations. Nothing is polled or changed automatically."""

    def probe_capabilities(self, names: list[str] | None = None):
        """Explicitly test selected read operations; rejection is not proof of absence."""
        from .capabilities import READ_PROBES, CapabilityReport
        from .settings import MipcAuthenticationError, MipcError, MipcTransportError

        selected = list(READ_PROBES) if names is None else names
        if not isinstance(selected, list) or any(
            name not in READ_PROBES for name in selected
        ):
            raise ValueError("Unknown capability probe")
        readable, rejected = set(), {}
        for name in dict.fromkeys(selected):
            try:
                getattr(self, READ_PROBES[name])()
            except (MipcAuthenticationError, MipcTransportError):
                raise
            except MipcError as err:
                rejected[name] = type(err).__name__
            else:
                readable.add(name)
        return CapabilityReport(frozenset(readable), rejected)

    def activate(self, activation_code: str) -> dict[str, Any]:
        """Send activation to this host only; offline support depends on firmware."""
        return self.call("ccm_active", ActivationCode=activation_code)

    def add_device(self, serial: str, password: str) -> dict[str, Any]:
        """Add a device to the configured gateway, without cloud lookup."""
        from .crypto_helpers import des_encrypt_password_hash, hash_password

        if not self.shared_secret:
            raise ValueError("Login is required")
        encrypted = des_encrypt_password_hash(
            hash_password(password), self.shared_secret
        )
        return self.call("ccm_dev_add", sn=serial, pwd=encrypted)

    def remove_device(self, serial: str) -> None:
        self.call("ccm_dev_del", sn=serial)

    def change_device_password(
        self, username: str, old_password: str, new_password: str
    ) -> None:
        """Update an explicitly named device user; does not change a cloud account."""
        from .crypto_helpers import des_encrypt_password_hash, hash_password

        if not self.shared_secret:
            raise ValueError("Login is required")

        def encrypt(password):
            return des_encrypt_password_hash(
                hash_password(password), self.shared_secret
            )

        self.call(
            "ccm_pwd_set",
            user=[
                {
                    "username": username,
                    "old_pwd": encrypt(old_password),
                    "pwd": encrypt(new_password),
                    "level": "",
                }
            ],
        )

    def check_session(self) -> dict[str, Any]:
        with self._lock:
            return self._checked("cacs_check_nid_req", {"dnid": self.nid()})

    def change_password(
        self, old_password: str, new_password: str, *, guest: bool = False
    ) -> None:
        """Change the current local account password and require explicit login again."""
        from .crypto_helpers import des_encrypt_password_hash, hash_password
        from .settings import MipcAuthenticationError, flatten

        if type(guest) is not bool:
            raise ValueError("Expected boolean guest")
        with self._lock:
            if not self.sid or not self.shared_secret:
                raise MipcAuthenticationError("cacs_passwd_req")
            self._checked(
                "cacs_passwd_req",
                flatten(
                    {
                        "nid": self.nid(),
                        "old_pass": des_encrypt_password_hash(
                            hash_password(old_password), self.shared_secret
                        ),
                        "new_pass": des_encrypt_password_hash(
                            hash_password(new_password), self.shared_secret
                        ),
                        "guest": guest,
                    }
                ),
            )
            self.sid = ""

    def logout(self) -> None:
        with self._lock:
            try:
                if self.sid:
                    self._checked("cacs_logout_req", {"dnid": self.nid()})
            finally:
                self.sid = ""

    def call(
        self, method: str, *, target_serial: str | None = None, **fields: Any
    ) -> dict:
        """Call an observed local device RPC using unflattened Python values.

        The catalog describes request shapes, not hardware support. Unknown
        endpoints and cloud account APIs are excluded. run_rpc remains the
        backwards-compatible low-level escape hatch at the configured host.
        """
        from .catalog import ENDPOINTS

        if method not in ENDPOINTS or ENDPOINTS[method]["scope"] != "device":
            raise ValueError("Not an observed local device endpoint")
        allowed = set(ENDPOINTS[method]["fields"]) - {"sess"}
        if fields.keys() - allowed:
            raise ValueError(
                "Unrecognized request fields; consult the endpoint catalog"
            )
        if method.startswith("mmq_"):
            from .events import queue_message
            from .settings import flatten

            if target_serial is not None:
                raise ValueError("Message queues do not take a target serial")
            if method == "mmq_pick":
                return queue_message(self.run_rpc(method, flatten(fields)))
            return self._checked(method, flatten(fields))
        return self._authenticated(method, _target_serial=target_serial, **fields)

    def event_queue(self, *, lifetime: int = 30):
        """Create a local queue and subscribe, without starting a listener thread."""
        from .events import EventQueue

        return EventQueue(self, lifetime)

    def get_info(self) -> dict[str, Any]:
        return self._checked("ccm_info_get", {})

    def get_devices(self, start: int = 0, count: int = 128) -> dict[str, Any]:
        """List devices known to this configured gateway; never discovers a cloud server."""
        self._range(start, 0, 2**31 - 1)
        self._range(count, 1, 128)
        return self.call("ccm_devs_get", start=start, counts=count)

    def get_ip_cameras(self) -> dict[str, Any]:
        return self.call("ccm_ipcs_get")

    def get_microphone_inputs(self) -> dict[str, Any]:
        return self.call("ccm_mics_get")

    def get_speaker_outputs(self) -> dict[str, Any]:
        return self.call("ccm_speakers_get")

    def update_microphone(self, token: str, **changes: Any) -> None:
        if not changes or changes.keys() - {"level", "silent"}:
            raise ValueError("Supported microphone fields: level, silent")
        if "level" in changes:
            self._range(changes["level"], 0, 100)
        if "silent" in changes and type(changes["silent"]) is not bool:
            raise ValueError("silent must be a boolean")
        with self._lock:
            matches = [c for c in self.get_microphones() if c.get("token") == token]
            if len(matches) != 1 or not all(
                k in matches[0] for k in ("entity", "token", "silent", "level")
            ):
                raise MipcProtocolError("ccm_mic_get")
            conf = merge_document(matches[0], changes)
            self.call("ccm_mic_set", conf=conf, force_persistence=1)

    def update_imaging(self, *, token: str = "vs0", **changes: Any) -> None:
        allowed = {"brightness", "contrast", "color_saturation", "sharpness", "mode"}
        if not changes or changes.keys() - allowed:
            raise ValueError("Unsupported imaging field")
        for key, value in changes.items():
            if key == "mode":
                if value not in ("auto", "day", "night"):
                    raise ValueError("Invalid image mode")
            else:
                self._range(value, 0, 100)
        with self._lock:
            conf = self.get_imaging(token)
            if changes.keys() - conf.keys():
                raise MipcProtocolError("ccm_img_get")
            self.call("ccm_img_set", token=token, conf=merge_document(conf, changes))

    def get_network_interfaces(self) -> tuple[NetworkInterface, ...]:
        """Read interface identity/link/IP without exposing Wi-Fi credentials."""
        return network_interfaces(self.get_network())

    def set_power_frequency(self, hertz: int) -> None:
        """MIPC client mapping: enum 0 = 60 Hz, 1 = 50 Hz.

        Some OEM client UIs reverse their labels. This helper follows the MIPC
        UI, not the Vimtag OEM UI. Raw update_misc remains available.
        """
        if type(hertz) is not int or hertz not in (50, 60):
            raise ValueError("Expected 50 or 60 hertz")
        self.update_misc(power_freq=0 if hertz == 60 else 1)

    def get_timezones(self) -> tuple[str, ...]:
        """Return the UTC offset strings used by the extracted Windows UI."""
        data = self.get_zone(self.get_device_sn())
        address = data.get("address")
        zones = address.get("zones") if isinstance(address, dict) else None
        if not isinstance(zones, list):
            raise MipcProtocolError("ccm_zone_get")
        return tuple(
            dict.fromkeys(
                z["utc"]
                for z in zones
                if isinstance(z, dict) and isinstance(z.get("utc"), str) and z["utc"]
            )
        )

    def get_recording_mode(self) -> str | None:
        return recording_mode(self.get_recording())

    def set_recording_mode(self, mode: str) -> None:
        """Select off/continuous/existing weekly schedule for local SD storage.

        Scheduled mode needs a pre-existing nonempty schedule; this method never
        creates guessed time windows. It preserves retention and unknown fields.
        SD media is required to actually record, even if a setting is accepted.
        """
        if mode not in ("off", "continuous", "scheduled"):
            raise ValueError("Expected off, continuous or scheduled")
        with self._lock:
            data = self._document("ccm_record_task_get", "task")
            schedule = data.get("sch")
            if (
                not isinstance(schedule, dict)
                or not {"enable", "full_time"} <= schedule.keys()
            ):
                raise MipcProtocolError("ccm_record_task_get")
            if mode == "scheduled" and not schedule.get("times"):
                raise ValueError("Configure a recording schedule first")
            patch = {"enable": int(mode != "off")}
            if mode != "off":
                patch["full_time"] = int(mode == "continuous")
            self._require_existing(data, {"sch": patch})
            self.call("ccm_record_task_set", task=merge_document(data, {"sch": patch}))

    def set_motion_alarm_enabled(self, enabled: bool) -> None:
        """Toggle only the motion action. Global arming and other outputs stay as-is.

        Motion notifications require both global arming and this action enabled.
        Never infer permission to arm other configured IO/record/snapshot actions.
        """
        if type(enabled) is not bool:
            raise ValueError("Expected boolean enabled")
        with self._lock:
            data = self.get_alert_actions()
            actions = data.get("actions")
            if not isinstance(actions, list):
                raise MipcProtocolError("ccm_alert_action_get")
            matches = [
                a
                for a in actions
                if isinstance(a, dict) and a.get("token") == "motion_alert"
            ]
            if len(matches) != 1 or type(matches[0].get("enable")) not in (int, bool):
                raise MipcProtocolError("ccm_alert_action_get")
            self.call(
                "ccm_alert_action_set",
                actions=merge_document(matches[0], {"enable": int(enabled)}),
            )

    def set_alarm_armed(self, enabled: bool) -> None:
        """Explicit global arming: may activate existing IO, snapshot and recording actions."""
        self.set_alert_actions(enabled=enabled, actions=[])

    def update_misc(self, **changes: Any) -> None:
        """Update observed misc fields, e.g. flip and power_freq.

        Power frequency is the firmware's enum, not a value in hertz. No
        undocumented conversion is applied; inspect get_misc() first.
        """
        self._update_document("ccm_misc_get", "info", "ccm_misc_set", changes)

    def update_osd(self, **changes: Any) -> None:
        self._update_document("ccm_osd_get", "osd", "ccm_osd_set", changes)

    def update_alert_config(self, **changes: Any) -> None:
        self._update_document("ccm_alert_dev_get", "conf", "ccm_alert_dev_set", changes)

    def update_motion_mask(self, changes: Mapping[str, Any]) -> None:
        self._update_document(
            "ccm_motion_mask_get", "conf", "ccm_motion_mask_set", changes
        )

    def update_recording(self, changes: Mapping[str, Any]) -> None:
        """Merge task fields while retaining schedules and retention settings."""
        self._update_document(
            "ccm_record_task_get", "task", "ccm_record_task_set", changes
        )

    def _update_document(self, get_method, key, set_method, changes):
        if not isinstance(changes, Mapping) or not changes:
            raise ValueError("Expected non-empty changes")
        with self._lock:
            document = self._document(get_method, key)
            self._require_existing(document, changes)
            self.call(set_method, **{key: merge_document(document, changes)})

    @classmethod
    def _require_existing(cls, document: dict, changes: Mapping) -> None:
        for key, value in changes.items():
            if key not in document:
                raise ValueError("Setting was not returned by this firmware")
            old = document[key]
            if isinstance(value, Mapping):
                if not isinstance(old, dict):
                    raise ValueError("Setting must keep the camera's document shape")
                cls._require_existing(old, value)
            elif type(value) is not type(old) and not (
                type(old) is int and type(value) is bool
            ):
                raise ValueError("Setting must keep the camera's value type")

    def set_alert_actions(self, *, enabled: bool, actions: list[dict]) -> None:
        """Update each supplied action by token, then set global arming.

        The camera accepts one action object per request, not an array. Updates
        are sequential, not atomic; an error can leave earlier actions changed.
        Read get_alert_actions() before editing and verify after writing. An
        empty list changes only global arming; omitted actions are preserved.
        """
        if (
            type(enabled) is not bool
            or not isinstance(actions, list)
            or not all(isinstance(a, dict) for a in actions)
        ):
            raise ValueError("Expected boolean enabled and list of actions")
        if any(not isinstance(a.get("token"), str) or not a["token"] for a in actions):
            raise ValueError("Each action requires a nonempty token")
        with self._lock:
            for action in actions:
                self.call("ccm_alert_action_set", actions=action)
            self.call("ccm_alert_action_set", enable=enabled)

    def get_message_filters(self) -> dict[str, Any]:
        return self.call("ccm_msg_filter_get")

    def set_message_filters(self, *, generated: str, published: str) -> None:
        """Filters are MIPC expression strings, passed as data without eval."""
        if not isinstance(generated, str) or not isinstance(published, str):
            raise ValueError("Expected filter strings")
        self.call("ccm_msg_filter_set", gen_filter=generated, pub_filter=published)

    def get_messages(
        self,
        *,
        start: int = 0,
        count: int = 20,
        filter: str = "",
        flag: int = 0,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> dict[str, Any]:
        self._range(count, -128, 128)
        if count == 0:
            raise ValueError("count must not be zero")
        return self.call(
            "ccm_msg_get",
            start=start,
            counts=count,
            filter=filter,
            flag=flag,
            start_time=start_time,
            end_time=end_time,
        )

    def get_cruise(self) -> dict[str, Any]:
        """The wire protocol misspells cruise as curise."""
        return self.call("ccm_curise_get")

    def control_cruise(self, command: str, index: int | None = None) -> dict[str, Any]:
        """Firmware-specific command; inspect catalog/evidence before use."""
        return self.call("ccm_curise_set", type=command, index=index)

    def get_scenes(self) -> dict[str, Any]:
        return self.call("ccm_scene_get")

    def set_scenes(self, info: Any, *, all: int = 0) -> None:
        self.call("ccm_scene_set", all=all, info=info)

    def get_schedule(self) -> dict[str, Any]:
        return self.call("ccm_schedule_get")

    def set_schedule(self, schedule: Any) -> None:
        self.call("ccm_schedule_set", sch=schedule)

    def get_external_devices(
        self, *, flag: int = 0, start: int = 0, count: int = 20
    ) -> dict[str, Any]:
        return self.call("ccm_exdev_get", flag=flag, start=start, counts=count)

    def discover_external_devices(
        self, *, flag: int = 0, timeout: int = 30, interval: int = 1
    ) -> dict[str, Any]:
        """Explicit pairing discovery on the camera; never runs on construction."""
        return self.call(
            "ccm_exdev_discover", flag=flag, timeout=timeout, interval=interval
        )

    def add_external_device(
        self, id: str, model: str, *, timeout: int = 30, interval: int = 1
    ) -> dict[str, Any]:
        return self.call(
            "ccm_exdev_add", id=id, model=model, timeout=timeout, interval=interval
        )

    def remove_external_device(self, id: str) -> None:
        self.call("ccm_exdev_del", id=id)

    def get_zone(self, device_serial: str) -> dict[str, Any]:
        return self.call("ccm_zone_get", dev_sn=device_serial)

    def get_hardware_test(self) -> dict[str, Any]:
        return self.call("ccm_hardware_test_get")

    def run_hardware_test(self, external_device: Any) -> dict[str, Any]:
        return self.call("ccm_hardware_test", exdev=external_device)

    def set_nickname(self, nickname: str) -> None:
        if not isinstance(nickname, str) or not nickname or len(nickname) > 128:
            raise ValueError("Expected a nickname of 1..128 characters")
        self.call("ccm_nick_set", nick=nickname)

    def set_network(self, changes: Mapping[str, Any]) -> None:
        """May disconnect the camera. No reconnection, scanning or cloud fallback."""
        if not isinstance(changes, Mapping) or not changes:
            raise ValueError("Expected non-empty changes")
        with self._lock:
            document = self.get_network()
            self._require_existing(document, changes)
            self.call("ccm_net_set", info=merge_document(document, changes))

    def set_ntp(
        self,
        *,
        auto_sync: bool,
        manual: dict | list | None = None,
        dhcp: int | None = None,
    ) -> None:
        if type(auto_sync) is not bool:
            raise ValueError("auto_sync must be a boolean")
        self.call("ccm_ntp_set", auto_sync=auto_sync, manual=manual, dhcp=dhcp)

    def set_date(
        self,
        utc_date: dict,
        *,
        timezone: str | int | None = None,
        type: str | int | None = None,
        daylight_savings: int | None = None,
    ) -> None:
        """Send the structured clock document named utc_date on the wire.

        Firmware timezone/NTP behavior is not uniform. This is an explicit raw
        clock-setting operation, not a verified timezone-only workflow. It never
        changes the host computer's clock.
        """
        if not isinstance(utc_date, dict) or not {"date", "time"} <= utc_date.keys():
            raise ValueError("Expected structured date and time")
        self.call(
            "ccm_date_set",
            utc_date=utc_date,
            timezone=timezone,
            type=type,
            daylight_savings=daylight_savings,
        )

    def set_storage_enabled(self, enabled: bool, *, token: str = "sd") -> None:
        if type(enabled) is not bool:
            raise ValueError("Expected boolean enabled")
        self.call("ccm_disk_ctl", token=token, conf={"enable": enabled})

    def control_storage(self, command: str, *, token: str = "sd") -> None:
        """Explicit storage maintenance; format destroys recordings."""
        if command not in ("format", "repair", "mount", "umount"):
            raise ValueError("Unsupported storage command")
        self.call("ccm_disk_ctl", token=token, type=command)

    def reboot(self) -> None:
        self.call("ccm_reboot")

    def restore(self, *, keep_configuration: bool = True) -> None:
        """Explicit firmware restore; may reset credentials and network settings."""
        if type(keep_configuration) is not bool:
            raise ValueError("Expected boolean keep_configuration")
        self.call("ccm_restore", backup=keep_configuration)

    def get_upgrade_status(self, *, check: bool = False) -> dict[str, Any]:
        """check=True may cause the CAMERA to check the vendor's update service."""
        if type(check) is not bool:
            raise ValueError("Expected boolean check")
        return self.call("ccm_upgrade_get", check=check)

    def start_upgrade(self, image_source: str) -> None:
        """Explicit firmware operation; source 'download' may use vendor services."""
        if not isinstance(image_source, str) or not image_source:
            raise ValueError("Expected image source")
        self.call("ccm_upgrade", img_src=image_source)

    def get_box_configuration(self, box_serial: str) -> dict[str, Any]:
        return self.call("ccm_box_conf_get", target_serial=box_serial)

    def get_box_recordings(
        self,
        box_serial: str,
        device_serial: str,
        *,
        flag: int = 0,
        start_time: int = 0,
        end_time: int = 0,
    ) -> dict[str, Any]:
        return self.call(
            "ccm_box_get",
            target_serial=box_serial,
            sn=device_serial,
            flag=flag,
            start_time=start_time,
            end_time=end_time,
        )

    def set_box_recordings(
        self,
        box_serial: str,
        device_serial: str,
        command: str,
        *,
        start_time: int = 0,
        end_time: int = 0,
    ) -> None:
        self.call(
            "ccm_box_set",
            target_serial=box_serial,
            sn=device_serial,
            cmd=command,
            start_time=start_time,
            end_time=end_time,
        )

    def login_box(
        self, box_serial: str, username: str, password: str, *, enabled: bool = True
    ) -> dict[str, Any]:
        return self.call(
            "ccm_box_login",
            target_serial=box_serial,
            enable=enabled,
            username=username,
            password=password,
        )

    def _media_url(
        self, method: str, token: str, protocol: str, allow_remote: bool
    ) -> str:
        if protocol not in ("rtmp", "rtsp"):
            raise ValueError("Expected rtmp or rtsp")
        data = self.call(
            method,
            setup={"stream": "RTP_Unicast", "trans": {"proto": protocol}},
            token=token,
        )
        uri = data.get("uri")
        url = uri.get("url") if isinstance(uri, dict) else data.get("url")
        if not isinstance(url, str):
            raise MipcProtocolError(method)
        try:
            parsed = urlsplit(url)
            expected = urlsplit("http://" + self.host)
            if (
                parsed.scheme != protocol
                or not parsed.hostname
                or parsed.netloc.endswith(":")
            ):
                raise ValueError("Invalid media URL")
            _ = (
                parsed.port
            )  # Validate the port even though the caller owns media transport.
            if (
                not allow_remote
                and parsed.hostname.lower() != expected.hostname.lower()
            ):
                raise ValueError("Remote media address")
        except ValueError:
            raise MipcProtocolError(method) from None
        return url

    def get_stream_url(
        self, token: str = "p0", *, protocol: str = "rtmp", allow_remote: bool = False
    ) -> str:
        """Negotiate a URL; it must name the configured camera unless opted out."""
        return self._media_url("ccm_play", token, protocol, allow_remote)

    def get_playback_url(
        self, token: str, *, protocol: str = "rtmp", allow_remote: bool = False
    ) -> str:
        return self._media_url("ccm_replay", token, protocol, allow_remote)

    def get_talk_url(
        self, token: str, *, protocol: str = "rtmp", allow_remote: bool = False
    ) -> str:
        """Negotiate talk transport only; encoding/sending microphone audio is caller-owned."""
        return self._media_url("ccm_talk", token, protocol, allow_remote)

    def send_audio(
        self,
        pcm: bytes | Iterable[bytes],
        token: str = "p0",
        *,
        timeout: float = 10,
        stop_event: Event | None = None,
    ) -> AudioSendResult:
        """Send interruptible PCM16 mono 16 kHz using optional PyAV.

        Publishes AAC over local RTMP. Does not change volume/mute, use a cloud
        relay, or retry failed uploads. This client is locked until completion.
        """
        from .audio import send_pcm

        return send_pcm(self, pcm, token, timeout, stop_event)

    def get_external_switch_enabled(self) -> bool:
        """Read the Android client's external-switch flag; meaning is model-specific."""
        data = self.call("ccm_exsw_get")
        value = data.get("enable")
        if type(value) not in (int, bool) or value not in (0, 1):
            raise MipcProtocolError("ccm_exsw_get")
        return bool(value)

    def get_sleep_config(self) -> dict[str, Any]:
        """Read a complete Android sleep document, where supported by firmware."""
        return self.call("ccm_sleep_get")

    def get_crop_zoom(self, token: str = "vs0") -> dict[str, Any]:
        """Read Android crop/zoom configuration without guessing coordinate units."""
        return self.call("ccm_crop_zoom_get", token=token)

    def request_snapshot(self, token: str = "p0") -> dict[str, Any]:
        return self.call("ccm_snapshot", token=token)

    def subscribe(self) -> dict[str, Any]:
        """Request subscription acknowledgement, not a persistent event listener."""
        return self.call("ccm_subscribe")
