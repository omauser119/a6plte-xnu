/* SPDX-License-Identifier: BSD-2-Clause */
#ifndef A6_PACKAGE_H
#define A6_PACKAGE_H
#include <stdint.h>
/* Bound the initial contiguous RAM donation to the native bootstrap tables. */
#define A6_XNU_MAX_MEMORY UINT64_C(0x40000000)
struct a6_xnu_package {
    char magic[8]; uint32_t version, header;
    uint64_t virt, entry, span, bytes;
    uint32_t crc, flags; uint64_t ramdisk_bytes;
};
struct a6_xnu_layout {
    uint64_t kernel, args, tree, ramdisk, top, donated;
};
int a6_package_parse(const void *, uint64_t, struct a6_xnu_package *);
int a6_package_layout(const struct a6_xnu_package *, uint64_t, uint64_t, struct a6_xnu_layout *);
#endif
