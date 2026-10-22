/* SPDX-License-Identifier: BSD-2-Clause */
#include "loader.h"
#include "apple_dt.h"
#include "crc32.h"
#include "package.h"
#include "../console/boot_abi.h"
static void copy(void *d,const void *s,uint64_t n) { uint8_t *a=d; const uint8_t *b=s; while(n--) *a++=*b++; }
static void zero(void *d,uint64_t n) { uint8_t *a=d; while(n--) *a++=0; }
static void pause_before_entry(void) {
    uint64_t begin,now,freq;
    __asm__ volatile("mrs %0,cntpct_el0":"=r"(begin));
    __asm__ volatile("mrs %0,cntfrq_el0":"=r"(freq));
    do { __asm__ volatile("mrs %0,cntpct_el0":"=r"(now)); } while(now-begin<freq*2);
}
void xnu_load(struct platform *p,const void *dtb,struct range image) {
    struct a6_fb *fb=&p->fb;
#define FAIL(s) do { a6_fb_puts(fb,"XNU LOAD STOP: " s "\n"); return; } while(0)
    if(!p->initrd_start || p->initrd_end<=p->initrd_start || p->initrd_end-p->initrd_start<64) FAIL("no kernel package");
    /* A bootloader must not relocate the package into a firmware carveout.
     * Check before the first load, since secure RAM may abort the access. */
    for(unsigned i=0;i<p->nr_reserved;++i) {
        const struct range *range=&p->reserved[i];
        if(p->initrd_start<range->base+range->size && range->base<p->initrd_end) {
            a6_fb_puts(fb,"PACKAGE PA: "); a6_fb_hex(fb,p->initrd_start);
            a6_fb_puts(fb,"\nRESERVED PA: "); a6_fb_hex(fb,range->base); a6_fb_puts(fb,"\n");
            FAIL("kernel package overlaps reserved RAM");
        }
    }
    a6_fb_puts(fb,"PACKAGE HEADER at "); a6_fb_hex(fb,p->initrd_start); a6_fb_puts(fb,"\n");
    struct a6_xnu_package h;
    if(a6_package_parse((const void *)(uintptr_t)p->initrd_start,p->initrd_end-p->initrd_start,&h))
        FAIL("invalid package header or bounds");
#if A6_ROOT_USERDATA
    if(h.ramdisk_bytes) FAIL("userdata-root image must not contain a RAMDisk");
#endif
    a6_fb_puts(fb,"PACKAGE HEADER READ\n");
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
    if(p->rng_seed_size!=sizeof(p->rng_seed)) FAIL("lk2nd must supply 256 bytes of boot entropy");
    a6_fb_puts(fb,"Boot entropy: 256 bytes from lk2nd\n");
    uint64_t el,sctlr; __asm__ volatile("mrs %0, CurrentEL":"=r"(el)); __asm__ volatile("mrs %0,sctlr_el1":"=r"(sctlr));
    if(el!=4 || (sctlr&5)) FAIL("EL1 with MMU and D-cache off required");
    /* Only donate a verified contiguous free window, never all RAM across firmware carveouts. */
    uint64_t allocation,arena=h.ramdisk_bytes ? 256*1024*1024 : 128*1024*1024;
    if(p->nr_reserved>=96) FAIL("reservation table full");
    const uint8_t *d=dtb; uint32_t dtlen=(uint32_t)d[4]<<24|(uint32_t)d[5]<<16|(uint32_t)d[6]<<8|d[7];
    p->reserved[p->nr_reserved++]=(struct range){(uintptr_t)dtb,dtlen};
#if A6_ROOT_USERDATA
    struct range window;
    if(platform_alloc_xnu(p,image,&window)) FAIL("no safe RAM window");
    allocation=window.base;arena=window.size;
#else
    if(platform_alloc(p,arena,0x200000,image,&allocation)) FAIL("no safe RAM window");
#endif
    /* Preserve PA/VA low-21-bit alignment and reserve all ramdisk pages. */
    struct a6_xnu_layout layout;
    if(a6_package_layout(&h,allocation,arena,&layout)) FAIL("invalid bootstrap memory placement");
    uint64_t dest=layout.kernel,donated=layout.donated;
    a6_fb_puts(fb,"Loading Mach-O at "); a6_fb_hex(fb,dest); a6_fb_puts(fb,"\n");
    copy((void *)(uintptr_t)dest,src,h.span);
    a6_fb_puts(fb,"KERNEL COPY COMPLETE\n");
    if(h.ramdisk_bytes) {
        a6_fb_puts(fb,"Copying RAMDisk at "); a6_fb_hex(fb,layout.ramdisk); a6_fb_puts(fb,"\n");
        copy((void *)(uintptr_t)layout.ramdisk,src+h.span,h.ramdisk_bytes);
        a6_fb_puts(fb,"RAMDISK COPY COMPLETE\n");
    }
    uint64_t args_pa=layout.args,tree_pa=layout.tree;
    struct a6_boot_args *args=(void *)(uintptr_t)args_pa; zero(args,sizeof(*args));
    uint64_t freq; __asm__ volatile("mrs %0,cntfrq_el0":"=r"(freq));
    unsigned tree_size=a6_make_adt((void *)(uintptr_t)tree_pa,0x10000,dest,donated,h.span,(uint32_t)freq,
                                p->rng_seed,p->rng_seed_size,layout.ramdisk,h.ramdisk_bytes);
    zero(p->rng_seed,sizeof(p->rng_seed));
    p->rng_seed_size=0;
    if(!tree_size) FAIL("Apple DT overflow");
    args->revision=2; args->version=2; args->virt_base=h.virt; args->phys_base=dest; args->mem_size=donated; args->mem_size_actual=donated;
    args->top_of_kernel_data=layout.top;
    args->video=(struct a6_boot_video){(uintptr_t)fb->base,0,fb->stride,fb->width,fb->height,fb->format==A6_RGB888?24:fb->format==A6_XRGB8888?32:16};
    /* XNU consumes a virtual DT pointer after its bootstrap identity -> KVA transition. */
    args->device_tree=h.virt+tree_pa-dest; args->device_tree_length=tree_size;
#if A6_ROOT_USERDATA
    /* The DEVELOPMENT macOS profile otherwise rejects iOS PID1 with
     * OS_REASON_EXEC / EXEC_EXIT_REASON_WRONG_PLATFORM (9 / 14).
     * Use XNU's native compatibility switch; keep signature checks intact. */
    /* This standalone port has no AppleMobileFileIntegrity trust-cache
     * service. Use launchd_cache_loader's native unsecure data-cache mode,
     * rather than pretending an Apple trust-cache query authenticated it. */
    const char cmd[]="-v debug=0x14 cpus=1 serial=1 startup_debug=1 unentitled_ios_sim_launch=1 launchd_unsecure_cache=1 rd=a6userdata launchdsuffix=release";
    _Static_assert(sizeof(cmd)<=sizeof(args->command_line),"BootArgs command line overflow");
    copy(args->command_line,cmd,sizeof(cmd));
    a6_fb_puts(fb,"Root: userdata HFS+; PID1: /sbin/launchd\n");
#else
    const char cmd[]="-v debug=0x14 cpus=1 serial=1 startup_debug=1";
    const char root_cmd[]="-v debug=0x14 cpus=1 serial=1 startup_debug=1 rd=md0";
    if(h.ramdisk_bytes) copy(args->command_line,root_cmd,sizeof(root_cmd));
    else copy(args->command_line,cmd,sizeof(cmd));
#endif
    /* Native topology parsing filters out every AP with cpus=1, so the
     * retained SMP implementation cannot issue CPU_ON for CPU1--CPU7. */
    a6_fb_puts(fb,"CPU: CPU0 only; SMP temporarily disabled\n");
    a6_fb_puts(fb,"Entering experimental XNU. Waiting for XNU marker.\n");
    a6_fb_puts(fb,"ENTRY PA: "); a6_fb_hex(fb,dest+h.entry-h.virt);
    a6_fb_puts(fb,"\nBOOT ARGS PA: "); a6_fb_hex(fb,args_pa); a6_fb_puts(fb,"\n");
    pause_before_entry();
    __asm__ volatile("dsb sy; ic iallu; dsb sy; isb":::"memory");
    ((void (*)(struct a6_boot_args *))(uintptr_t)(dest+h.entry-h.virt))(args);
    FAIL("kernel returned");
}
