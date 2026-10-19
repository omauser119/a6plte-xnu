/* SPDX-License-Identifier: BSD-2-Clause */
#ifndef A6_APPLE_DT_H
#define A6_APPLE_DT_H
#include <stdint.h>
unsigned a6_make_adt(void *buf, unsigned cap, uint64_t dest, uint64_t arena,
                     uint64_t span, uint32_t freq, const uint8_t *seed, unsigned seed_size, uint64_t ramdisk, uint64_t ramdisk_bytes);
#endif
