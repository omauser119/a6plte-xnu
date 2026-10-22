/* SPDX-License-Identifier: BSD-2-Clause */
#ifndef A6_FDT_H
#define A6_FDT_H
#include "../console/fb.h"
struct range { uint64_t base, size; };
struct platform {
    struct a6_fb fb;
    struct range ram[16], reserved[96];
    unsigned nr_ram, nr_reserved;
    uint64_t initrd_start, initrd_end;
    uint8_t rng_seed[256];
    unsigned rng_seed_size;
};
int platform_parse(const void *, struct platform *);
int platform_alloc(const struct platform *, uint64_t, uint64_t, struct range, uint64_t *);
int platform_alloc_xnu(const struct platform *, struct range, struct range *);
#endif
