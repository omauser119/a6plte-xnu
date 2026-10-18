#include "../console/boot_abi.h"
#include "../xnu/pexpert/arm/a6plte/early.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
static uintptr_t pa;
static uintptr_t map(uintptr_t p,uintptr_t n) { assert(p==pa && n==3240*2220); return p; }
int main(void) {
    unsigned char *b=calloc(1,3240*2220); assert(b); pa=(uintptr_t)b;
    struct a6_boot_args a={.revision=2,.version=2,.video={.base=pa,.stride=3240,.width=1080,.height=2220,.depth=24}};
    a6_xnu_early_entry(&a);
    unsigned long n=0; for(unsigned i=0;i<3240*2220;++i)n+=b[i]; assert(n);
    a6_xnu_puts("test visible through bootstrap mapping\n");
    unsigned long n2=0;for(unsigned i=0;i<3240*2220;++i)n2+=b[i];assert(n2>n);
    a6_xnu_suspend_console();
    a6_xnu_puts("test queued while retiring bootstrap mappings\n");
    unsigned long n3=0;for(unsigned i=0;i<3240*2220;++i)n3+=b[i];assert(n3==n2);
    assert(a6_xnu_map_console(map));
    a6_xnu_puts("test mapped console output\n");
    /* Real XNU assert metadata has unaligned 64-bit pointers at +4 and +12. */
    unsigned char descriptor[20];
    uint32_t info=2129u<<8;
    uintptr_t file=(uintptr_t)"pmap.c",expression=(uintptr_t)"err == kSuccess";
    memcpy(descriptor,&info,4); memcpy(descriptor+4,&file,8); memcpy(descriptor+12,&expression,8);
    a6_xnu_early_fault(0,0xf200bffc,0,0,1,(uintptr_t)descriptor);
    free(b); puts("PASS: XNU bootstrap output, safe deferred transition, mapped framebuffer");
}
