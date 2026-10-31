from types import SimpleNamespace
from unittest.mock import Mock

from mipc_camera_client import cli


def test_offline_endpoint_catalog_needs_no_credentials(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["mipc_camera_client", "endpoints", "ccm_osd_set"])
    monkeypatch.delenv("CAMERA_PASSWORD", raising=False)
    monkeypatch.setattr(
        cli, "MipcCameraClient", Mock(side_effect=AssertionError("must stay offline"))
    )
    cli.main()
    assert '"osd"' in capsys.readouterr().out


def test_snapshot_explicit_file_is_not_treated_as_directory(tmp_path):
    client = SimpleNamespace(
        get_image=lambda: b"jpeg", get_device_sn=lambda: "synthetic"
    )
    target = tmp_path / "image.jpg"
    cli.snapshot(client, str(target))
    assert target.read_bytes() == b"jpeg"


def test_snapshot_directory_sanitizes_camera_serial(tmp_path):
    client = SimpleNamespace(
        get_image=lambda: b"jpeg", get_device_sn=lambda: "../../bad/serial"
    )
    cli.snapshot(client, str(tmp_path))
    assert len(list(tmp_path.glob("*.jpeg"))) == 1


def test_snapshot_without_filename_uses_pipe(monkeypatch):
    client = SimpleNamespace(get_image=lambda: b"jpeg")
    writer = Mock()
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr(cli, "_write_bytes_stdout", writer)
    cli.snapshot(client, None)
    writer.assert_called_once_with(b"jpeg")
