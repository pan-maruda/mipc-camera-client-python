"""List candidate RPC symbols in cached scripts without executing them.

Usage: python tools/inventory_client.py C:\\Users\\bryle\\MIPC
Output is metadata only. Cookies, debug logs and cached RPC replies are not read.
Candidates include UI event names; they are not automatically added to the API.
"""

import argparse
import hashlib
import json
import re
import zlib
from pathlib import Path


def inventory(root: Path) -> dict:
    assets = []
    cache = root / "cache"
    if not cache.is_dir():
        raise ValueError("Client directory has no cache directory")
    for path in sorted(cache.glob("f_*")):
        if not path.is_file() or path.stat().st_size > 50_000_000:
            continue
        raw = path.read_bytes()
        for match in re.finditer(b"\x1f\x8b\x08", raw):
            try:
                decoder = zlib.decompressobj(31)
                data = decoder.decompress(raw[match.start() :], 20_000_000)
                if not decoder.eof:
                    continue
                script = data.decode("utf-8")
            except (zlib.error, UnicodeDecodeError):
                continue
            if script.count("ccm_") < 20:
                continue
            names = sorted(
                set(re.findall(r"\b(?:ccm|cacs|mmq)_[a-z0-9_]{2,60}\b", script))
            )
            assets.append(
                {
                    "cache_asset": path.name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "decompressed_bytes": len(data),
                    "candidate_symbols": names,
                }
            )
    executable = root / "MIPC.exe"
    return {
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()
        if executable.is_file()
        else None,
        "assets": assets,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(inventory(args.client_directory), indent=2))
