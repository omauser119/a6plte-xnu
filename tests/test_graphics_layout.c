/* SPDX-License-Identifier: BSD-2-Clause */
#include "../xnu/iokit/Kernel/arm/A6PlatformServicesABI.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint64_t random_word(void) {
    static uint64_t s=0xdebdfee1; s^=s<<13;s^=s>>7;s^=s<<17;return s;
}
int main(void) {
    struct a6_surface_info s;
    assert(sizeof(s)==32 && sizeof(struct a6_display_info)==32);
    assert(a6_surface_layout(1080,1920,A6_PIXEL_XRGB8888,&s));
    assert(s.width==1080 && s.height==1920 && s.stride==4352 && s.size==8355840);
    assert(s.reserved==0 && s.size%4096==0);
    assert(!a6_surface_layout(UINT64_MAX,1,1,&s));
    assert(!a6_surface_layout(4096,4096,2,&s));
    assert(!a6_surface_layout(1,1,3,&s));
    assert(!a6_surface_layout(1,1,1,NULL));
    struct a6_surface_info zero={0};assert(!memcmp(&s,&zero,sizeof(s)));
    struct a6_display_info d={1,1080,2220,3240,A6_PIXEL_RGB888,24,7192800};
    assert(a6_display_rectangle(&d,0,0,1080,2220,3240,7192800));
    assert(a6_display_rectangle(&d,1079,2219,1,1,3,3));
    assert(!a6_display_rectangle(&d,1079,2219,2,1,6,6));
    assert(!a6_display_rectangle(&d,0,2219,1,2,3,6));
    assert(!a6_display_rectangle(&d,0,0,1,1,UINT64_MAX,UINT64_MAX));
    assert(!a6_display_rectangle(&d,0,0,1,1,3,2));
    assert(!a6_display_rectangle(&d,0,0,1,1,0,0));
    assert(!a6_display_rectangle(&d,0,0,0,1,3,3));
    assert(!a6_display_rectangle(NULL,0,0,1,1,3,3));
    for (unsigned i=0;i<100000;++i) {
        uint64_t w=random_word(),h=random_word(),fmt=random_word();
        if (i%2==0) { w%=5000;h%=5000;fmt%=4; }
        if (a6_surface_layout(w,h,fmt,&s)) {
            assert(w && h && w<=4096 && h<=4096 && (fmt==1 || fmt==2));
            assert(s.size<=A6_SURFACE_MAX_BYTES && s.size>=s.stride*h && s.stride>=w*(fmt==1?3:4));
        }
        uint64_t x=random_word()%1200,y=random_word()%2300,rw=random_word(),rh=random_word(),stride=random_word(),bytes=random_word();
        if (i%2==0) { rw%=1200;rh%=2300;stride%=66000; }
        if (a6_display_rectangle(&d,x,y,rw,rh,stride,bytes)) {
            assert(x<1080 && y<2220 && rw && rh && rw<=1080-x && rh<=2220-y);
            assert(stride>=rw*3 && stride<=65536 && bytes>=stride*rh);
            assert((y+rh-1)*d.stride+(x+rw)*3<=d.size);
        }
    }
    puts("PASS: shared-surface allocation bounds, framebuffer edge rectangles, overflow and 100000 fuzz cases");
}
