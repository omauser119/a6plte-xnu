#include "../console/boot_abi.h"
#include "../xnu/pexpert/arm/a6plte/early.h"
#include "../xnu/iokit/Kernel/arm/A6PlatformServicesABI.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
static uintptr_t pa;
static uintptr_t map(uintptr_t p,uintptr_t n) { assert(p==pa && n==3240*2220); return p; }
static void *writer(void *arg) {
    (void)arg;
    for (unsigned n=0;n<80;++n) a6_xnu_puts("Concurrent CPU framebuffer line\n");
    return NULL;
}
int main(void) {
    unsigned char *b=calloc(1,3240*2220); assert(b); pa=(uintptr_t)b;
    struct a6_display display;
    assert(!a6_xnu_get_display(&display));
    struct a6_boot_args a={.revision=2,.version=2,.video={.base=pa,.stride=3240,.width=1080,.height=2220,.depth=24}};
    a6_xnu_early_entry(&a);
    unsigned long n=0; for(unsigned i=0;i<3240*2220;++i)n+=b[i]; assert(n);
    a6_xnu_puts("test visible through bootstrap mapping\n");
    unsigned long n2=0;for(unsigned i=0;i<3240*2220;++i)n2+=b[i];assert(n2>n);
    a6_xnu_suspend_console();
    assert(!a6_xnu_get_display(&display));
    a6_xnu_puts("test queued while retiring bootstrap mappings\n");
    unsigned long n3=0;for(unsigned i=0;i<3240*2220;++i)n3+=b[i];assert(n3==n2);
    assert(a6_xnu_map_console(map));
    assert(a6_xnu_get_display(&display));
    assert(display.info.width==1080 && display.info.height==2220 && display.info.stride==3240);
    assert(display.info.size==3240*2220 && display.info.bits_per_pixel==24);
    assert(display.physical_address==pa && display.virtual_address==pa);
    a6_xnu_puts("test mapped console output\n");
    /* Concurrent scrolling must yield the same pixels as the serialized text.
     * Identical lines make the expected image independent of thread order. */
    a6_xnu_early_entry(&a);assert(a6_xnu_map_console(map));
    for (unsigned n=0;n<640;++n) a6_xnu_puts("Concurrent CPU framebuffer line\n");
    unsigned char *expected=malloc(3240*2220);assert(expected);
    memcpy(expected,b,3240*2220);
    a6_xnu_early_entry(&a);assert(a6_xnu_map_console(map));
    pthread_t writers[8];
    for(unsigned n=0;n<8;++n) assert(!pthread_create(&writers[n],NULL,writer,NULL));
    for(unsigned n=0;n<8;++n) assert(!pthread_join(writers[n],NULL));
    assert(!memcmp(expected,b,3240*2220));free(expected);
    /* Real XNU assert metadata has unaligned 64-bit pointers at +4 and +12. */
    unsigned char descriptor[20];
    uint32_t info=2129u<<8;
    uintptr_t file=(uintptr_t)"pmap.c",expression=(uintptr_t)"err == kSuccess";
    memcpy(descriptor,&info,4); memcpy(descriptor+4,&file,8); memcpy(descriptor+12,&expression,8);
    a6_xnu_early_fault(0,0xf200bffc,0,0,1,(uintptr_t)descriptor);
    free(b); puts("PASS: XNU bootstrap output, safe deferred transition, mapped framebuffer");
}
