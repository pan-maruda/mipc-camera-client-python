"""Data-only discovery of live stream profiles advertised by the camera."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StreamProfile:
    """A playback token and its firmware-reported quality name."""

    token: str
    name: str
    width: int | None = None
    height: int | None = None


def stream_profiles(info: Any) -> list[StreamProfile]:
    """Ignore unknown properties and ambiguous or malformed profile declarations."""
    if not isinstance(info, dict) or not isinstance(info.get("p"), list):
        return []
    found: dict[str, str] = {}
    rejected: set[str] = set()
    for item in info["p"]:
        if not isinstance(item, dict):
            continue
        token, name = item.get("n"), item.get("v")
        if not isinstance(token, str) or token not in ("p0", "p1", "p2", "p3"):
            continue
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            rejected.add(token)
            continue
        name = name.strip()
        if token in found and found[token] != name:
            rejected.add(token)
        found[token] = name
    return [
        StreamProfile(token, found[token])
        for token in sorted(found)
        if token not in rejected
    ]
