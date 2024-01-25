# mipc_camera_client

[![PyPI version](https://badge.fury.io/py/mipc-camera-client.svg)](https://badge.fury.io/py/mipc-camera-client)

Simple client for MIPC-based webcam. 
I bought a cheapo used WiFi camera on eBay, turns out the local web UI accessible over LAN is broken,
and using the OEM's app proxies all the video through random IP addresses which I'm not cool with.

## supported features

- login & auth - reverse-engineered from the broken web UI on my camera :)
- getting a snapshot
- getting a stream URL
- control pan/tilt

## Using the library

Install the package as usual per your package manager and:
```python
camera_ip = "192.168.0.123"
camera_user = "exampleuser"
camera_password = "P@ssw0rd"

from mipc_camera_client import MipcCameraClient

c = MipcCameraClient(camera_ip)
c.login(camera_user, camera_password)
jpeg_data = c.get_image()
with open("hello.jpg", mode="wb") as file:
    file.write(jpeg_data)
```

Also see [examples/](./examples/).

## CLI

```
$ usage: mipc_camera_client [-h] [--host HOST] [--user USER] {snapshot,stream,ptz} ...

CLI client for MIPC cameras

options:
  -h, --help            show this help message and exit
  --host HOST           Camera address (hostname or IP), uses CAMERA_HOST env var if not supplied
  --user USER           Camera username (from the web interface), uses CAMERA_USER env var if not supplied. Set CAMERA_PASSWORD for password.

commands:
  Available commands

  {snapshot,stream,ptz}
    snapshot            take a JPEG snapshot
    stream              get RTMP stream URL
    ptz                 control pan/tilt/zoom
```
