"""
Example on how to use the client class to take snapshots at a regular interval,
aka timelapse mode. Set CAMERA_HOST, CAMERA_USER and CAMERA_PASSWORD, and run.
"""

import datetime
import os
from pathlib import Path
import time

from mipc_camera_client import MipcCameraClient

camera_ip = os.environ["CAMERA_HOST"]
camera_user = os.environ["CAMERA_USER"]
# login
c = MipcCameraClient(camera_ip)
c.login(camera_user, os.environ["CAMERA_PASSWORD"])

# stop taking pictures in 2 hours from now
stop_time = datetime.datetime.now() + datetime.timedelta(hours=2)
# take a picture every 5 seconds
sleep_interval = datetime.timedelta(seconds=5)

def _generate_filename():
    """Generate filename based on camera serial number and current timestamp"""
    now = datetime.datetime.now(datetime.timezone.utc)
    timestamp_str = now.strftime("%Y-%m-%dT%H-%M-%S.%f%Z")
    return f"{timestamp_str}_{c.get_device_sn()}.jpeg"

# Create an output directory
output_dir = Path("pictures/")
output_dir.mkdir(exist_ok=True)

while datetime.datetime.now() <= stop_time:
    print("taking snapshot... ", end='')
    jpeg_data = c.get_image()
    snapshot_path = output_dir / _generate_filename()
    snapshot_path.write_bytes(jpeg_data)
    print(f"saved to {snapshot_path}")
    time.sleep(sleep_interval.seconds)
