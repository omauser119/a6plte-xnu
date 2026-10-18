/* SPDX-License-Identifier: BSD-2-Clause */
#ifndef A6_FB_H
#define A6_FB_H
#include <stdint.h>
#include <stddef.h>
enum a6_pixel_format { A6_RGB888 = 1, A6_XRGB8888 = 2, A6_RGB565 = 3 };
struct a6_fb {
    volatile uint8_t *base;
    uint64_t size;
    uint32_t width, height, stride, format, x, y;
};
int a6_fb_init(struct a6_fb *, uintptr_t, uint64_t, uint32_t, uint32_t, uint32_t, uint32_t);
void a6_fb_putc(struct a6_fb *, char);
void a6_fb_puts(struct a6_fb *, const char *);
void a6_fb_hex(struct a6_fb *, uint64_t);
void a6_fb_clear(struct a6_fb *);
#endif
