"""Real AAC encode/decode in memory, cancellation and private-error handling."""

import builtins
import math
import struct
import threading
from io import BytesIO
from unittest.mock import Mock

import pytest

from mipc_camera_client import MipcCameraClient, MipcTransportError
from mipc_camera_client.audio import AudioSendResult


@pytest.fixture
def camera():
    client = MipcCameraClient("192.0.2.10")
    client.get_talk_url = Mock(return_value="rtmp://192.0.2.10/private?token=secret")
    yield client
    client.close()


@pytest.mark.parametrize(
    "pcm,kwargs",
    [
        (b"", {}),
        (b"x", {}),
        (bytearray(10), {}),
        (bytes(10), {"token": ""}),
        (bytes(10), {"timeout": True}),
        (bytes(10), {"timeout": float("nan")}),
        (bytes(10), {"timeout": 0}),
        (bytes(10), {"timeout": 31}),
        (bytes(10), {"stop_event": object()}),
    ],
)
def test_bad_input_has_no_media_side_effects(camera, pcm, kwargs):
    with pytest.raises(ValueError):
        camera.send_audio(pcm, **kwargs)
    camera.get_talk_url.assert_not_called()


def test_audio_extra_is_optional_and_missing_dependency_is_actionable(
    camera, monkeypatch
):
    original = builtins.__import__

    def without_av(name, *args, **kwargs):
        if name == "av":
            raise ImportError("not installed")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_av)
    with pytest.raises(ImportError, match=r"\[audio\]"):
        camera.send_audio(bytes(320))
    camera.get_talk_url.assert_not_called()


def test_pre_cancelled_upload_never_reserves_talk(camera):
    stop = threading.Event()
    stop.set()
    assert camera.send_audio(bytes(320), stop_event=stop) == AudioSendResult(
        0, cancelled=True
    )
    camera.get_talk_url.assert_not_called()


def test_real_aac_packets_decode_as_mono_16khz_without_network(camera, monkeypatch):
    av = pytest.importorskip("av")
    original = av.open

    class RetainedBuffer(BytesIO):
        def close(self):
            pass

    buffer = RetainedBuffer()
    calls = []

    def local_output(url, **kwargs):
        calls.append(kwargs)
        return original(buffer, **kwargs)

    monkeypatch.setattr(av, "open", local_output)
    sleep = Mock()
    monkeypatch.setattr("mipc_camera_client.audio.time.sleep", sleep)
    pcm = b"".join(
        struct.pack("<h", int(1000 * math.sin(2 * math.pi * 1000 * n / 16000)))
        for n in range(16003)
    )
    result = camera.send_audio(pcm, timeout=4)
    assert result.samples_sent == 16003 and not result.cancelled
    assert result.duration == 16003 / 16000
    camera.get_talk_url.assert_called_once_with("p0")
    assert calls[0]["timeout"] == (4, 4)
    assert calls[0]["options"]["rw_timeout"] == "4000000"
    assert sleep.call_count == 52
    with original(BytesIO(buffer.getvalue())) as source:
        audio = source.streams.audio[0]
        assert audio.codec_context.name == "aac"
        assert audio.codec_context.sample_rate == 16000
        assert len(audio.codec_context.layout.channels) == 1
        assert sum(f.samples for f in source.decode(audio)) >= 16003


def test_transport_failures_do_not_expose_private_urls_or_retry(camera, monkeypatch):
    av = pytest.importorskip("av")
    output = Mock(side_effect=OSError("rtmp://private?password=secret"))
    monkeypatch.setattr(av, "open", output)
    with pytest.raises(MipcTransportError) as raised:
        camera.send_audio(bytes(640))
    assert raised.value.code == "audio_transport_failed"
    assert raised.value.__suppress_context__
    assert "secret" not in str(raised.value)
    camera.get_talk_url.assert_called_once()
    output.assert_called_once()


def test_cancellation_closes_the_real_encoder_early(camera, monkeypatch):
    av = pytest.importorskip("av")
    original = av.open
    stop = threading.Event()
    closed = []

    class Output:
        def __enter__(self):
            self.output = original(BytesIO(), mode="w", format="flv")
            return self

        def __exit__(self, *args):
            self.output.close()
            closed.append(True)

        def add_stream(self, *args, **kwargs):
            return self.output.add_stream(*args, **kwargs)

        def mux(self, packet):
            self.output.mux(packet)
            stop.set()

    monkeypatch.setattr(av, "open", lambda *args, **kwargs: Output())
    monkeypatch.setattr("mipc_camera_client.audio.time.sleep", lambda *_: None)
    result = camera.send_audio(bytes(32000), stop_event=stop)
    assert result.cancelled and 0 < result.samples_sent < 16000
    assert closed == [True]


def test_upload_over_thirty_seconds_has_no_duration_cap(camera, monkeypatch):
    av = pytest.importorskip("av")
    original = av.open
    monkeypatch.setattr(
        av, "open", lambda *args, **kwargs: original(BytesIO(), mode="w", format="flv")
    )
    monkeypatch.setattr("mipc_camera_client.audio.time.sleep", lambda *_: None)
    result = camera.send_audio(bytes(31 * 32000))
    assert result.duration == 31 and not result.cancelled


def test_streaming_producer_is_closed_on_stop(camera, monkeypatch):
    av = pytest.importorskip("av")
    original = av.open
    stop = threading.Event()
    closed = []

    def source():
        try:
            while True:
                yield bytes(640)
        finally:
            closed.append(True)

    class Output:
        def __enter__(self):
            self.output = original(BytesIO(), mode="w", format="flv")
            return self

        def __exit__(self, *args):
            self.output.close()

        def add_stream(self, *args, **kwargs):
            return self.output.add_stream(*args, **kwargs)

        def mux(self, packet):
            self.output.mux(packet)
            stop.set()

    monkeypatch.setattr(av, "open", lambda *args, **kwargs: Output())
    monkeypatch.setattr("mipc_camera_client.audio.time.sleep", lambda *_: None)
    result = camera.send_audio(source(), stop_event=stop)
    assert result.cancelled and closed == [True]
