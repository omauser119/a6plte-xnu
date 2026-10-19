#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
boot_root=ramdisk
if [[ ${1:-} == --root=userdata ]]; then boot_root=userdata; shift; fi
if [[ $# != 1 && $# != 2 ]] || [[ $boot_root == userdata && $# != 1 ]]; then
    echo 'Usage: package-boot.sh [--root=userdata] /path/to/A6PLTE-kernel-MachO [raw-ramdisk.hfs]' >&2; exit 2
fi
A6_BOOT_ROOT=$boot_root "$ROOT/scripts/build-smoke.sh"
ramdisk_args=()
if [[ $# == 2 ]]; then ramdisk_args=(--ramdisk "$2"); fi
stem=xnu
if [[ $boot_root == userdata ]]; then stem=xnu-userdata; fi
python3 "$ROOT/scripts/pack-xnu.py" "$1" "$ROOT/artifacts/$stem.package" "${ramdisk_args[@]}"
python3 "$ROOT/scripts/mkbootimg-v0.py" --kernel "$ROOT/artifacts/fb-smoke.kernel" --ramdisk "$ROOT/artifacts/$stem.package" --output "$ROOT/artifacts/$stem-boot.img" --pagesize 2048 --base 0x80000000 --kernel_offset 0x00080000 --ramdisk_offset 0x20000000 --tags_offset 0x01e00000 --board a6plte --cmdline 'a6plte-xnu lk2nd.pass-simplefb=autorefresh' --header_version 0
