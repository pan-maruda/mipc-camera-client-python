import logging
import pprint
from typing import Literal, Union

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

LOGGER = logging.getLogger(__name__)

JSONP_PREFIX = "message("

__all__ = ["MipcCameraClient"]


class MipcCameraClient:
    """HTTP Client for MIPC-compatible cameras."""

    _sn: Union[str, None]

    def __init__(self, host: str) -> None:
        self.tid = 0
        self.sid = ""
        self.lid = ""
        self.seq = 0
        self._sn = None
        self.shared_secret = None
        self.host = host
        self.init_keys()
        self._r: requests.Session = requests.Session()

    def __repr__(self) -> str:
        return f"MipcCameraClient(host={repr(self.host)})"

    def init_keys(self, priv_key=None) -> None:
        self.priv_key = priv_key or dh_gen_private()
        self.pub_key = dh_gen_public(self.priv_key)

    def run_dh(self) -> None:
        dh_resp = self.run_rpc("cacs_dh_req", dh_req_data(self.pub_key, self.tid))

        resp_data = dh_resp["data"]
        self._handle_dh_ack(resp_data)

    def _handle_dh_ack(self, resp_data) -> None:
        self.shared_secret = dh_shared_secret(resp_data["key_b2a"], self.priv_key)
        self.tid = resp_data["tid"]
        self.lid = resp_data["lid"]

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
        if (
            "data" not in response_body
            or "result" not in response_body["data"]
            or response_body["data"]["result"] != ""
        ):
            raise Exception(f"failed to login: [{response_body}]")
        data = response_body["data"]
        self.sid = data["sid"]
        self.seq = data["seq"]
        self.lid = data["lid"]
        self.client_addr = data["addr"]

    def run_rpc(self, msg_type, data, response_type="js"):
        query_params = data

        LOGGER.debug(
            f"{self.host=} {msg_type=} data={pprint.pformat(data, compact=True)}"
        )
        resp = self._r.request(
            method="GET",
            url=f"http://{self.host}/ccm/{msg_type}.{response_type}",
            params=query_params,
        )
        resp.raise_for_status()
        if response_type == "js":
            parsed = MipcCameraClient._parse_jsonp(resp.text)
            LOGGER.debug(
                f"{resp.request.url} {resp} {pprint.pformat(parsed, compact=True)}"
            )
            return parsed
        else:
            return resp.content

    @classmethod
    def _parse_jsonp(cls, text: str) -> any:
        unwrapped_es_obj = text.removeprefix(JSONP_PREFIX).removesuffix(");")
        return json5.loads(unwrapped_es_obj)

    def login(self, username: str, password: str):
        """log in to the camera api and start a session"""
        if not self.shared_secret:
            self.run_dh()
        login_data = self._login_data(username, password)
        login_response_json = self.run_rpc("cacs_login_req", login_data)
        LOGGER.debug(login_response_json)
        return self._handle_login_response(login_response_json)

    def get_image(self) -> bytes:
        """gets a JPEG snapshot of what the camera sees now"""
        return self.run_rpc(
            "ccm_pic_get",
            data={
                "dsess": 1,
                "dsess_nid": self.nid(),
                "dsess_sn": self.get_device_sn(),
                "dtoken": "p0_xxxxxxxxxx",  # (sic)
            },
            response_type="jpg",
        )

    def get_rtmp_stream(self, token: Literal["p0", "p1", "p2", "p3"] = "p0"):
        """gets the URL of the RTMP live stream from camera

        TODO: refactor quality selection"""
        resp = self.run_rpc(
            "ccm_play",
            {
                "dsess": 1,
                "dsess_nid": self.nid(),
                "dsess_sn": self.get_device_sn(),
                "dsetup": 1,
                "dsetup_stream": "RTP_Unicast",
                "dsetup_trans": 1,
                "dsetup_trans_proto": "rtmp",
                "dtoken": token,
            },
        )

        return resp["data"]["uri"]["url"]

    def get_device_sn(self) -> Union[str, None]:
        """gets the camera serial number (cached for the client lifetime)"""
        if not self._sn:
            api_result = self.run_rpc("ccm_info_get", data={})
            sn = api_result.get("data", dict()).get("sn")
            if not sn:
                # maybe this should be a ValueError?
                LOGGER.warn(
                    f"ccm_info_get did not contain a valid camera SN! response JSON was {api_result}"
                )
            self._sn = sn
        return self._sn

    def control_ptz(self, tilt_x, tilt_y, speed_x=48, speed_y=16):
        """
        move the camera by making the motors go brr

        TODO figure out the x, y ranges
        """
        ptz_data = {
            "dsess": 1,
            "dsess_nid": self.nid(),
            "dsess_sn": self.get_device_sn(),
            "dtoken": "ptz0",
            "dtrans": 1,
            "dtrans_pan_tilt": 1,
            "dtrans_pan_tilt_x": tilt_x,
            "dtrans_pan_tilt_y": tilt_y,
            "dtrans_pan_tilt_z": 0,
            "dspeed": 1,
            "dspeed_pan_tilt": 1,
            "dspeed_pan_tilt_x": speed_x,
            "dspeed_pan_tilt_y": speed_y,
            "ddome_cmd": 0,
        }
        resp = self.run_rpc("ccm_ptz_ctl", ptz_data)
        if not resp["type"] == "ccm_ptz_ctl_ack":
            LOGGER.warn(f"got unexpected response from camera: {resp}")
