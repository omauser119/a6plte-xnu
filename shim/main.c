/* SPDX-License-Identifier: BSD-2-Clause */
#include "fdt.h"
#include "loader.h"
static struct platform platform;
extern char _start[], __image_end[];
static uint64_t counter(void) { uint64_t t; __asm__ volatile("mrs %0, cntpct_el0":"=r"(t)); return t; }
static void pause_second(void) { uint64_t f; __asm__ volatile("mrs %0, cntfrq_el0":"=r"(f)); uint64_t t=counter(); while(counter()-t<f) __asm__ volatile("yield"); }
void shim_main(const void *dtb) {
    if(platform_parse(dtb,&platform)) {
        /* Fail closed: don't guess an FB address if DTB validation failed. */
        for(;;) __asm__ volatile("wfe");
    }
    struct a6_fb *fb=&platform.fb;
    a6_fb_clear(fb);
    a6_fb_puts(fb,"A6PLTE / SM-A605FN\nFRAMEBUFFER BRING-UP\n\n");
    a6_fb_puts(fb,"AArch64 bridge entered. UART disabled.\nFB: "); a6_fb_hex(fb,(uintptr_t)fb->base);
    a6_fb_puts(fb,"\nDTB: "); a6_fb_hex(fb,(uintptr_t)dtb);
    uint64_t el; __asm__ volatile("mrs %0, CurrentEL":"=r"(el));
    a6_fb_puts(fb,"\nCurrentEL: "); a6_fb_hex(fb,el>>2);
    a6_fb_puts(fb,"\nRAM banks: "); a6_fb_hex(fb,platform.nr_ram);
    if(platform.initrd_end>platform.initrd_start) {
        a6_fb_puts(fb,"\nKernel package detected.\n");
        xnu_load(&platform,dtb,(struct range){(uintptr_t)_start,(uintptr_t)__image_end-(uintptr_t)_start});
        for(;;) __asm__ volatile("wfe");
    }
    a6_fb_puts(fb,"\n\nThis image tests the bridge console.\nXNU is NOT running in this image.\n\n");
    for(uint64_t n=0;;++n) {
        a6_fb_puts(fb,"DISPLAY HEARTBEAT "); a6_fb_hex(fb,n); a6_fb_puts(fb,"\n");
        pause_second();
    }
}
/* Freestanding compiler support (built with -fno-builtin). */
void *memcpy(void *d,const void *s,size_t n) { uint8_t *a=d; const uint8_t *b=s; while(n--) *a++=*b++; return d; }
void *memset(void *d,int c,size_t n) { uint8_t *a=d; while(n--) *a++=(uint8_t)c; return d; }
