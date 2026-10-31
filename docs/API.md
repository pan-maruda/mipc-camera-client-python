# API reference

All methods are synchronous. Settings are not polled and commands are not retried automatically. Full response documents retain firmware extensions. Every operation uses the configured host. Request schemas and the hardware-validation boundary are in [PROTOCOL.md](PROTOCOL.md).

### `activate(self, activation_code: 'str') -> 'dict[str, Any]'`

Send activation to this host only; offline support depends on firmware.

### `add_device(self, serial: 'str', password: 'str') -> 'dict[str, Any]'`

Add a device to the configured gateway, without cloud lookup.

### `add_external_device(self, id: 'str', model: 'str', *, timeout: 'int' = 30, interval: 'int' = 1) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `call(self, method: 'str', *, target_serial: 'str | None' = None, **fields: 'Any') -> 'dict'`

Call an observed local device RPC using unflattened Python values.

The catalog describes request shapes, not hardware support. Unknown
endpoints and cloud account APIs are excluded. run_rpc remains the
backwards-compatible low-level escape hatch at the configured host.

### `change_device_password(self, username: 'str', old_password: 'str', new_password: 'str') -> 'None'`

Update an explicitly named device user; does not change a cloud account.

### `change_password(self, old_password: 'str', new_password: 'str', *, guest: 'bool' = False) -> 'None'`

Change the current local account password and require explicit login again.

### `check_session(self) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `close(self) -> None`

Release the owned HTTP session.

### `control_cruise(self, command: 'str', index: 'int | None' = None) -> 'dict[str, Any]'`

Firmware-specific command; inspect catalog/evidence before use.

### `control_ptz(self, tilt_x, tilt_y, speed_x=48, speed_y=16, token='ptz0')`

Relative pan/tilt command; units and limits depend on firmware.

### `control_storage(self, command: 'str', *, token: 'str' = 'sd') -> 'None'`

Explicit storage maintenance; format destroys recordings.

### `discover_external_devices(self, *, flag: 'int' = 0, timeout: 'int' = 30, interval: 'int' = 1) -> 'dict[str, Any]'`

Explicit pairing discovery on the camera; never runs on construction.

### `event_queue(self, *, lifetime: 'int' = 30)`

Create a local queue and subscribe, without starting a listener thread.

### `get_alert_actions(self) -> dict[str, typing.Any]`

Explicit operation; see the protocol inventory for request fields.

### `get_alert_config(self) -> mipc_camera_client.settings.AlertConfig`

Explicit operation; see the protocol inventory for request fields.

### `get_box_configuration(self, box_serial: 'str') -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_box_recordings(self, box_serial: 'str', device_serial: 'str', *, flag: 'int' = 0, start_time: 'int' = 0, end_time: 'int' = 0) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_cruise(self) -> 'dict[str, Any]'`

The wire protocol misspells cruise as curise.

### `get_date(self) -> dict[str, typing.Any]`

Explicit operation; see the protocol inventory for request fields.

### `get_device_info(self, select: str | None = None) -> mipc_camera_client.settings.DeviceInfo`

Explicit operation; see the protocol inventory for request fields.

### `get_device_sn(self) -> Optional[str]`

gets the camera serial number (cached for the client lifetime)

### `get_devices(self, start: 'int' = 0, count: 'int' = 128) -> 'dict[str, Any]'`

List devices known to this configured gateway; never discovers a cloud server.

### `get_disks(self) -> list[mipc_camera_client.settings.DiskStatus]`

Explicit operation; see the protocol inventory for request fields.

### `get_external_devices(self, *, flag: 'int' = 0, start: 'int' = 0, count: 'int' = 20) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_hardware_test(self) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_image(self, token: str = 'p0_xxxxxxxxxx') -> bytes`

gets a JPEG snapshot of what the camera sees now

### `get_imaging(self, token: str = 'vs0') -> mipc_camera_client.settings.ImagingConfig`

Explicit operation; see the protocol inventory for request fields.

### `get_info(self) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_ip_cameras(self) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_message_filters(self) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_messages(self, *, start: 'int' = 0, count: 'int' = 20, filter: 'str' = '', flag: 'int' = 0, start_time: 'int | None' = None, end_time: 'int | None' = None) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_microphone_inputs(self) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_microphones(self) -> list[mipc_camera_client.settings.AudioConfig]`

Explicit operation; see the protocol inventory for request fields.

### `get_misc(self) -> mipc_camera_client.settings.MiscConfig`

Explicit operation; see the protocol inventory for request fields.

### `get_motion_mask(self) -> dict[str, typing.Any]`

Explicit operation; see the protocol inventory for request fields.

### `get_network(self, *, tokens: list[str] | None = None, items: list[str] | None = None, scan: bool = False) -> dict[str, typing.Any]`

Read configuration; wireless scanning is opt-in via scan=True.

### `get_ntp(self) -> dict[str, typing.Any]`

Explicit operation; see the protocol inventory for request fields.

### `get_osd(self) -> mipc_camera_client.settings.OsdConfig`

Explicit operation; see the protocol inventory for request fields.

### `get_playback_url(self, token: 'str', *, protocol: 'str' = 'rtmp', allow_remote: 'bool' = False) -> 'str'`

Explicit operation; see the protocol inventory for request fields.

### `get_recording(self) -> dict[str, typing.Any]`

Explicit operation; see the protocol inventory for request fields.

### `get_rtmp_stream(self, token: Literal['p0', 'p1', 'p2', 'p3'] = 'p0')`

Get an RTMP URL at the configured camera host.

### `get_scenes(self) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_schedule(self) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_speaker(self, token: str = 'ao0') -> mipc_camera_client.settings.AudioConfig`

Explicit operation; see the protocol inventory for request fields.

### `get_speaker_outputs(self) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `get_stream_url(self, token: 'str' = 'p0', *, protocol: 'str' = 'rtmp', allow_remote: 'bool' = False) -> 'str'`

Negotiate a URL; it must name the configured camera unless opted out.

### `get_talk_url(self, token: 'str', *, protocol: 'str' = 'rtmp', allow_remote: 'bool' = False) -> 'str'`

Negotiate talk transport only; encoding/sending microphone audio is caller-owned.

### `get_upgrade_status(self, *, check: 'bool' = False) -> 'dict[str, Any]'`

check=True may cause the CAMERA to check the vendor's update service.

### `get_video_sources(self) -> list[dict[str, typing.Any]]`

Explicit operation; see the protocol inventory for request fields.

### `get_zone(self, device_serial: 'str') -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `login(self, username: str, password: str)`

log in to the camera api and start a session

### `login_box(self, box_serial: 'str', username: 'str', password: 'str', *, enabled: 'bool' = True) -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `logout(self) -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `probe_capabilities(self, names: 'list[str] | None' = None)`

Explicitly test selected read operations; rejection is not proof of absence.

### `reboot(self) -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `remove_device(self, serial: 'str') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `remove_external_device(self, id: 'str') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `request_snapshot(self, token: 'str' = 'p0') -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `restore(self, *, keep_configuration: 'bool' = True) -> 'None'`

Explicit firmware restore; may reset credentials and network settings.

### `run_hardware_test(self, external_device: 'Any') -> 'dict[str, Any]'`

Explicit operation; see the protocol inventory for request fields.

### `run_rpc(self, msg_type, data, response_type='js', *, request_timeout=None)`

Low-level request to this host only; data must already be flattened.

### `set_alert_actions(self, *, enabled: 'bool', actions: 'list[dict]') -> 'None'`

Update supplied actions by token, one action object per request, then set global arming. An empty list changes arming only. Omitted actions are preserved. Updates are sequential and can partially complete on failure; read before editing and verify afterward.

### `set_box_recordings(self, box_serial: 'str', device_serial: 'str', command: 'str', *, start_time: 'int' = 0, end_time: 'int' = 0) -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `set_date(self, utc_date: 'dict', *, timezone: 'str | int | None' = None, type: 'str | int | None' = None, daylight_savings: 'int | None' = None) -> 'None'`

Send the structured camera clock document named `utc_date` on the wire. Firmware timezone/NTP behavior varies; this is an explicit raw clock-setting operation, not a verified timezone-only workflow. It never changes the host computer's clock.

### `set_flip(self, enabled: bool) -> None`

Explicit operation; see the protocol inventory for request fields.

### `set_imaging(self, field: str, value: int | str, token: str = 'vs0') -> None`

Explicit operation; see the protocol inventory for request fields.

### `set_message_filters(self, *, generated: 'str', published: 'str') -> 'None'`

Filters are MIPC expression strings, passed as data without eval.

### `set_microphone_level(self, level: int, token: str | None = None) -> None`

Explicit operation; see the protocol inventory for request fields.

### `set_network(self, changes: 'Mapping[str, Any]') -> 'None'`

May disconnect the camera. No reconnection, scanning or cloud fallback.

### `set_nickname(self, nickname: 'str') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `set_ntp(self, *, auto_sync: 'bool', manual: 'dict | list | None' = None, dhcp: 'int | None' = None) -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `set_osd_enabled(self, enabled: bool) -> None`

Explicit operation; see the protocol inventory for request fields.

### `set_recording_enabled(self, enabled: bool) -> None`

Explicit operation; see the protocol inventory for request fields.

### `set_scenes(self, info: 'Any', *, all: 'int' = 0) -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `set_schedule(self, schedule: 'Any') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `set_speaker_level(self, level: int, token: str = 'ao0') -> None`

Explicit operation; see the protocol inventory for request fields.

### `set_storage_enabled(self, enabled: 'bool', *, token: 'str' = 'sd') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `start_upgrade(self, image_source: 'str') -> 'None'`

Explicit firmware operation; source 'download' may use vendor services.

### `subscribe(self) -> 'dict[str, Any]'`

Request subscription acknowledgement, not a persistent event listener.

### `update_alert_config(self, **changes: 'Any') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `update_imaging(self, *, token: 'str' = 'vs0', **changes: 'Any') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `update_microphone(self, token: 'str', **changes: 'Any') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `update_misc(self, **changes: 'Any') -> 'None'`

Update observed misc fields, e.g. flip and power_freq.

Power frequency is the firmware's enum, not a value in hertz. No
undocumented conversion is applied; inspect get_misc() first.

### `update_motion_mask(self, changes: 'Mapping[str, Any]') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `update_osd(self, **changes: 'Any') -> 'None'`

Explicit operation; see the protocol inventory for request fields.

### `update_recording(self, changes: 'Mapping[str, Any]') -> 'None'`

Merge task fields while retaining schedules and retention settings.

### `mipc_camera_client.events.MotionEvent.from_message(item) -> MotionEvent | None`

Normalize the locally observed `alert` / `motion_alert` pulse into an immutable
`serial_number`, `message_id`, and Unix-seconds `timestamp`. Unknown event codes,
missing identifiers and malformed values return `None`. No property content is
evaluated. This is a pulse, not a motion-on / motion-off state.

### `get_stream_profiles() -> list[StreamProfile]`

Read firmware-advertised p0–p3 properties. Return token/name metadata; absent,
malformed or conflicting profile declarations are omitted. No guessed profiles.

### `probe_stream_profiles(decoder) -> list[StreamProfile]`

Decode advertised streams through a caller-supplied `decoder(local_url)` callback
returning a width/height pair. Successful profiles include measured dimensions.
Failed probes retain unknown dimensions. Authentication failures propagate. The
callback must bound network/decode time; no encoder configuration is changed.

## Explicit device settings

- `get_network_interfaces() -> tuple[NetworkInterface, ...]` reads each interface's
  token, connection type, enabled flag, link status, MAC and IPv4 address. This
  view excludes Wi-Fi keys, SSIDs and nearby APs; `get_network()` remains the raw
  sensitive document. Both interfaces may be up. A working link is not proof of
  the active/default route or internet access.
- `set_power_frequency(hertz)` accepts integer 50 or 60. The extracted **MIPC** UI
  uses enum 0 for 60 Hz and 1 for 50 Hz. Its Vimtag OEM UI reverses the displayed
  order; cross-model/OEM behavior still needs validation. `update_misc(power_freq=...)`
  remains the raw enum API. Verified both enum readbacks on f300.
- `get_timezones() -> tuple[str, ...]` returns unique advertised UTC offsets from
  `ccm_zone_get.address.zones[].utc`, matching the extracted Windows UI option
  values. City names and zoneinfo file paths are metadata, not proven setter IDs.
  `get_ntp()["timezone"]` exposes the firmware's reported setting, which can still
  contain a legacy city label.
- No high-level timezone setter is offered: f300 tests found successful readback
  could accompany an incorrect clock shift. `set_date` / `set_ntp` remain explicit
  advanced APIs. Their raw calls are not a verified timezone-only workflow. Do
  not replay a cached clock or assume `utc_date` behaves uniformly across firmware.
- `get_recording_mode()` returns `off`, `continuous`, `scheduled`, or `None` for an
  unrecognized schema. `set_recording_mode(mode)` preserves task retention and
  schedule fields. Scheduled mode needs existing nonempty time windows. This is
  **local SD task recording**, requiring usable storage to produce footage.
- `set_recording_enabled(bool)` is retained for compatibility: it only changes the
  SD task's enable flag. It does not choose continuous mode.
- `set_motion_alarm_enabled(bool)` changes only the observed `motion_alert` action's
  enable flag. It preserves global arming, other actions and all output settings.
  Motion notifications require global arming as well as the motion action.
- `set_alarm_armed(bool)` explicitly changes global arming. Existing actions can
  activate IO outputs, snapshots and recording; it does not make those outputs safe.
- `reboot()` and `restore(keep_configuration=False)` already provide restart and
  factory reset. Factory reset can erase credentials/networking and was **not**
  executed during validation. No maintenance action is called automatically.

### OSD fields verified independently

```python
camera.update_osd(week=1)  # weekday
camera.update_osd(date={"date_enable": 1})  # calendar date
camera.update_osd(date={"time_enable": 1})  # clock time
camera.update_osd(date={"format": "MM-DD-YYYY"})  # also YYYY-MM-DD
camera.update_osd(date={"enable_12h": 1})  # 0 for 24-hour
```

Live f300 snapshots confirmed each flag independently; original settings were
restored. Other OEM date formats are not assumed supported.

### Playback labels and recording boxes

Windows client handlers map **HD** to p0, **Standard** to p1, and **Smooth** to p2.
The top label follows the device's advertised quality (HD1080p on the test f300).
D1 and CIF are firmware labels, not trustworthy resolution claims. Decode frames
for dimensions: the test camera yielded p0 1920×1080 and p1/p2 both 640×360.
Different profiles may still use different frame rates or bitrates.

The extracted **Auto** handler only changes the client label; it neither changes
`PlayProfile` nor sends a different camera token. No fictitious automatic camera
mode is exposed.

`get_box_recordings` / `set_box_recordings` target a separately addressed MIPC
recording box/gateway. They are distinct from the camera's continuous or scheduled
SD recording and are not claimed to work without that separate hardware.

## Android reads and speaker uploads

- `send_audio(pcm: bytes, token="p0", *, timeout=10, stop_event=None) -> AudioSendResult`:
  send with no fixed duration cap of signed PCM16 little-endian mono 16000 Hz audio as
  AAC/RTMP. Requires the optional `[audio]` extra. Timeout is a finite positive
  network-operation bound up to 30 seconds; audio is paced separately in real
  time. `stop_event` is an optional `threading.Event`. The result reports
  `samples_sent`, `sample_rate`, `duration` and `cancelled`. A few encoder-buffered
  samples may finish during stop; failed transmissions are never retried.
- `get_external_switch_enabled() -> bool`: validate and return the camera's
  `ccm_exsw_get` flag. Do not infer physical accessory behavior from this flag.
- `get_sleep_config() -> dict`: read `ccm_sleep_get` where implemented.
- `get_crop_zoom(token="vs0") -> dict`: read `ccm_crop_zoom_get` without assuming
  coordinate units or write support.

[Android inspection](ANDROID.md) records exact provenance and hardware limits.
