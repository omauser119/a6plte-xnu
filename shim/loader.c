/* SPDX-License-Identifier: BSD-2-Clause */
#include "loader.h"
#include "crc32.h"
#include "../console/boot_abi.h"
struct package { char magic[8]; uint32_t version, header; uint64_t virt, entry, span, bytes; uint32_t crc, flags; uint64_t reserved; };
_Static_assert(sizeof(struct package)==64,"package ABI");
static void copy(void *d,const void *s,uint64_t n) { uint8_t *a=d; const uint8_t *b=s; while(n--) *a++=*b++; }
static void zero(void *d,uint64_t n) { uint8_t *a=d; while(n--) *a++=0; }
static unsigned length(const char *s) { unsigned n=0; while(s[n]) ++n; return n; }
static void pause_before_entry(void) {
    uint64_t begin,now,freq;
    __asm__ volatile("mrs %0,cntpct_el0":"=r"(begin));
    __asm__ volatile("mrs %0,cntfrq_el0":"=r"(freq));
    do { __asm__ volatile("mrs %0,cntpct_el0":"=r"(now)); } while(now-begin<freq*2);
}
/* Bounded Apple flat device-tree writer: native little-endian counts and 4-byte padding. */
struct adt { uint8_t *base; unsigned used, cap; int failed; };
static void emit(struct adt *a,const void *v,unsigned n) { if(a->failed || n>a->cap-a->used) { a->failed=1; return; } copy(a->base+a->used,v,n); a->used+=n; }
static void word(struct adt *a,uint32_t v) { emit(a,&v,4); }
static void prop(struct adt *a,const char *name,const void *v,unsigned n) {
    char key[32]={0}; unsigned l=length(name); if(l>31) { a->failed=1; return; }
    copy(key,name,l); emit(a,key,32); word(a,n); emit(a,v,n);
    uint32_t z=0; emit(a,&z,(4-n%4)%4);
}
static void str(struct adt *a,const char *k,const char *v) { prop(a,k,v,length(v)+1); }
static void node(struct adt *a,unsigned props,unsigned kids,const char *name) { word(a,props+1); word(a,kids); str(a,"name",name); }
static unsigned make_adt(void *buf,unsigned cap,uint64_t dest,uint64_t arena,uint64_t span,uint32_t freq) {
    struct adt a={buf,0,cap,0}; uint32_t one=1,zero32=0; uint64_t r[3]={0,0x01000000,0x10000000};
    node(&a,2,3,"device-tree"); str(&a,"compatible","samsung,a6plte"); str(&a,"model","SM-A605FN");
    node(&a,4,1,"chosen"); prop(&a,"debug-enabled",&one,4); prop(&a,"dram-base",&dest,8); prop(&a,"dram-size",&arena,8); str(&a,"firmware-version","lk2nd-a6plte-xnu-experimental");
    node(&a,1,0,"memory-map"); uint64_t kr[2]={dest,span}; prop(&a,"Kernel",kr,sizeof(kr));
    node(&a,0,1,"cpus");
    node(&a,6,0,"cpu0"); str(&a,"device_type","cpu"); str(&a,"state","running"); prop(&a,"reg",&zero32,4); prop(&a,"cpu-id",&zero32,4); prop(&a,"timebase-frequency",&freq,4); str(&a,"compatible","arm,cortex-a53");
    node(&a,2,0,"arm-io"); str(&a,"device_type","msm8953"); prop(&a,"ranges",r,sizeof(r));
    return a.failed?0:a.used;
}
void xnu_load(struct platform *p,const void *dtb,struct range image) {
    struct a6_fb *fb=&p->fb;
#define FAIL(s) do { a6_fb_puts(fb,"XNU LOAD STOP: " s "\n"); return; } while(0)
    if(!p->initrd_start || p->initrd_end<=p->initrd_start || p->initrd_end-p->initrd_start<64) FAIL("no kernel package");
    a6_fb_puts(fb,"PACKAGE HEADER at "); a6_fb_hex(fb,p->initrd_start); a6_fb_puts(fb,"\n");
    struct package h; copy(&h,(const void *)(uintptr_t)p->initrd_start,sizeof(h));
    a6_fb_puts(fb,"PACKAGE HEADER READ\n");
    const char magic[8]="A6XNU01"; for(unsigned i=0;i<8;++i) if(h.magic[i]!=magic[i]) FAIL("bad package magic");
    if(h.version!=1 || h.header!=64 || h.flags || h.reserved || h.span!=h.bytes || !h.span || h.span>64*1024*1024 ||
       h.bytes!=p->initrd_end-p->initrd_start-64 || (h.virt&0x3fff) || (h.span&0x3fff) || h.virt<0xffff000000000000ULL ||
       h.virt+h.span<h.virt || h.entry<h.virt || h.entry-h.virt>=h.span || (h.entry&3)) FAIL("invalid package bounds");
    const uint8_t *src=(void *)(uintptr_t)(p->initrd_start+64);
    a6_fb_puts(fb,"CRC CHECK ");
    uint32_t crc=0;
    for(uint64_t offset=0;offset<h.bytes;) {
        uint64_t chunk=h.bytes-offset;
        if(chunk>0x100000) chunk=0x100000;
        crc=a6_crc32(crc,src+offset,chunk); offset+=chunk;
        a6_fb_puts(fb,".");
    }
    a6_fb_puts(fb,"\n");
    if(crc!=h.crc) FAIL("CRC mismatch");
    a6_fb_puts(fb,"CRC OK\n");
    uint64_t el,sctlr; __asm__ volatile("mrs %0, CurrentEL":"=r"(el)); __asm__ volatile("mrs %0,sctlr_el1":"=r"(sctlr));
    if(el!=4 || (sctlr&5)) FAIL("EL1 with MMU and D-cache off required");
    /* Only donate a verified contiguous free window, never all RAM across firmware carveouts. */
    uint64_t dest,arena=128*1024*1024;
    if(p->nr_reserved>=96) FAIL("reservation table full");
    const uint8_t *d=dtb; uint32_t dtlen=(uint32_t)d[4]<<24|(uint32_t)d[5]<<16|(uint32_t)d[6]<<8|d[7];
    p->reserved[p->nr_reserved++]=(struct range){(uintptr_t)dtb,dtlen};
    if(platform_alloc(p,arena,0x200000,image,&dest)) FAIL("no safe 128 MiB RAM window");
    a6_fb_puts(fb,"Loading Mach-O at "); a6_fb_hex(fb,dest); a6_fb_puts(fb,"\n");
    copy((void *)(uintptr_t)dest,src,h.bytes);
    a6_fb_puts(fb,"KERNEL COPY COMPLETE\n");
    uint64_t args_pa=dest+h.span, tree_pa=args_pa+0x4000;
    struct a6_boot_args *args=(void *)(uintptr_t)args_pa; zero(args,sizeof(*args));
    uint64_t freq; __asm__ volatile("mrs %0,cntfrq_el0":"=r"(freq));
    unsigned tree_size=make_adt((void *)(uintptr_t)tree_pa,0x10000,dest,arena,h.span,(uint32_t)freq);
    if(!tree_size) FAIL("Apple DT overflow");
    args->revision=2; args->version=2; args->virt_base=h.virt; args->phys_base=dest; args->mem_size=arena; args->mem_size_actual=arena;
    args->top_of_kernel_data=(tree_pa+tree_size+0x3fff)&~0x3fffULL;
    args->video=(struct a6_boot_video){(uintptr_t)fb->base,0,fb->stride,fb->width,fb->height,fb->format==A6_RGB888?24:fb->format==A6_XRGB8888?32:16};
    /* XNU consumes a virtual DT pointer after its bootstrap identity -> KVA transition. */
    args->device_tree=h.virt+tree_pa-dest; args->device_tree_length=tree_size;
    const char cmd[]="-v debug=0x14 cpus=1 serial=1";
    copy(args->command_line,cmd,sizeof(cmd));
    a6_fb_puts(fb,"Entering experimental XNU. Waiting for XNU marker.\n");
    a6_fb_puts(fb,"ENTRY PA: "); a6_fb_hex(fb,dest+h.entry-h.virt);
    a6_fb_puts(fb,"\nBOOT ARGS PA: "); a6_fb_hex(fb,args_pa); a6_fb_puts(fb,"\n");
    pause_before_entry();
    __asm__ volatile("dsb sy; ic iallu; dsb sy; isb":::"memory");
    ((void (*)(struct a6_boot_args *))(uintptr_t)(dest+h.entry-h.virt))(args);
    FAIL("kernel returned");
}
