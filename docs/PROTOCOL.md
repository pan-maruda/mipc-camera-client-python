# Client protocol inventory

Static analysis of the application installed at `C:\Users\bryle\MIPC` on 2026-10-29. No executable, plugin, script, cookies, debug logs, camera recordings, credentials, or account IDs are redistributed.

The combined catalogue contains 89 observed RPC names, including 80 device/queue RPCs. The Windows baseline below contains 81 names; [Android inspection](ANDROID.md) adds eight confirmed call sites and an alternate talk request field. All device RPCs are available through `client.call(name, **fields)` at the explicitly configured host. Account operations are documented for completeness and excluded from that interface. Login/DH use the pre-existing local authentication implementation.

## Evidence

Installed `MIPC.exe`: file/product version `1.0.0.1`, SHA-256 `4ee04e0b2fe97eccd2211cce19fe1c52f5239781d308fe829f22216b4c05c3ea`. The executable and cached bundles have different file dates; an application update does not establish that cached scripts are current. This inventory describes the files present during inspection, not a verified latest server-side client.

`python tools/inventory_client.py <client-directory>` reproduces cache hashes and lists candidate symbols without executing the app, reading cookies/logs, exporting raw cache content, or contacting a server. Candidate UI symbols still need call-site analysis before they become endpoints.

| Cache asset | Decompressed SHA-256 | Bytes |
| --- | --- | --- |
| `cache\f_000001` | `bb86ef6fdeeabfa6a0c21dd01828f96a4f8abefc41e33b18e0628a9a6cf34e11` | 1562786 |
| `cache\f_000007` | `02224ab249cc3f369e50948cb4bd80e676ad7cbe03a54fcb5f9720c92142f3e2` | 1729948 |
| `cache\f_00000b` | `526a2bc64138ddfbc2dedc8f313bc54ef963bb85d7e3c094ed88765ce25f322c` | 1690170 |

The installed native binary contains no additional confirmed `ccm_*` call sites. UI event names such as `ccm_media_get_request`, `ccm_disk_ctl_set`, and Wi-Fi `*_request` events are not independent wire endpoints. The web UI routes Wi-Fi configuration through `ccm_net_get/set`.

Offsets below count Unicode characters in the decompressed UTF-8 bundle. Their purpose is reproducible inspection, not a claim that a camera accepts the request. Multiple observed payload variants are unioned; optionality and response schemas vary by firmware.

## Endpoint coverage

| RPC | Scope | Observed top-level fields | First source / offset |
| --- | --- | --- | --- |
| `cacs_bind_req` | account | `email`, `lang`, `nid`, `p`, `pass`, `user` | `02224ab249cc` / 361068 |
| `cacs_check_nid_req` | authentication | `nid` | `02224ab249cc` / 847428 |
| `cacs_dh_req` | authentication | `bnum_prime`, `key_a2b`, `root_num`, `tid` | `02224ab249cc` / 358537 |
| `cacs_login_req` | authentication | `lid`, `nid`, `param`, `pass`, `session_req`, `user` | `02224ab249cc` / 810079 |
| `cacs_logout_req` | authentication | `nid` | `02224ab249cc` / 360786 |
| `cacs_passwd_req` | authentication | `guest`, `new_pass`, `nid`, `old_pass` | `02224ab249cc` / 360899 |
| `cacs_query_req` | account | `lid`, `nid`, `p`, `user` | `02224ab249cc` / 362749 |
| `cacs_recovery_req` | account | `email`, `lang`, `lid`, `nid`, `p`, `user` | `02224ab249cc` / 361474 |
| `cacs_reg_req` | account | `lid`, `nid`, `pass`, `session_req`, `user` | `02224ab249cc` / 360684 |
| `ccm_active` | device | `ActivationCode`, `sess` | `02224ab249cc` / 374627 |
| `ccm_alert_action_get` | device | `sess` | `02224ab249cc` / 370929 |
| `ccm_alert_action_set` | device | `actions`, `enable`, `sess` | `02224ab249cc` / 371129 |
| `ccm_alert_dev_get` | device | `sess` | `02224ab249cc` / 370395 |
| `ccm_alert_dev_set` | device | `conf`, `sess` | `02224ab249cc` / 370684 |
| `ccm_box_conf_get` | device | `sess` | `02224ab249cc` / 376317 |
| `ccm_box_get` | device | `end_time`, `flag`, `sess`, `sn`, `start_time` | `02224ab249cc` / 375882 |
| `ccm_box_login` | device | `enable`, `password`, `sess`, `username` | `02224ab249cc` / 376498 |
| `ccm_box_set` | device | `cmd`, `end_time`, `sess`, `sn`, `start_time` | `02224ab249cc` / 377053 |
| `ccm_curise_get` | device | `sess` | `02224ab249cc` / 374960 |
| `ccm_curise_set` | device | `index`, `sess`, `type` | `02224ab249cc` / 375165 |
| `ccm_date_get` | device | `sess` | `02224ab249cc` / 372171 |
| `ccm_date_set` | device | `daylight_savings`, `sess`, `timezone`, `type`, `utc_date` | `02224ab249cc` / 372492 |
| `ccm_dev_add` | device | `pwd`, `sess`, `sn` | `02224ab249cc` / 366524 |
| `ccm_dev_del` | device | `sess`, `sn` | `02224ab249cc` / 366394 |
| `ccm_dev_info_get` | device | `select`, `sess` | `02224ab249cc` / 367680 |
| `ccm_devs_get` | device | `counts`, `sess`, `start` | `02224ab249cc` / 364690 |
| `ccm_disk_ctl` | device | `conf`, `sess`, `token`, `type` | `02224ab249cc` / 370076 |
| `ccm_disk_get` | device | `sess` | `02224ab249cc` / 369780 |
| `ccm_exdev_add` | device | `id`, `interval`, `model`, `sess`, `timeout` | `02224ab249cc` / 378413 |
| `ccm_exdev_del` | device | `id`, `sess` | `02224ab249cc` / 363655 |
| `ccm_exdev_discover` | device | `flag`, `interval`, `sess`, `timeout` | `02224ab249cc` / 378219 |
| `ccm_exdev_get` | device | `counts`, `flag`, `sess`, `start` | `02224ab249cc` / 378623 |
| `ccm_hardware_test` | device | `exdev`, `sess` | `02224ab249cc` / 379263 |
| `ccm_hardware_test_get` | device | `sess` | `02224ab249cc` / 379385 |
| `ccm_img_get` | device | `sess`, `token` | `02224ab249cc` / 366716 |
| `ccm_img_set` | device | `conf`, `reset`, `sess`, `token` | `02224ab249cc` / 367216 |
| `ccm_info_get` | device |  | `02224ab249cc` / 374764 |
| `ccm_ipcs_get` | device | `sess` | `02224ab249cc` / 376678 |
| `ccm_mic_get` | device | `sess` | `02224ab249cc` / 373783 |
| `ccm_mic_set` | device | `conf`, `force_persistence`, `sess` | `02224ab249cc` / 374239 |
| `ccm_mics_get` | device | `sess` | `02224ab249cc` / 856938 |
| `ccm_misc_get` | device | `sess` | `02224ab249cc` / 366938 |
| `ccm_misc_set` | device | `info`, `sess` | `02224ab249cc` / 367428 |
| `ccm_motion_mask_get` | device | `sess` | `02224ab249cc` / 371283 |
| `ccm_motion_mask_set` | device | `conf`, `sess` | `02224ab249cc` / 371430 |
| `ccm_msg_filter_get` | device | `sess` | `02224ab249cc` / 375305 |
| `ccm_msg_filter_set` | device | `gen_filter`, `pub_filter`, `sess` | `02224ab249cc` / 375697 |
| `ccm_msg_get` | device | `counts`, `end_time`, `filter`, `flag`, `sess`, `start`, `start_time` | `02224ab249cc` / 366133 |
| `ccm_net_get` | device | `force_scan`, `items`, `select`, `sess`, `tokens` | `02224ab249cc` / 368745 |
| `ccm_net_set` | device | `info`, `sess` | `02224ab249cc` / 369026 |
| `ccm_nick_set` | device | `nick`, `sess` | `02224ab249cc` / 368359 |
| `ccm_ntp_get` | device | `sess` | `02224ab249cc` / 372020 |
| `ccm_ntp_set` | device | `auto_sync`, `dhcp`, `manual`, `sess` | `02224ab249cc` / 372689 |
| `ccm_osd_get` | device | `sess` | `02224ab249cc` / 369155 |
| `ccm_osd_set` | device | `osd`, `sess` | `02224ab249cc` / 369498 |
| `ccm_pic_get` | device | `flag`, `sess`, `token` | `02224ab249cc` / 376856 |
| `ccm_play` | device | `sess`, `setup`, `token` | `02224ab249cc` / 364887 |
| `ccm_ptz_ctl` | device | `sess`, `speed`, `token`, `trans` | `02224ab249cc` / 365768 |
| `ccm_pwd_set` | device | `sess`, `user` | `02224ab249cc` / 368561 |
| `ccm_reboot` | device | `sess` | `02224ab249cc` / 373561 |
| `ccm_record_task_get` | device | `sess` | `02224ab249cc` / 365088 |
| `ccm_record_task_set` | device | `sess`, `task` | `02224ab249cc` / 365220 |
| `ccm_replay` | device | `sess`, `setup`, `token` | `02224ab249cc` / 365932 |
| `ccm_restore` | device | `backup`, `sess` | `02224ab249cc` / 373431 |
| `ccm_scene_get` | device | `sess` | `02224ab249cc` / 378076 |
| `ccm_scene_set` | device | `all`, `info`, `sess` | `02224ab249cc` / 378801 |
| `ccm_schedule_get` | device | `sess` | `02224ab249cc` / 378964 |
| `ccm_schedule_set` | device | `sch`, `sess` | `02224ab249cc` / 379108 |
| `ccm_snapshot` | device | `sess`, `token` | `02224ab249cc` / 365404 |
| `ccm_speaker_get` | device | `sess`, `token` | `02224ab249cc` / 373672 |
| `ccm_speaker_set` | device | `conf`, `force_persistence`, `sess` | `02224ab249cc` / 373954 |
| `ccm_speakers_get` | device |  | `02224ab249cc` / 856486 |
| `ccm_subscribe` | device | `sess` | `02224ab249cc` / 359558 |
| `ccm_talk` | device | `sess`, `setup`, `token` | `02224ab249cc` / 365566 |
| `ccm_upgrade` | device | `img_src`, `sess` | `02224ab249cc` / 373309 |
| `ccm_upgrade_get` | device | `check`, `sess` | `02224ab249cc` / 372875 |
| `ccm_video_srcs_get` | device |  | `02224ab249cc` / 829058 |
| `ccm_zone_get` | device | `dev_sn`, `sess` | `02224ab249cc` / 377232 |
| `mmq_create` | device | `timeout` | `02224ab249cc` / 359472 |
| `mmq_destroy` | device | `qid` | `02224ab249cc` / 360397 |
| `mmq_pick` | device | `qid`, `timeout` | `02224ab249cc` / 359242 |

## Boundaries

Five catalog entries are local authentication operations (DH, login, logout, session check, password change); four are account registration/binding/query/recovery operations. Authentication has dedicated methods. `call()` excludes both categories so device inputs cannot replace authentication/session material.

* Client call-site evidence is not hardware validation. A later f300 read-only test verified a subset of operations; see [HARDWARE.md](HARDWARE.md). The inventory does not imply support for every endpoint on every device.
* Stream/playback/talk methods negotiate URLs only. RTMP/RTSP availability is firmware-dependent; no claim is made that every camera supports RTSP. Native plugin audio capture, playback, and clip export are not reimplemented. Optional `send_audio()` now provides bounded AAC encoding and local speaker publishing; see [Android/audio evidence](ANDROID.md). Event queues expose explicit synchronous polling, without a background listener.
* Cloud login/registration/recovery/binding/device discovery are not required for direct local access and are not implemented. Gateway/box/external-device endpoints still require compatible hardware at the configured host.
* Explicit NTP, firmware checks/downloads, alert actions and network settings can cause the camera itself to contact other hosts. The library cannot guarantee that firmware remains offline; use network rules if complete isolation is required.
* Firmware enum meanings and unobserved response fields are returned without guessed conversions. Advanced callers can use `call` with the catalog field names; convenience document updates preserve firmware extension fields.
* `ccm_pic_get` has both a JSON acknowledgement form (via `call`) and the existing JPEG response form (via `get_image`). Event queues use observed mmq_create/pick/destroy and ccm_subscribe calls. Their live delivery semantics still need hardware validation.
