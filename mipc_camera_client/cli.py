import argparse
import datetime
import inspect
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from mipc_camera_client import MipcCameraClient


def print_info(c: MipcCameraClient) -> None:
    print(json.dumps(c.get_info(), indent=2))


def print_settings(c: MipcCameraClient, section: str) -> None:
    from .capabilities import READ_PROBES

    print(json.dumps(getattr(c, READ_PROBES[section])(), indent=2))


def print_probe(c: MipcCameraClient) -> None:
    report = c.probe_capabilities()
    print(
        json.dumps(
            {"readable": sorted(report.readable), "rejected": report.rejected}, indent=2
        )
    )


def call_rpc(c: MipcCameraClient, method: str, data_file: str | None) -> None:
    payload = {}
    if data_file:
        text = (
            sys.stdin.read()
            if data_file == "-"
            else Path(data_file).read_text(encoding="utf-8")
        )
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("RPC input must be a JSON object")
    print(json.dumps(c.call(method, **payload), indent=2))


def print_endpoints(c=None, method: str | None = None) -> None:
    from .catalog import ENDPOINTS

    if method is not None:
        if method not in ENDPOINTS:
            raise ValueError("Unknown endpoint")
        print(json.dumps(ENDPOINTS[method], indent=2))
    else:
        for name, entry in ENDPOINTS.items():
            print(f"{name} ({entry['scope']})")


LOGGER = logging.getLogger("mipc_camera_client")


def print_stream_url(c: MipcCameraClient) -> None:
    LOGGER.info("Getting RTMP stream URL")
    print(c.get_rtmp_stream())


def _write_bytes_stdout(bs: bytes):
    with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as fd:
        fd.write(bs)
        fd.flush()


def _generate_filename(c: MipcCameraClient):
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = now.strftime("%Y-%m-%dT%H-%M-%S.%f%Z")
    serial = re.sub(r"[^A-Za-z0-9._-]", "_", c.get_device_sn() or "camera")[:128]
    return f"{timestamp_str}_{serial}.jpeg"


def snapshot(c: MipcCameraClient, filename: Optional[str]) -> None:
    LOGGER.info("Taking snapshot")
    jpeg = c.get_image()
    out_path = None
    match filename:
        case "-":
            _write_bytes_stdout(jpeg)
        case None if not sys.stdout.isatty():
            _write_bytes_stdout(jpeg)
        case None:
            out_path = Path(_generate_filename(c))
        case dir if Path(dir).is_dir():
            out_path = Path(dir) / _generate_filename(c)
        case file:
            out_path = Path(file)
    if out_path:
        out_path.write_bytes(jpeg)
    LOGGER.info(f"saved {len(jpeg)} bytes to {out_path or 'stdout'}")
    if out_path:
        print(out_path)


def ptz_handler(
    c: MipcCameraClient, x: int, y: int, zero: bool, speed_x: int, speed_y: int
) -> None:
    if zero:
        LOGGER.info("resetting pan/tilt position")
        c.control_ptz(tilt_x=-360, tilt_y=-360, speed_x=speed_x, speed_y=speed_y)
    else:
        LOGGER.info(f"moving {x=} {y=}")
        c.control_ptz(tilt_x=x, tilt_y=y, speed_x=speed_x, speed_y=speed_y)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLI client for MIPC cameras")
    parser.add_argument(
        "--host",
        default=os.getenv("CAMERA_HOST"),
        help="Camera address (hostname or IP), uses CAMERA_HOST env var if not supplied",
    )
    parser.add_argument(
        "--user",
        default=os.getenv("CAMERA_USER"),
        help="Camera username (from the web interface), uses CAMERA_USER env var if not supplied. Set CAMERA_PASSWORD for password.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Silence all output except for the snapshot filename or stream URL",
    )
    subparsers = parser.add_subparsers(
        title="commands",
        description="Available commands",
        required=True,
    )
    snap_parser = subparsers.add_parser(
        "snapshot",
        help="take a JPEG snapshot",
    )
    snap_parser.set_defaults(handler=snapshot)
    snap_parser.add_argument(
        "filename",
        nargs="?",
        help="path to save to (use - for stdout or leave empty when piping)",
    )

    stream_parser = subparsers.add_parser(
        "stream",
        help="get RTMP stream URL",
    )
    stream_parser.set_defaults(handler=print_stream_url)

    ptz_parser = subparsers.add_parser("ptz", help="control relative pan/tilt")

    ptz_parser.add_argument("--x", type=int, help="X movement (relative)", default=0)
    ptz_parser.add_argument("--y", type=int, help="Y movement (relative)", default=0)
    ptz_parser.add_argument(
        "--zero",
        "--home",
        action="store_true",
        help="reset the camera to 'zero' position or leftmost extreme",
    )
    ptz_parser.add_argument(
        "--speed-x", type=int, help="X movement (relative)", default=80
    )
    ptz_parser.add_argument(
        "--speed-y", type=int, help="Y movement (relative)", default=50
    )
    # --x=300 --y=80

    ptz_parser.set_defaults(handler=ptz_handler)

    subparsers.add_parser("info", help="read basic device identity").set_defaults(
        handler=print_info
    )
    subparsers.add_parser(
        "probe", help="explicitly probe read capabilities without writes"
    ).set_defaults(handler=print_probe)
    from .capabilities import READ_PROBES

    read_parser = subparsers.add_parser("read", help="read a settings document")
    read_parser.add_argument("section", choices=sorted(READ_PROBES))
    read_parser.set_defaults(handler=print_settings)
    rpc_parser = subparsers.add_parser(
        "rpc", help="explicit local device RPC; writes execute immediately"
    )
    rpc_parser.add_argument("method")
    rpc_parser.add_argument("--data-file", help="JSON payload file, or - for stdin")
    rpc_parser.set_defaults(handler=call_rpc)
    catalog_parser = subparsers.add_parser(
        "endpoints", help="offline endpoint catalog; no login required"
    )
    catalog_parser.add_argument("method", nargs="?")
    catalog_parser.set_defaults(handler=print_endpoints)

    return parser.parse_args()


def _run_handler(args: argparse.Namespace, c: MipcCameraClient):
    # sorry
    handler_arg_names = inspect.getfullargspec(args.handler).args
    args_dict = vars(args)
    handler_args = {
        name: args_dict[name] for name in handler_arg_names if name not in ("c")
    }
    args.handler(c, **handler_args)


def main():
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
        level="INFO",
    )
    args = parse_args()
    if args.quiet:
        logging.getLogger().setLevel(logging.CRITICAL)
    if args.handler is print_endpoints:
        print_endpoints(method=args.method)
        return
    if "CAMERA_PASSWORD" not in os.environ:
        print("Error: environment variable CAMERA_PASSWORD not set", file=sys.stderr)
        sys.exit(2)
    if not args.host or not args.user:
        print(
            "Error: set CAMERA_HOST and CAMERA_USER or use --host and --user",
            file=sys.stderr,
        )
        sys.exit(2)
    LOGGER.info("Logging into camera")
    with MipcCameraClient(args.host) as c:
        c.login(args.user, os.environ["CAMERA_PASSWORD"])
        _run_handler(args, c)


if __name__ == "__main__":
    main()
