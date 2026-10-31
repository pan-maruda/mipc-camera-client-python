# MIPC camera client â€” local control

A Python client that talks directly to a MIPC-compatible camera or gateway at an address you provide. No Windows application, vendor JavaScript, native plugin, cloud account discovery, telemetry, or background service is included.

This fork expands [Pan Maruda's original MIPC camera client](https://github.com/pan-maruda/mipc-camera-client-python). The current version is **0.2.0.dev0**, not a published PyPI release. The Windows client supplies protocol evidence; see [hardware validation](docs/HARDWARE.md) for tested camera support.

## Install from GitHub

Python 3.10 or newer:

```shell
python -m pip install "mipc-camera-client @ git+https://github.com/brylee123/mipc-camera-client-python.git@main"
```

## Basic use

```python
import os
from pathlib import Path
from mipc_camera_client import MipcCameraClient

with MipcCameraClient("192.168.1.50:80", timeout=10) as camera:
    camera.login(os.environ["CAMERA_USER"], os.environ["CAMERA_PASSWORD"])
    print(camera.get_info())
    Path("snapshot.jpg").write_bytes(camera.get_image())
    print(camera.get_stream_url())  # URL negotiation only; caller owns playback
```

Construction does not contact anything. Login uses the existing MIPC DH/DES protocol at the supplied host. Each operation stays at that host, ignores environment proxies and .netrc, rejects HTTP redirects, and has a bounded timeout. There is no automatic login retry or cloud fallback. Expired sessions, including the f300 `Receiver / InvalidSession` response, raise `MipcAuthenticationError`. Callers can renew authentication and retry reads once; the library never automatically replays settings writes, movement or maintenance commands. The legacy protocol uses HTTP and legacy cryptography; it does not provide modern transport security.

The hardware-tested f300 uses its device serial as the local login name and its separate Device/Admin PW. For that model, use `camera.login(camera.get_device_sn(), device_password)`. MIPC cloud account credentials do not authenticate the local camera. Other firmware may use a different local username.

## Security: keep camera traffic local

For better privacy, block the camera's internet access at your router or firewall
while allowing your local client to reach it. The library uses the configured
camera host, but it cannot prevent the camera firmware from independently
contacting vendor services. Network restrictions reduce that exposure; they do
not make the camera firmware trusted.

1. Reserve the camera's LAN address in your router's DHCP settings.
2. Deny the camera's outbound internet (WAN) traffic across all protocols and
   ports, covering **both IPv4 and IPv6** if enabled. Blocking DNS or vendor
   domains alone is insufficient.
3. Preserve local access from your client or Home Assistant to the camera's
   control and media services, including return traffic. A generic **Block device**
   option or guest-network isolation may also block LAN access. With a separate
   camera/IoT network, allow the required traffic between networks explicitly.
4. Restrict every connected interface: Ethernet and Wi-Fi can both be active with
   different addresses. Block both or disconnect the unused interface. Do not
   forward camera ports from the internet; remove existing camera port forwards
   or UPnP mappings.
5. Verify enforcement of the WAN block, restart the camera, and check local
   snapshots, streaming, controls and events on your model.

Vendor cloud viewing, notifications, updates and internet time synchronization
may stop working. A trusted local time server can be used where supported, with
the necessary local access allowed. Keep the camera clock correct when consuming
timestamped events. Your client computer or Home Assistant can retain internet
access for dependency installation and updates.

Local operations have been tested, but hardware validation with camera WAN access
blocked is **still outstanding**. The camera protocol uses HTTP and legacy
cryptography; limit LAN access to trusted devices, ideally using a separate
camera/IoT network. Internet blocking does not add transport encryption.

## Settings and controls

```python
# After login; call only the settings your hardware supports.
print(camera.get_microphone_inputs())
print(camera.get_speaker())  # Direct configuration; list discovery is unsupported on f300.
print(camera.get_imaging())
camera.update_imaging(brightness=55, mode="auto")
camera.set_microphone_level(60)
camera.update_microphone("mic0", silent=True)
camera.set_speaker_level(40)
camera.set_flip(True)
camera.update_osd(text="Front door", date={"time_enable": 1})
print(camera.get_alert_config())
print(camera.get_recording())
print(camera.get_disks())
camera.control_ptz(tilt_x=5, tilt_y=0)
```

Document update methods fetch the current document and preserve unrelated and unknown fields. They reject fields not returned by the camera. Simple setters validate their input ranges; firmware-specific values in advanced document updates are passed without guessed enum conversions. Array replacement is explicit, not an automatic merge of schedules or actions. Use the input/output tokens returned by your device; `mic0`, `ao0`, `vs0`, `p0`, and `ptz0` are examples/defaults, not universal capabilities.

The API covers audio inputs/outputs, image modes and levels, flip/power-frequency configuration, OSD, motion and alert configuration/actions, recording schedules, storage, date/NTP, network/Wi-Fi, PTZ/cruise, scenes, schedules, external accessories, gateway/box operations, device passwords, snapshots, media negotiation, events, and maintenance. See [the method reference](docs/API.md).

## Capability inspection

```python
report = camera.probe_capabilities(["imaging", "microphones", "osd", "disks"])
print(report.readable)
print(report.rejected)
```

Probing is opt-in and issues only the selected reads. A rejected read can mean missing support, insufficient permissions, or a different response schema. A successful read does not prove that writes are supported. Transport and session failures propagate immediately.

## Local event queues

```python
with camera.event_queue() as events:
    for item in events.poll(timeout=5):
        from mipc_camera_client.events import MotionEvent
        event = MotionEvent.from_message(item)
        if event is not None:
            print(event)  # Does not print the device serial.
```

Queues use the observed `mmq_create`, `ccm_subscribe`, `mmq_pick`, and `mmq_destroy` flow. Wire timeouts are milliseconds; Python timeouts are seconds. Polling is synchronous and blocks other operations on the same client. Use a separately logged-in client when you need simultaneous controls. The library starts no threads and does not reconnect silently. Local `alert` / `motion_alert` pulses have been received from an f300 while panning changed its view. No motion-clear event was observed. Polls can time out even after successful delivery; callers must close the old queue/session and reconnect with backoff. A timeout must not be interpreted as a motion-clear state. Physical movement still needs a separate validation.

The camera must have its motion alarm armed. Reading/subscribing does not change alarm actions. `set_alert_actions()` updates one token at a time; inspect existing IO, snapshot and recording actions before arming.

## Advanced endpoints

The data-only [protocol inventory](docs/PROTOCOL.md) records **89 observed RPCs: 80 device/queue operations, 5 authentication operations, and 4 account operations**. It includes bundle hashes, call-site offsets, observed field names, and request shapes in `mipc_camera_client/endpoints.json`. No vendor bundle or cached camera/account payload is shipped.

```python
# Structured Python input; session IDs and MIPC's HTTP encoding are added.
print(camera.call("ccm_msg_get", flag=0, start=0, counts=20, filter="record"))
```

`call()` accepts catalogued device/queue methods. Account registration, recovery and binding are excluded. `run_rpc()` remains the original low-level escape hatch for flattened parameters at the configured host. Library exceptions identify the method without including credential-bearing URLs or response dumps.

Maintenance operations execute when explicitly called. `reboot()`, `restore()`, `control_storage("format")`, `set_network()`, and password changes can disrupt the device or erase data. Nothing calls them automatically. Firmware checks/downloads, NTP, alert actions and network configuration may cause the **camera firmware** to contact other hosts; the library itself does not follow those hosts. Complete offline isolation requires camera network restrictions.

Stream, playback and `get_talk_url()` methods negotiate URLs. The optional `send_audio()` method implements bounded local AAC speaker uploads; it does not capture a microphone or embed a player. Returned media URLs must match the configured camera hostname unless `allow_remote=True` is explicitly requested. RTMP/RTSP support depends on firmware. Native plugin clip export and full Windows UI parity are not claimed.

## Command line

Set `CAMERA_HOST`, `CAMERA_USER` and `CAMERA_PASSWORD` in your environment, then:

```shell
mipc_camera_client info
mipc_camera_client read imaging
mipc_camera_client probe
mipc_camera_client snapshot image.jpg
mipc_camera_client stream
mipc_camera_client ptz --x 5 --y 0
mipc_camera_client endpoints ccm_osd_set
mipc_camera_client rpc ccm_msg_get --data-file request.json
```

`endpoints` works offline without credentials. RPC input is a JSON file or standard input (`--data-file -`). It uses structured fields, not flattened `d...` names. RPC commands can write settings and execute immediately. Output documents can contain device identifiers or tokens; treat saved output accordingly.

## Development and verification

```shell
python -m pip install poetry
poetry install --with dev
poetry run pytest
poetry run ruff check mipc_camera_client tests tools
poetry run ruff format --check mipc_camera_client tests tools
poetry build
```

Tests cover upstream crypto vectors, request encoding, all catalog device dispatch entries, conservative settings updates, auth/error handling, media host restrictions, queue lifecycle, and a real loopback HTTP camera simulator. A read-only f300 hardware run also passed 30 checks, produced a valid 1920Ã—1080 JPEG and decoded three local H.264/RTMP video frames. Speaker-list discovery returned HTTP 404 while direct speaker configuration remained readable; this is now reported as `MipcUnsupportedError`. See [hardware validation](docs/HARDWARE.md) for scope and limits. Follow-up tests verified 16 settings write/read-back paths, a reversible brightness change, both physical motors, and Home Assistant snapshot/HLS consumption. Persistence across a reboot, actual recording without an SD card, and maintenance operations remain unverified.

## Credits and license

The original library was created by [Pan Maruda (pan-maruda)](https://github.com/pan-maruda) in [mipc-camera-client-python](https://github.com/pan-maruda/mipc-camera-client-python). Their reverse-engineered local authentication, snapshot, streaming and pan/tilt implementation forms the foundation of this fork.

This fork adds the expanded device API, protocol inventory and hardware validation. The original copyright notice and BSD-3-Clause license are preserved in [LICENSE](LICENSE).

## Video quality profiles

`get_stream_profiles()` returns immutable `StreamProfile` objects with the
advertised playback `token` and firmware `name`. A name such as D1 or CIF does
**not** establish its resolution. `width` and `height` remain `None` until measured.

`probe_stream_profiles(decoder)` negotiates each advertised stream at the local
camera and supplies its private URL to your bounded decoder callback. Return
`(frame.width, frame.height)` from a decoded frame. The SDK has no media-decoder
dependency; the caller provides one. Failed probes retain unknown dimensions;
authentication errors propagate. Keep URLs private and bound connection/read times.

On the tested f300, p0 decoded at 1920×1080. Both p1 (advertised D1) and p2
(advertised CIF) decoded at 640×360; the server sometimes returned a p2 media path
for a p1 request. The Windows client sends these same tokens but contains static
resolution assumptions. Do not convert its labels into assumed frame sizes.
Selecting a profile changes playback negotiation, not the camera encoder settings.

## Clear device controls

The [device settings reference](docs/API.md#explicit-device-settings) covers
credential-free interface/IP/MAC views, camera-advertised timezone metadata, OSD weekday /
calendar date / clock time and formats, MIPC power frequency, explicit SD recording
modes and separate motion-action/global-arming controls. All changes stay at the
configured camera host and preserve unrelated document fields. Restart and factory
reset are explicit maintenance calls; factory reset has not been live-tested.

**Continuous recording** means all-day recording to the camera's local SD storage.
**Scheduled recording** uses configured time windows. **Recording box** APIs address
separate MIPC storage hardware. The compatibility method `set_recording_enabled`
only enables the existing SD task; use `set_recording_mode` to choose the mode.

Timezone editing remains an open hardware issue: the tested f300 can acknowledge
an update while shifting its clock incorrectly. The library reports the setting
and advertised UTC offsets; it does not claim a safe timezone-only setter. The
camera's original local clock and settings were restored after this investigation.

## Send audio to the speaker

The updated library has not been published to PyPI. Install the review branch
with its optional codec dependency:

```shell
python -m pip install "mipc-camera-client[audio] @ git+https://github.com/brylee123/mipc-camera-client-python.git@feature/android-audio"
```

After login:

```python
from pathlib import Path

# Raw signed PCM16 little-endian, mono, 16000 Hz; with no fixed duration cap.
result = camera.send_audio(Path("announcement.pcm").read_bytes())
print(result.duration)
```

This publishes AAC over RTMP directly to the configured camera. It uses the
existing speaker volume, does not unmute the camera microphone, and never retries
failed audio. Pass a `threading.Event` as `stop_event` to stop an upload. This
synchronous call locks its client until completion; pass an iterable of PCM chunks
for incremental input and use a separate client for
concurrent controls. Completion confirms transport, not audibility on every model.
The tested f300 produced a matching AAC test tone in an authorized acoustic
loopback check. See [Android evidence and limits](docs/ANDROID.md).

Android inspection also added explicit read helpers `get_external_switch_enabled`,
`get_sleep_config` and `get_crop_zoom`. On the tested f300 only the external-switch
flag was readable; its physical meaning is unverified. Sleep/crop reads returned
HTTP 404 and are not advertised as supported controls on that camera.
