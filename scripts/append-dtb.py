#!/usr/bin/env python3
"""Append an A6+ DTB in the format consumed by lk2nd's ARM64 path."""

import argparse
import struct
from pathlib import Path


FDT_MAGIC = 0xD00DFEED
LINUX_MAGIC = b"ARMd"
LINUX_DTB_OFFSET = 0x2C
PAGE_SIZE = 0x1000


def aligned(value, alignment):
    return (value + alignment - 1) & ~(alignment - 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", required=True, type=Path)
    parser.add_argument("--dtb", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    fd = bytearray(args.fd.read_bytes())
    if len(fd) < 64 or fd[0x38:0x3C] != LINUX_MAGIC:
        raise SystemExit("input is not a Linux ARM64 Image")

    image_size = struct.unpack_from("<Q", fd, 0x10)[0]
    if image_size != len(fd):
        raise SystemExit(
            f"FD size 0x{len(fd):x} does not match Image image_size 0x{image_size:x}"
        )

    dtb = args.dtb.read_bytes()
    if len(dtb) < 40 or struct.unpack_from(">I", dtb, 0)[0] != FDT_MAGIC:
        raise SystemExit("input is not a flattened device tree")

    dtb_size = struct.unpack_from(">I", dtb, 4)[0]
    if dtb_size < 40 or dtb_size > len(dtb):
        raise SystemExit("invalid DTB total size")
    dtb = dtb[:dtb_size]

    dtb_offset = aligned(len(fd), PAGE_SIZE)
    if dtb_offset > len(fd):
        fd.extend(b"\0" * (dtb_offset - len(fd)))

    # lk2nd reads the appended-DTB offset from the ARM64 Image reserved word
    # at 0x2c. Linux ignores this reserved word; the UEFI trampoline does too.
    struct.pack_into("<I", fd, LINUX_DTB_OFFSET, dtb_offset)
    fd.extend(dtb)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(fd)
    print(f"wrote {args.output} ({len(fd)} bytes), DTB at 0x{dtb_offset:x}")


if __name__ == "__main__":
    main()
