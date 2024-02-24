import argparse
import datetime
import logging
import os
from pathlib import Path
import sys
from typing import Optional
from mipc_camera_client import MipcCameraClient
import inspect

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
    return f"{timestamp_str}_{c.get_device_sn()}.jpeg"


def snapshot(c: MipcCameraClient, filename: Optional[str]) -> None:
    LOGGER.info("Taking snapshot")
    jpeg = c.get_image()
    out_path = None
    match filename:
        case "-":
            _write_bytes_stdout(jpeg)
        case None if not sys.stdout.isatty:
            _write_bytes_stdout(jpeg)
        case None:
            out_path = Path(_generate_filename(c))
        case dir if Path(dir).is_dir:
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
        help="Silence all output except for the snapshot filename or stream URL")
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

    ptz_parser = subparsers.add_parser("ptz", help="control pan/tilt/zoom")

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
    if "CAMERA_PASSWORD" not in os.environ:
        print("Error: environment variable CAMERA_PASSWORD not set", file=sys.stderr)
        sys.exit(2)
    LOGGER.info(f"Logging into {args.host} as {args.user}")
    c = MipcCameraClient(args.host)
    c.login(args.user, os.environ["CAMERA_PASSWORD"])

    _run_handler(args, c)

if __name__ == "__main__":
    main()
