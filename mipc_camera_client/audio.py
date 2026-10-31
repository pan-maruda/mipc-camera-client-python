"""Interruptible local AAC talk uploads; PyAV is an optional dependency."""

from __future__ import annotations

import math
import time
from collections.abc import Iterable
from contextlib import closing
from dataclasses import dataclass
from fractions import Fraction
from itertools import chain
from threading import Event
from typing import TYPE_CHECKING

from .settings import MipcError, MipcTransportError

if TYPE_CHECKING:
    from . import MipcCameraClient

SAMPLE_RATE = 16000
FRAME_SAMPLES = 320


@dataclass(frozen=True)
class AudioSendResult:
    """Transport completion, not a guarantee of audible playback on all models."""

    samples_sent: int
    sample_rate: int = SAMPLE_RATE
    cancelled: bool = False

    @property
    def duration(self) -> float:
        return self.samples_sent / self.sample_rate


def pcm_frames(pcm, stop):
    """Yield small aligned chunks and close a streaming decoder on stop/error."""
    source = iter((pcm,)) if isinstance(pcm, bytes) else iter(pcm)
    try:
        for chunk in source:
            if stop is not None and stop.is_set():
                return
            if not isinstance(chunk, bytes) or len(chunk) % 2:
                raise ValueError("Expected complete PCM16 byte samples")
            for offset in range(0, len(chunk), FRAME_SAMPLES * 2):
                if stop is not None and stop.is_set():
                    return
                yield chunk[offset : offset + FRAME_SAMPLES * 2]
    finally:
        close = getattr(source, "close", None)
        if close:
            close()


def send_pcm(
    client: MipcCameraClient,
    pcm: bytes | Iterable[bytes],
    token: str,
    timeout: float,
    stop_event: Event | None = None,
) -> AudioSendResult:
    """Publish signed little-endian PCM16, mono, 16 kHz to the local speaker.

    This synchronous operation holds this client's lock; use a separate client
    for concurrent reads. Bytes or an iterable of PCM chunks are paced in real time.
    There is no duration cap. Streaming producers must themselves be interruptible.
    It never unmutes a microphone, changes volume, retries, or opens input URLs.
    """
    if isinstance(pcm, bytes):
        if not pcm or len(pcm) % 2:
            raise ValueError("Expected nonempty PCM16 bytes with complete samples")
    elif isinstance(pcm, (str, bytearray)) or not isinstance(pcm, Iterable):
        raise ValueError("Expected PCM16 bytes or an iterable of byte chunks")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("Expected a camera profile token")
    if (
        type(timeout) not in (int, float)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 30
    ):
        raise ValueError("Expected a timeout greater than zero and at most 30 seconds")
    if stop_event is not None and not isinstance(stop_event, Event):
        raise ValueError("Expected a threading.Event")
    if stop_event is not None and stop_event.is_set():
        return AudioSendResult(0, cancelled=True)
    try:
        import av
    except ImportError:
        raise ImportError(
            "Install this library with its [audio] extra to send audio"
        ) from None

    with (
        client._lock,
        av.logging.Capture(local=True),
        closing(pcm_frames(pcm, stop_event)) as chunks,
    ):
        try:
            # Check the encoder before reserving the camera's single talk slot.
            codec = av.codec.Codec("aac", "w")
            resampler = av.AudioResampler(
                format=codec.audio_formats[0].name, layout="mono", rate=SAMPLE_RATE
            )
            first = next(chunks, None)
            if first is None:
                if stop_event is not None and stop_event.is_set():
                    return AudioSendResult(0, cancelled=True)
                raise ValueError("Audio has no samples")
            # get_talk_url enforces the configured camera host. Remote URLs are
            # never opted into by this higher-level operation.
            url = client.get_talk_url(token)
            with av.open(
                url,
                mode="w",
                format="flv",
                timeout=(timeout, timeout),
                options={
                    "flvflags": "no_duration_filesize",
                    "rw_timeout": str(int(timeout * 1_000_000)),
                },
            ) as output:
                stream = output.add_stream("aac", rate=SAMPLE_RATE)
                stream.layout = "mono"
                stream.bit_rate = 32000
                started = time.monotonic()
                samples = 0
                for data in chain((first,), chunks):
                    if stop_event is not None and stop_event.is_set():
                        break
                    frame = av.AudioFrame(
                        format="s16", layout="mono", samples=len(data) // 2
                    )
                    frame.sample_rate = SAMPLE_RATE
                    frame.time_base = Fraction(1, SAMPLE_RATE)
                    frame.pts = samples
                    frame.planes[0].update(
                        data + bytes(frame.planes[0].buffer_size - len(data))
                    )
                    for converted in resampler.resample(frame):
                        for packet in stream.encode(converted):
                            output.mux(packet)
                    samples += frame.samples
                    time.sleep(
                        max(0, started + samples / SAMPLE_RATE - time.monotonic())
                    )
                for frame in resampler.resample(None):
                    for packet in stream.encode(frame):
                        output.mux(packet)
                for packet in stream.encode(None):
                    output.mux(packet)
            # This f300 needs a short server-side cleanup interval before the
            # next negotiation; do not retry an audio upload to work around it.
            time.sleep(1)
            return AudioSendResult(
                samples, cancelled=stop_event is not None and stop_event.is_set()
            )
        except MipcError:
            raise
        except Exception:
            # FFmpeg errors can include the private negotiated URL. Do not expose
            # those messages, logs or exception chains to a caller.
            raise MipcTransportError("send_audio", "audio_transport_failed") from None
