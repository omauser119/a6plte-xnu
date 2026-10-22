/* SPDX-License-Identifier: BSD-2-Clause */
#include "../shim/fdt.h"
#include "../shim/package.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static int touches(struct range a,struct range b) {
    return a.size && b.size && a.base<b.base+b.size && b.base<a.base+a.size;
}
static void check(const struct platform *p,struct range image,struct range out) {
    assert(out.size>=0x10000000 && out.size<=A6_XNU_MAX_MEMORY && !(out.base&0x1fffff));
    assert(out.base+out.size<=0x100000000ULL);
    unsigned inside=0;
    for(unsigned i=0;i<p->nr_ram;++i)
        inside|=out.base>=p->ram[i].base && out.base+out.size<=p->ram[i].base+p->ram[i].size;
    assert(inside && !touches(out,image));
    for(unsigned i=0;i<p->nr_reserved;++i)assert(!touches(out,p->reserved[i]));
    if(p->initrd_end>p->initrd_start)
        assert(!touches(out,(struct range){p->initrd_start,p->initrd_end-p->initrd_start}));
    /* An identity-map framebuffer must not overwrite a kernel RAM L1 slot. */
    uint64_t first=out.base>>30,last=(out.base+out.size-1)>>30;
    uint64_t fb_first=(uintptr_t)p->fb.base>>30,fb_last=((uintptr_t)p->fb.base+p->fb.size-1)>>30;
    assert(last<fb_first || first>fb_last);
    struct a6_xnu_package h={.virt=0xfffffff007004000ULL,.span=0x1200000};
    struct a6_xnu_layout layout;
    assert(!a6_package_layout(&h,out.base,out.size,&layout));
    assert(layout.kernel>=out.base && layout.kernel+layout.donated==out.base+out.size);
    assert(layout.top<=out.base+out.size && (layout.kernel&0x1fffff)==(h.virt&0x1fffff));
}
static struct platform fixture(void) {
    struct platform p={.nr_ram=2,.nr_reserved=1,.initrd_start=0x43600000,.initrd_end=0x44800000};
    p.ram[0]=(struct range){0x40000000,0x40000000};
    p.ram[1]=(struct range){0x80000000,0x80000000};
    p.reserved[0]=(struct range){0x40000000,0x0a400000};
    p.fb.base=(volatile uint8_t *)(uintptr_t)0x90001000;p.fb.size=3240*2220;
    return p;
}
static void rejected(struct platform *p,struct range image) {
    struct range out={1,2};assert(platform_alloc_xnu(p,image,&out));assert(!out.base && !out.size);
}
int main(void) {
    struct range image={0x40080000,0x20000},out;
    struct platform p=fixture(),original=p;
    assert(!platform_alloc_xnu(&p,image,&out));
    assert(out.base==0xc0000000 && out.size==0x40000000);check(&p,image,out);
    assert(!memcmp(&original,&p,sizeof(p)));
    p.nr_ram=1;
    assert(!platform_alloc_xnu(&p,image,&out));
    assert(out.base==0x4a400000 && out.size==0x30000000);check(&p,image,out);
    p.ram[0].size=0x2a000000;
    assert(!platform_alloc_xnu(&p,image,&out) && out.size==0x18000000);check(&p,image,out);
    p.ram[0].size=0x20000000;
    assert(!platform_alloc_xnu(&p,image,&out) && out.size==0x10000000);check(&p,image,out);
    p.ram[0].size=0x1a000000;rejected(&p,image);
    p=fixture();p.nr_ram=1;p.nr_reserved=0;p.initrd_start=p.initrd_end=0;
    assert(!platform_alloc_xnu(&p,image,&out));check(&p,image,out);
    /* Unsorted firmware/DTB holes must never become usable kernel memory. */
    p.reserved[p.nr_reserved++]=(struct range){0x70000000,0x100000};
    p.reserved[p.nr_reserved++]=(struct range){0x60000000,0x800000};
    p.reserved[p.nr_reserved++]=(struct range){0x50000000,0x100000};
    rejected(&p,image);
    p=fixture();p.nr_ram=1;p.ram[0]=(struct range){0x100000000ULL,0x40000000};rejected(&p,image);
    p.ram[0]=(struct range){UINT64_MAX-1,1};rejected(&p,image);
    p.ram[0]=(struct range){UINT64_MAX-1,4};rejected(&p,image);
    p=fixture();p.nr_reserved=96;rejected(&p,image);
    p=fixture();p.nr_ram=17;rejected(&p,image);
    p=fixture();p.reserved[0]=(struct range){UINT64_MAX,2};rejected(&p,image);
    p=fixture();rejected(&p,(struct range){UINT64_MAX,2});
    p=fixture();p.fb.base=NULL;rejected(&p,image);
    p=fixture();p.fb.size=UINT64_MAX;rejected(&p,image);
    assert(platform_alloc_xnu(NULL,image,&out) && !out.size);
    assert(platform_alloc_xnu(&p,image,NULL));
    puts("PASS: native RAM donation up to1GiB, one-bank/firmware/image/DTB/payload confinement, framebuffer L1 exclusion, 768/384/256MiB fallbacks and overflow rejection");
}
