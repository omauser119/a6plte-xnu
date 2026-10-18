/* SPDX-License-Identifier: BSD-2-Clause */
#ifndef A6_CRC32_H
#define A6_CRC32_H
#include <stddef.h>
#include <stdint.h>
uint32_t a6_crc32(uint32_t seed, const void *data, size_t size);
#endif
