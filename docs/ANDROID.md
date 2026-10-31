# Android client findings and local speaker audio

The supplied file named `uptodown-com.mining.app.mipca.apk` was identified from
its binary manifest as **com.uptodown 7.42**, not MIPC. It was not installed or
executed. The filename alone is not sufficient to identify an Android package.

An actual MIPC APK was subsequently retrieved through the public download flow
at <http://www.mipcm.com/download/> and its `ccvs_get_version_req` download lookup.
This is the version served by that download flow, not a claim of the newest
Google Play version:

- Package: `com.mining.app.mipca`
- Version: `v11.9.1.2409291120`, version code 293
- APK SHA-256: `20c66d333df411629bb2ed7ce572ddca80bb27bef0dff96f65c29d0b4222d8f8`
- Static inspection only; no APK or vendor native library is redistributed.

DEX call sites in `com.mining.cloud.mcld_agent` confirm the following additional
request shapes. The endpoint catalogue records the DEX hash, code offset and
method name. These are protocol evidence, not universal hardware capabilities.

| RPC | Non-session request fields | Finding on the tested f300 |
| --- | --- | --- |
| `ccm_exsw_get` / `set` | none / `enable` | Read succeeds with a boolean-like flag; physical meaning and writes unverified |
| `ccm_sleep_get` / `set` | none / `sleep_enable` | Read returns HTTP 404; no sleep/privacy control claimed |
| `ccm_crop_zoom_get` / `set` | `token` / `token`, `smooth_crop_zoom`, `crop_zoom_conf` (`x`, `y`, `width`, `height`) | Read returns HTTP 404; coordinate units unverified |
| `ccm_preset_pos_ctrl` | `cmd`, `infos` (`info` list containing `id`, `nick`) | Call site verified; commands and hardware behavior not tested |
| `ccm_audio_ctrl` | `cmd` | A separate voice-alarm control, not a speech upload; intentionally not activated |

String-only candidates also include cloud, segment, UART, box-search and network
test operations. Some names are callbacks or acknowledgements. They are not added
to the callable catalogue without confirmed request construction. `ccm_cap_get`
appears in multiple Android functions, but this f300 did not return the expected
acknowledgement; no guessed capability schema is exposed.

## Talk audio

The Windows client negotiates `ccm_talk`, then publishes microphone audio through
its native media engine. The Android client also negotiates `ccm_talk`, defaults
to RTDP, and constructs a microphone-to-destination channel. Its request omits the
Windows profile token and includes a field literally spelled **`slient`**, default
1. This spelling is preserved in the raw catalogue; it is not treated as a proven
general mute/stop API. Android's microphone wrapper defaults to 16 kHz capture.

Local RTMP publishing was investigated on the f300 without a cloud account.
Silent G.711 A-law, AAC and Nellymoser uploads accepted packets. A subsequent
authorized microphone-loopback test detected the transmitted **1320 Hz AAC** tone
strongly in the camera's returned microphone audio. AAC at 16 kHz mono is therefore
the implemented path. Packet acceptance alone is not treated as proof that other
codecs play correctly. Microphone mute was restored and no ambient audio saved.

`send_audio()` encodes caller-provided PCM16 little-endian, mono, 16 kHz bytes to
AAC and publishes FLV over RTMP using optional PyAV. It decodes and sends incrementally without a fixed duration cap,
paces transmission, supports a `threading.Event` cancellation signal, and closes
the publisher on completion or failure. It never changes microphone mute or
speaker volume. The camera's current speaker volume still determines audibility.

Negotiating a talk URL can reserve the camera's single talk resource before any
audio is sent. Abandoning the URL during exploration produced `Receiver` /
`ccm.system.err` on subsequent negotiations; publishing and closing the original
destination released it, and fresh negotiation worked again. Avoid probing talk
as an ordinary capability read. A network failure can prevent clean release; the
library reports the failure without silently retrying or rebooting the camera.

The library does not capture a computer microphone or provide browser two-way
WebRTC audio. Applications supply their own PCM bytes. Use a separately logged-in
client when controls or event polling must run while an upload is active.
