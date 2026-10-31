"""Explicit synchronous access to the camera's local message queue."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .settings import MipcError, MipcProtocolError

if TYPE_CHECKING:
    from . import MipcCameraClient


@dataclass(frozen=True)
class MotionEvent:
    """A camera's local alert pulse, not an occupancy or motion-clear state.

    This schema was observed on an f300. Other event types/codes and malformed
    items are ignored. The device serial is deliberately excluded from repr.
    """

    serial_number: str = field(repr=False)
    message_id: int
    timestamp: int

    @classmethod
    def from_message(cls, item: Any) -> MotionEvent | None:
        if not isinstance(item, dict) or (item.get("type"), item.get("code")) != (
            "alert",
            "motion_alert",
        ):
            return None
        serial, message_id, timestamp = (
            item.get("sn"),
            item.get("msg_id"),
            item.get("date"),
        )
        if (
            not isinstance(serial, str)
            or not serial
            or type(message_id) is not int
            or message_id <= 0
            or type(timestamp) is not int
            or timestamp <= 0
        ):
            return None
        return cls(serial, message_id, timestamp)


def queue_message(response: Any) -> dict:
    if not isinstance(response, dict) or not isinstance(response.get("data"), dict):
        raise MipcProtocolError("mmq_pick")
    data = response["data"]
    if response.get("type") == "ccm_msg":
        items = data.get("items")
        if not isinstance(items, list) or not all(
            isinstance(item, dict) for item in items
        ):
            raise MipcProtocolError("mmq_pick")
        return data
    if response.get("type") == "mmq_pick_ack":
        if data.get("result") != "":
            raise MipcError("mmq_pick")
        return {**data, "items": []}
    raise MipcProtocolError("mmq_pick")


class EventQueue:
    """Poll blocks this client; use a separate logged-in client for other control.

    No thread is started and failed requests are never silently retried.
    """

    def __init__(self, client: MipcCameraClient, lifetime: int = 30) -> None:
        client._range(lifetime, 1, 300)
        self._client = client
        self._qid = None
        with client._lock:
            if not client.sid:
                raise MipcProtocolError("mmq_create")
            data = client.call("mmq_create", timeout=lifetime * 1000)
            qid = data.get("qid")
            if type(qid) not in (str, int) or qid == "":
                raise MipcProtocolError("mmq_create")
            self._qid = qid
            try:
                client._authenticated("ccm_subscribe", _queue_id=qid)
            except Exception:
                try:
                    self.close()
                except MipcError:
                    pass
                raise

    def poll(self, timeout: int = 5) -> list[dict[str, Any]]:
        """Wait up to timeout seconds (wire units are milliseconds)."""
        self._client._range(timeout, 1, 300)
        with self._client._lock:
            if self._qid is None:
                raise ValueError("Event queue is closed")
            response = self._client.run_rpc(
                "mmq_pick",
                {"dqid": self._qid, "dtimeout": timeout * 1000, "hqid": self._qid},
                request_timeout=timeout + 2,
            )
            return queue_message(response)["items"]

    def close(self) -> None:
        with self._client._lock:
            if self._qid is not None:
                qid, self._qid = self._qid, None
                self._client._checked("mmq_destroy", {"dqid": qid, "hqid": qid})

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.close()
        else:
            try:
                self.close()
            except MipcError:
                pass
