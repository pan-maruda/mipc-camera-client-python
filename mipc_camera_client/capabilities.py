"""Explicit, read-only probes; success is evidence of readability only."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityReport:
    readable: frozenset[str]
    rejected: dict[str, str]


# Deliberately excludes network scans, discovery/pairing, active firmware
# checks, subscriptions, and media-session creation.
READ_PROBES = {
    "device_info": "get_device_info",
    "microphones": "get_microphones",
    "speaker": "get_speaker",
    "imaging": "get_imaging",
    "misc": "get_misc",
    "osd": "get_osd",
    "alerts": "get_alert_config",
    "alert_actions": "get_alert_actions",
    "recording": "get_recording",
    "disks": "get_disks",
    "video_sources": "get_video_sources",
    "ntp": "get_ntp",
    "date": "get_date",
    "cruise": "get_cruise",
    "scenes": "get_scenes",
    "schedule": "get_schedule",
}
