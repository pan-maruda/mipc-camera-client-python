import logging
import math
import re
import threading
from typing import Literal, Union
from urllib.parse import urlsplit
from xml.etree import ElementTree

import json5
import requests

from .crypto_helpers import (
    des_encrypt_password_hash,
    dh_gen_private,
    dh_gen_public,
    dh_req_data,
    dh_shared_secret,
    format_nid,
    hash_password,
)
from .operations import OperationsMixin
from .settings import (
    MipcAuthenticationError,
    MipcError,
    MipcProtocolError,
    MipcTransportError,
    MipcUnsupportedError,
    SettingsMixin,
)
from .sync import synchronized

LOGGER = logging.getLogger(__name__)

JSONP_PREFIX = "message("

__all__ = [
    "MipcCameraClient",
    "MipcError",
    "MipcAuthenticationError",
    "MipcProtocolError",
    "MipcTransportError",
    "MipcUnsupportedError",
]


class MipcCameraClient(SettingsMixin, OperationsMixin):
    """HTTP Client for MIPC-compatible cameras."""

    _sn: Union[str, None]

    def __init__(self, host: str, timeout: float = 10) -> None:
        if not isinstance(host, str) or not host or re.search(r"[\s\\]", host):
            raise ValueError("Expected a hostname or IP address with optional port")
        endpoint = urlsplit(f"http://{host}")
        if (
            not endpoint.hostname
            or endpoint.username
            or endpoint.password
            or endpoint.path
            or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError("Expected a hostname or IP address with optional port")
        try:
            if endpoint.port == 0 or host.endswith(":"):
                raise ValueError("Invalid camera port")
        except ValueError as err:
            raise ValueError("Invalid camera port") from err
        if (
            not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("Timeout must be positive")
        self.timeout = timeout
        self._lock = threading.RLock()
        self.tid = 0
        self.sid = ""
        self.lid = ""
        self.seq = 0
        self._sn = None
        self.shared_secret = None
        self.host = host
        self.init_keys()
        self._r: requests.Session = requests.Session()
        # Prevent ambient proxies and .netrc credentials from changing routing.
        self._r.trust_env = False

    def __repr__(self) -> str:
        return f"MipcCameraClient(host={repr(self.host)})"

    def init_keys(self, priv_key=None) -> None:
        self.priv_key = priv_key or dh_gen_private()
        self.pub_key = dh_gen_public(self.priv_key)

    @synchronized
    def run_dh(self) -> None:
        dh_resp = self.run_rpc("cacs_dh_req", dh_req_data(self.pub_key, self.tid))

        try:
            if dh_resp.get("type") != "cacs_dh_ack":
                raise ValueError("Unexpected DH acknowledgement")
            self._handle_dh_ack(dh_resp["data"])
        except (KeyError, TypeError, ValueError):
            raise MipcProtocolError("cacs_dh_req") from None

    def _handle_dh_ack(self, resp_data) -> None:
        self.shared_secret = dh_shared_secret(resp_data["key_b2a"], self.priv_key)
        self.tid = resp_data["tid"]
        self.lid = resp_data["lid"]

    @synchronized
    def nid(self) -> str:
        return self._create_nid_ex(0)

    def _create_nid_ex(self, nid_type, incr_seq=True):
        if incr_seq:
            self.seq += 1
        return format_nid(
            self.seq,
            self.lid if nid_type > 0 else self.sid,
            str(self.shared_secret),
            nid_type,
            None,
            None,
        )

    def _login_data(self, username, password, incr_nid=True):
        data = {
            "dlid": self.lid,
            "dnid": self._create_nid_ex(2, incr_nid),
            "duser": username,
            "dpass": des_encrypt_password_hash(
                hash_password(password), self.shared_secret
            ),
            "dsession_req": 1,
            "dparam__x_countz_": 1,
            "dparam": 1,
            "dparam_name": "spv",
            "dparam_value": "v1",
        }

        return data

    def _handle_login_response(self, response_body):
        data = response_body.get("data")
        if not isinstance(data, dict):
            raise MipcProtocolError("cacs_login_req")
        if response_body.get("type") != "cacs_login_ack":
            raise MipcProtocolError("cacs_login_req")
        status = data.get("ret")
        code = status.get("code") if isinstance(status, dict) else data.get("result")
        if code != "":
            raise MipcAuthenticationError("cacs_login_req")
        if (
            not all(isinstance(data.get(k), str) and data[k] for k in ("sid", "lid"))
            or type(data.get("seq")) is not int
        ):
            raise MipcProtocolError("cacs_login_req")
        self.sid = data["sid"]
        self.seq = data["seq"]
        self.lid = data["lid"]
        self.client_addr = data.get("addr")

    @synchronized
    def run_rpc(self, msg_type, data, response_type="js", *, request_timeout=None):
        """Low-level request to this host only; data must already be flattened."""
        if not isinstance(msg_type, str) or not re.fullmatch(
            r"[a-z][a-z0-9_]*", msg_type
        ):
            raise ValueError("Invalid RPC name")
        if response_type not in ("js", "jpg", "jpeg", "bin"):
            raise ValueError("Invalid response type")
        timeout = self.timeout if request_timeout is None else request_timeout
        if (
            not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("Timeout must be positive and finite")
        query_params = data

        LOGGER.debug("MIPC RPC %s", msg_type)
        try:
            resp = self._r.request(
                method="GET",
                url=f"http://{self.host}/ccm/{msg_type}.{response_type}",
                params=query_params,
                timeout=timeout,
                allow_redirects=False,
            )
        except requests.Timeout:
            raise MipcTransportError(msg_type, "timeout") from None
        except requests.RequestException:
            # requests exceptions can contain credential-bearing query strings.
            raise MipcTransportError(msg_type, "connection_error") from None
        if resp.status_code in (404, 405, 501):
            raise MipcUnsupportedError(msg_type, resp.status_code)
        if resp.status_code in (401, 403):
            raise MipcAuthenticationError(msg_type, f"http_{resp.status_code}")
        if resp.status_code >= 400:
            raise MipcTransportError(msg_type, f"http_{resp.status_code}")
        if 300 <= resp.status_code < 400:
            raise MipcProtocolError(msg_type)
        if response_type == "js":
            parsed = MipcCameraClient._parse_jsonp(resp.text)
            return parsed
        else:
            return resp.content

    @classmethod
    def _parse_jsonp(cls, text: str) -> dict:
        text = text.strip()
        if not text.startswith(JSONP_PREFIX) or not text.endswith(");"):
            raise MipcProtocolError("jsonp")
        try:
            parsed = json5.loads(text[len(JSONP_PREFIX) : -2])
        except ValueError:
            raise MipcProtocolError("jsonp") from None
        if not isinstance(parsed, dict):
            raise MipcProtocolError("jsonp")
        return parsed

    @synchronized
    def login(self, username: str, password: str):
        """log in to the camera api and start a session"""
        self.sid = ""
        if not self.shared_secret:
            self.run_dh()
        login_data = self._login_data(username, password)
        login_response_json = self.run_rpc("cacs_login_req", login_data)
        return self._handle_login_response(login_response_json)

    @synchronized
    def get_image(self, token: str = "p0_xxxxxxxxxx") -> bytes:
        """gets a JPEG snapshot of what the camera sees now"""
        if not self.sid:
            raise MipcAuthenticationError("ccm_pic_get")
        image = self.run_rpc(
            "ccm_pic_get",
            data={
                "dsess": 1,
                "dsess_nid": self.nid(),
                "dsess_sn": self.get_device_sn(),
                "dtoken": token,
            },
            response_type="jpg",
        )
        if not isinstance(image, bytes) or not image.startswith(b"\xff\xd8"):
            # The f300 returns an XML error envelope from the JPEG endpoint.
            # Bound parsing and reject declarations that could expand entities.
            if (
                isinstance(image, bytes)
                and len(image) <= 65536
                and b"\x00" not in image
                and b"<!DOCTYPE" not in image.upper()
                and b"<!ENTITY" not in image.upper()
            ):
                try:
                    reply = ElementTree.fromstring(image)
                except (ElementTree.ParseError, LookupError, ValueError):
                    pass
                else:
                    status = reply.find("data/ccm_pic_get_ack/ret")
                    if reply.tag == "message" and status is not None:
                        self._checked_response(
                            "ccm_pic_get",
                            {
                                "type": reply.findtext("type"),
                                "data": {
                                    "ret": {
                                        "code": status.findtext("code"),
                                        "sub": status.findtext("sub"),
                                    }
                                },
                            },
                        )
            raise MipcProtocolError("ccm_pic_get")
        return image

    def get_rtmp_stream(self, token: Literal["p0", "p1", "p2", "p3"] = "p0"):
        """Get an RTMP URL at the configured camera host."""
        if token not in ("p0", "p1", "p2", "p3"):
            raise ValueError("Invalid stream token")
        return self.get_stream_url(token)

    @synchronized
    def close(self) -> None:
        """Release the owned HTTP session."""
        self._r.close()
        self.sid = ""
        self.shared_secret = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    @synchronized
    def get_device_sn(self) -> Union[str, None]:
        """gets the camera serial number (cached for the client lifetime)"""
        if not self._sn:
            sn = self.get_info().get("sn")
            if not isinstance(sn, str) or not sn:
                raise MipcProtocolError("ccm_info_get")
            self._sn = sn
        return self._sn

    @synchronized
    def control_ptz(self, tilt_x, tilt_y, speed_x=48, speed_y=16, token="ptz0"):
        """Relative pan/tilt command; units and limits depend on firmware."""
        self._range(tilt_x, -360, 360)
        self._range(tilt_y, -360, 360)
        self._range(speed_x, 1, 100)
        self._range(speed_y, 1, 100)
        return self._authenticated(
            "ccm_ptz_ctl",
            token=token,
            trans={"pan_tilt": {"x": tilt_x, "y": tilt_y}},
            speed={"pan_tilt": {"x": speed_x, "y": speed_y}},
        )
