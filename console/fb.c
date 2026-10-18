/* SPDX-License-Identifier: BSD-2-Clause */
#include "fb.h"
#include "font5x12.h"
/* Single boot CPU, no allocation, no libc, no UART, byte stores (Device memory safe). */
#define SCALE 3u
#define CW (6u * SCALE)
#define CH (12u * SCALE)
static unsigned bpp(uint32_t f) { return f == A6_RGB888 ? 3 : f == A6_XRGB8888 ? 4 : f == A6_RGB565 ? 2 : 0; }
static void barrier(void) {
#ifdef __aarch64__
    __asm__ volatile("dsb sy" ::: "memory");
#endif
}
int a6_fb_init(struct a6_fb *f, uintptr_t base, uint64_t size,
               uint32_t w, uint32_t h, uint32_t stride, uint32_t format) {
    unsigned p = bpp(format);
    if (!base || !p || w < CW || h < CH || w > 8192 || h > 8192 ||
        stride < (uint64_t)w*p || stride > 65536 || size < (uint64_t)stride*h ||
        size > UINTPTR_MAX - base) return -1;
    *f = (struct a6_fb){(volatile uint8_t *)base, size, w, h, stride, format, 0, 0};
    return 0;
}
void a6_fb_clear(struct a6_fb *f) {
    if (!f->base) return;
    for (uint64_t i=0; i<(uint64_t)f->stride*f->height; ++i) f->base[i]=0;
    f->x=f->y=0;
    barrier();
}
static void pixel(struct a6_fb *f, uint32_t x, uint32_t y, int on) {
    volatile uint8_t *p = f->base + (uint64_t)y*f->stride + x*bpp(f->format);
    /* White on black deliberately avoids any RGB/BGR ambiguity in first-stage logs. */
    for (unsigned k=0; k<bpp(f->format); ++k) p[k]=on ? 255 : 0;
}
static void newline(struct a6_fb *f) {
    f->x=0; ++f->y;
    uint32_t rows=f->height/CH;
    if (f->y < rows) return;
    uint64_t line=(uint64_t)CH*f->stride, used=(uint64_t)rows*line;
    for (uint64_t i=0; i<used-line; ++i) f->base[i]=f->base[i+line];
    for (uint64_t i=used-line; i<used; ++i) f->base[i]=0;
    f->y=rows-1;
}
void a6_fb_putc(struct a6_fb *f, char ch) {
    if (!f->base) return;
    unsigned c=(unsigned char)ch;
    if (c=='\r') f->x=0;
    else if (c=='\n') newline(f);
    else if (c=='\t') { unsigned n=4-(f->x%4); while(n--) a6_fb_putc(f,' '); }
    else if(c=='\b') { if(f->x) --f->x; }
    else {
        if(c<32 || c>126) c='?';
        for(unsigned y=0;y<12;++y) {
            uint32_t bits=font5x12[(c-32)*2+y/6] >> ((y%6)*5);
            for(unsigned x=0;x<6;++x)
                for(unsigned sy=0;sy<SCALE;++sy)
                    for(unsigned sx=0;sx<SCALE;++sx)
                        pixel(f,f->x*CW+x*SCALE+sx,f->y*CH+y*SCALE+sy,x<5 && ((bits>>x)&1));
        }
        if(++f->x >= f->width/CW) newline(f);
    }
    barrier();
}
void a6_fb_puts(struct a6_fb *f,const char *s) { while(*s) a6_fb_putc(f,*s++); }
void a6_fb_hex(struct a6_fb *f,uint64_t n) {
    a6_fb_puts(f,"0x");
    for(int i=60;i>=0;i-=4) a6_fb_putc(f,"0123456789abcdef"[(n>>i)&15]);
}
