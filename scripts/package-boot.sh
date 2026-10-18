#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
if [[ $# != 1 ]]; then echo 'Usage: package-boot.sh /path/to/A6PLTE-kernel-MachO' >&2; exit 2; fi
"$ROOT/scripts/build-smoke.sh"
python3 "$ROOT/scripts/pack-xnu.py" "$1" "$ROOT/artifacts/xnu.package"
python3 "$ROOT/scripts/mkbootimg-v0.py" --kernel "$ROOT/artifacts/fb-smoke.kernel" --ramdisk "$ROOT/artifacts/xnu.package" --output "$ROOT/artifacts/xnu-boot.img" --pagesize 2048 --base 0x80000000 --kernel_offset 0x00080000 --ramdisk_offset 0x20000000 --tags_offset 0x01e00000 --board a6plte --cmdline 'a6plte-xnu lk2nd.pass-simplefb=autorefresh' --header_version 0
