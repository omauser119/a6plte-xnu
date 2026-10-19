/* SPDX-License-Identifier: BSD-2-Clause */
#include "apple_dt.h"
static void copy(void *d,const void *s,uint64_t n) { uint8_t *a=d; const uint8_t *b=s; while(n--) *a++=*b++; }
static unsigned length(const char *s) { unsigned n=0; while(s[n]) ++n; return n; }
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
unsigned a6_make_adt(void *buf,unsigned cap,uint64_t dest,uint64_t arena,uint64_t span,uint32_t freq,
                         const uint8_t *seed,unsigned seed_size,uint64_t ramdisk,uint64_t ramdisk_bytes) {
    struct adt a={buf,0,cap,0}; uint32_t one=1,zero32=0; uint64_t r[3]={0,0x01000000,0x10000000};
    node(&a,2,4,"device-tree"); str(&a,"compatible","samsung,a6plte"); str(&a,"model","SM-A605FN");
    node(&a,6,1,"chosen"); prop(&a,"debug-enabled",&one,4); prop(&a,"dram-base",&dest,8); prop(&a,"dram-size",&arena,8); str(&a,"firmware-version","lk2nd-a6plte-xnu-experimental");
    prop(&a,"random-seed",seed,seed_size);
    /* Cortex-A53 has no Apple CTRR: report that fact to native XNU startup. */
    prop(&a,"kernel-ctrr-to-be-enabled",&zero32,4);
    node(&a,1+(ramdisk_bytes!=0),0,"memory-map"); uint64_t kr[2]={dest,span}; prop(&a,"Kernel",kr,sizeof(kr));
    if(ramdisk_bytes) { uint64_t rd[2]={ramdisk,ramdisk_bytes}; prop(&a,"RAMDisk",rd,sizeof(rd)); }
    node(&a,0,1,"cpus");
    node(&a,6,0,"cpu0"); str(&a,"device_type","cpu"); str(&a,"state","running"); prop(&a,"reg",&zero32,4); prop(&a,"cpu-id",&zero32,4); prop(&a,"timebase-frequency",&freq,4); str(&a,"compatible","arm,cortex-a53");
    node(&a,2,0,"arm-io"); str(&a,"device_type","msm8953"); prop(&a,"ranges",r,sizeof(r));
    /* pmap_compute_max_asids() requires this node; absent properties select XNU defaults. */
    node(&a,0,0,"defaults");
    return a.failed?0:a.used;
}
