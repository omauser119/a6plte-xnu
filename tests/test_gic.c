#include "../xnu/pexpert/arm/a6plte/gic.h"
#include <assert.h>
#include <stdio.h>
static uint32_t regs[0x3000/4];
static unsigned writes;
static uint32_t rd(uintptr_t a) { assert(a>=0x1000 && a<0x4000 && !(a&3)); return regs[(a-0x1000)/4]; }
static void wr(uintptr_t a,uint32_t v) { assert(a>=0x1000 && a<0x4000 && !(a&3));regs[(a-0x1000)/4]=v;++writes; }
static void barrier(void) { }
int main(void) {
    struct a6_gic g={.dist=0x1000,.cpu=0x3000,.read=rd,.write=wr,.barrier=barrier};
    wr(0x1004,7); wr(0x1c04,~0u);
    assert(!a6_gic_init(&g) && g.lines==256);
    assert(rd(0x1100)==1u<<20); assert((rd(0x1c04)&(2u<<8))==0);
    assert(rd(0x3000)==1 && rd(0x3004)==255);
    for(unsigned irq=1020;irq<=1023;++irq) { wr(0x300c,irq); uint32_t t; assert(a6_gic_ack(&g,&t)==irq); unsigned n=writes;a6_gic_end(&g,t);assert(writes==n); }
    uint32_t token=20|(3<<10); wr(0x300c,token); uint32_t t; assert(a6_gic_ack(&g,&t)==20);
    a6_gic_end(&g,t); assert(rd(0x3010)==token);
    a6_gic_mask(&g,37);assert(rd(0x1184)==1u<<5);
    unsigned n=writes; a6_gic_mask(&g,1023);assert(n==writes);
    puts("PASS: GICv2 PPI20, level trigger, masks, EOI token, spurious IDs");
}
