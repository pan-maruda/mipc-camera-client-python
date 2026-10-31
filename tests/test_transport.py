"""Real loopback HTTP tests: independent synthetic camera, no vendor network."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from mipc_camera_client import (
    MipcAuthenticationError,
    MipcCameraClient,
    MipcProtocolError,
    MipcTransportError,
    MipcUnsupportedError,
)
from mipc_camera_client.crypto_helpers import (
    des_encrypt_password_hash,
    dh_gen_public,
    dh_shared_secret,
    hash_password,
)


@pytest.fixture
def camera():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            parsed = urlsplit(self.path)
            method, extension = parsed.path.rsplit("/", 1)[1].rsplit(".", 1)
            query = {
                k: v[0]
                for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
            }
            server.calls.append((method, query))
            if server.http_status != 200:
                self.send_response(server.http_status)
                self.end_headers()
                return
            if server.redirect:
                self.send_response(302)
                self.send_header("Location", "http://must-not-contact.invalid/")
                self.end_headers()
                return
            data = {"ret": {"code": ""}}
            if method == "cacs_dh_req":
                server.shared = dh_shared_secret(query["dkey_a2b"], 12345)
                data = {"key_b2a": str(dh_gen_public(12345)), "tid": 1, "lid": "0x12"}
            elif method == "cacs_login_req":
                expected = des_encrypt_password_hash(
                    hash_password("synthetic-password"), server.shared
                )
                if query.get("dpass") != expected:
                    data = {"result": "permission.denied"}
                else:
                    data = {
                        "result": "",
                        "sid": "0x34",
                        "lid": "0x12",
                        "seq": 100,
                        "addr": "127.0.0.1",
                    }
            elif method == "ccm_info_get":
                data["sn"] = "synthetic-camera"
            elif method == "ccm_mic_get":
                data["conf"] = [
                    {
                        "entity": "audio",
                        "token": "mic0",
                        "silent": 0,
                        "level": server.level,
                    }
                ]
            elif method == "ccm_mic_set":
                server.level = int(query["dconf_level"])
            elif method == "ccm_misc_get":
                data["info"] = {"flip": 0, "power_freq": 0}
            elif method == "ccm_play":
                data["uri"] = {"url": "rtmp://127.0.0.1:1935/live"}
            if extension == "jpg":
                payload = b"\xff\xd8synthetic-jpeg\xff\xd9"
            else:
                response = {"type": method.removesuffix("_req") + "_ack", "data": data}
                payload = ("message(" + json.dumps(response) + ");").encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.calls = []
    server.level = 20
    server.redirect = False
    server.http_status = 200
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.host = f"127.0.0.1:{server.server_port}"
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def test_end_to_end_local_login_read_write_media_and_logout(camera, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://must-not-contact.invalid:80")
    with MipcCameraClient(camera.host) as client:
        assert client._r.trust_env is False
        client.login("admin", "synthetic-password")
        assert client.get_device_sn() == "synthetic-camera"
        assert client.get_microphones()[0]["level"] == 20
        client.set_microphone_level(37)
        assert client.get_microphones()[0]["level"] == 37
        assert client.get_image().startswith(b"\xff\xd8")
        assert client.get_rtmp_stream() == "rtmp://127.0.0.1:1935/live"
        client.logout()
        assert client.sid == ""
    assert [m for m, _ in camera.calls[:2]] == ["cacs_dh_req", "cacs_login_req"]
    assert all(
        "dpass" not in q or q["dpass"] != "synthetic-password" for _, q in camera.calls
    )


def test_login_failure_is_classified_and_does_not_retry(camera):
    with MipcCameraClient(camera.host) as client:
        with pytest.raises(MipcAuthenticationError):
            client.login("admin", "wrong-password")
        assert not client.sid
    assert len(camera.calls) == 2


def test_redirects_are_never_followed(camera):
    camera.redirect = True
    with MipcCameraClient(camera.host) as client:
        with pytest.raises(MipcProtocolError):
            client.get_info()
    assert len(camera.calls) == 1


@pytest.mark.parametrize(
    "status,exception",
    [
        (404, MipcUnsupportedError),
        (405, MipcUnsupportedError),
        (501, MipcUnsupportedError),
        (401, MipcAuthenticationError),
        (403, MipcAuthenticationError),
        (500, MipcTransportError),
        (503, MipcTransportError),
    ],
)
def test_http_failures_are_classified_without_retries(camera, status, exception):
    camera.http_status = status
    with MipcCameraClient(camera.host) as client:
        with pytest.raises(exception) as error:
            client.get_info()
    assert error.value.code == f"http_{status}"
    assert len(camera.calls) == 1


def test_concurrent_requests_have_distinct_session_nonces(camera):
    with MipcCameraClient(camera.host) as client:
        client.login("admin", "synthetic-password")
        with ThreadPoolExecutor(max_workers=6) as pool:
            values = list(pool.map(lambda _: client.get_misc(), range(18)))
        assert all(v["flip"] == 0 for v in values)
        assert client.seq == 118
    nids = [q["dsess_nid"] for method, q in camera.calls if method == "ccm_misc_get"]
    assert len(nids) == len(set(nids)) == 18


def test_transport_exception_never_exposes_query_or_cause():
    with MipcCameraClient("127.0.0.1") as client:

        def fail(**kwargs):
            raise requests.ConnectionError("http://camera/ccm/test?dpass=secret")

        client._r.request = fail
        with pytest.raises(MipcTransportError) as error:
            client.run_rpc("test", {"dpass": "secret"})
        assert "secret" not in str(error.value)
        assert error.value.__suppress_context__ is True


@pytest.mark.parametrize(
    "name", ["../ccm_reboot", "https://vendor.invalid", "a/b", "a?b"]
)
def test_low_level_rpc_cannot_change_origin_or_path(name):
    with MipcCameraClient("127.0.0.1") as client:
        with pytest.raises(ValueError):
            client.run_rpc(name, {})
