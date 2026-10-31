# f300 hardware validation

Date: 2026-10-30. Camera: f300; firmware: `v5.1.10.1811061306`. The camera was identified in the MIPC application and tested directly over its LAN HTTP interface. Local login used the device serial and its separate Device/Admin PW.

**30 of 31 checks passed; one endpoint is unsupported on this firmware.** No persistent settings, passwords, network configuration, storage contents, or firmware were changed by these tests. Event queues and media sessions were created explicitly for testing and closed afterwards.

## Read-only checks

| Check | Result |
| --- | --- |
| `login` | Passed |
| `identity` | Passed |
| `device_info` | Passed |
| `microphone_inputs` | Passed |
| `microphones` | Passed |
| `speaker_outputs` | MipcUnsupportedError (http_404) |
| `speaker` | Passed |
| `imaging` | Passed |
| `misc` | Passed |
| `osd` | Passed |
| `alert_config` | Passed |
| `alert_actions` | Passed |
| `motion_mask` | Passed |
| `recording` | Passed |
| `disks` | Passed |
| `video_sources` | Passed |
| `network_without_scan` | Passed |
| `ntp` | Passed |
| `date` | Passed |
| `cruise` | Passed |
| `scenes` | Passed |
| `schedule` | Passed |
| `message_filters` | Passed |
| `messages` | Passed |
| `snapshot` | Passed |
| `live_stream` | Passed |
| `session_check` | Passed |
| `event_queue_create` | Passed |
| `event_poll` | Passed |
| `event_queue_destroy` | Passed |
| `logout` | Passed |

## Media verification

* Snapshot: a valid JPEG was decoded/verified in memory at 1920Ã—1080. No image was saved or published.
* Streaming: the library negotiated an RTMP URL naming the configured camera. An external PyAV decoder opened that URL and decoded three H.264 video frames at 1920Ã—1080. PyAV is a test tool, not a library dependency.
* No stream URLs, credentials, session tokens, device serials, MAC addresses, network configuration values, video frames or audio recordings are included in this report.

## Device-specific findings

* `ccm_speakers_get` returns HTTP 404. `ccm_speaker_get` succeeds and returns speaker configuration. The library now raises `MipcUnsupportedError` for HTTP 404/405/501 instead of reporting a network failure. Discovery failure must not be treated as proof that the camera has no speaker.
* The microphone `entity` field is a nested object on this firmware. Its type annotation now accommodates that shape, and a synthetic regression fixture verifies preserving the nested object when encoding a settings update.
* The local device username is its serial. MIPC cloud account credentials are separate from the device credentials and do not authenticate this local interface.
* Queue creation, subscription, a two-second empty poll and queue destruction succeeded. No events were received during that poll; actual motion-event delivery has not been demonstrated.

## Follow-up settings, motor and Home Assistant validation

Later on 2026-10-30, the same f300 and firmware were exercised through the standalone [Home Assistant integration](https://github.com/brylee123/ha-mipc-camera), temporarily bundling this library at commit `1a6e1cf6a7648247481d270105ae753df527ca31`.

- All 16 exposed settings accepted writes of their original values and read back unchanged: four image levels, speaker and microphone levels, two motion sensitivity levels, image flip, microphone mute, OSD text/date/time toggles and text content, recording schedule enabled, and day/night mode. Brightness was additionally changed by one unit, read back, then restored. This verifies those write paths on this firmware, not persistence after a reboot or every possible setting value.
- **Physical pan and tilt both work.** A small pan command shifted a private snapshot horizontally about 40 pixels, and a small tilt command shifted it vertically about 11 pixels. Inverse commands returned the view within approximately two pixels. The snapshots were kept local; no camera frames are included here. Motor inputs are relative device units, not independently calibrated degrees. Home Assistant's four motor buttons were also exercised with inverse moves.
- The SD slot reported `stat="empty"`, `size=0`, and `used_size=0`. A consumer must not divide by zero or interpret this as 0% of a usable card. Raw storage size units remain unverified. Actual recording to storage was not tested without media.
- Home Assistant 2026.10.4 retrieved a valid 1920×1080 JPEG and generated HLS media from the local RTMP source; a frame from the resulting HLS segment decoded at 1920×1080.
- All 26 integration entities had healthy states, with the nonexistent storage-usage percentage omitted. Credential redaction and unload/reload reconnection passed. The final integration acceptance run passed 32 checks after correcting two integration issues: debounced setting read-back and the empty-slot percentage sensor. These fixes belong in the Home Assistant adapter, not the camera protocol library.

The test returned changed brightness and motor position to their starting values. Recording and audio settings were written with their existing values; recording was not deliberately interrupted and no talk audio was transmitted.

## Still unverified

Settings persistence across power cycles; broad setting-value combinations; storage maintenance; firmware updates; reboot/restore; password changes; pairing/external accessories; gateway/box operations; actual recording to media and recorded-video playback; other-model talk audio; RTSP; and compatibility with other models or firmware. Readable cruise/schedule/scene documents do not establish support for their associated actions.

The tests checked direct local operation. They did not establish that the camera firmware makes no independent external connections. The Windows application was used for identifying the device and reading connection details; library RPCs and media decoding targeted the local camera.

### Local motion events (2026-10-30)

- The f300 emitted a local `ccm_msg` item with `type: "alert"`,
  `code: "motion_alert"`, positive integer `msg_id`, device `sn`, Unix-seconds
  `date`, and `p: [{n: "msg_id", v: "..."}]`. Pan movement changed the view;
  physical movement and other models remain unverified. No clear-state event
  was observed. Device-info messages arrived on the same queue.
- Tested with global arming enabled and only the motion action enabled; IO,
  snapshot and recording outputs were disabled and read back before arming.
  Original alarm actions and global state were restored and verified afterward.
- Sending an action array only changed its first element on this firmware. The
  Windows UI sends a single action object, keyed by its token. The public list
  setter now issues one request per action, then sets global arming; it is not
  atomic and never retries writes.
- Both short empty polls and event delivery worked. Longer runs eventually
  hit an HTTP timeout with queue lifetimes of 30 and 300 seconds. The SDK surfaces
  the error; listeners must recreate their dedicated session/queue with backoff.

### Video quality profiles (2026-10-30)

The device advertises p0=HD1080p, p1=D1 and p2=CIF. Local H.264 frames decoded at
1920×1080 for p0 and 640×360 for p1 and p2. A 25-frame run confirmed stable sizes
for p0 and p2. The server sometimes returned a p2 URL for a p1 request; opening
streams rapidly could also fail transiently. Advertised labels and the Windows
client's static 1280×720/640×360/320×180/160×90 mapping are not reliable measurements.


## Android and speaker follow-up (2026-10-30)

The vendor-served Android MIPC APK was statically inspected. Local RTMP talk
publishing was tested with several codecs. An authorized, temporary microphone
loopback detected a transmitted AAC 1320 Hz tone strongly in the returned audio;
no ambient audio was saved, and microphone mute was restored. The resulting
optional sender uses mono 16 kHz AAC and supports interruptible uploads without a fixed duration cap. Packet
acceptance alone does not establish audible support for the other codecs. See
[Android findings](ANDROID.md) for exact provenance, new request shapes and the
talk-resource reservation behavior.

Read-only probes: `ccm_exsw_get` returns a boolean-like flag; `ccm_sleep_get` and
`ccm_crop_zoom_get` return HTTP 404 on this f300. `ccm_cap_get` did not return the
expected acknowledgement. Preset, voice-alarm, external-switch writes and sleep /
crop writes were not activated. These remain capability-gated protocol findings.
