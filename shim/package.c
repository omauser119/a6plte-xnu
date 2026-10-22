/* SPDX-License-Identifier: BSD-2-Clause */
#include "package.h"
_Static_assert(sizeof(struct a6_xnu_package)==64,"package ABI");
int a6_package_parse(const void *data, uint64_t size, struct a6_xnu_package *h) {
    if(size<sizeof(*h)) return -1;
    const uint8_t *p=data; uint8_t *q=(void *)h;
    for(unsigned i=0;i<sizeof(*h);++i) q[i]=p[i];
    const char prefix[]="A6XNU0";
    for(unsigned i=0;i<6;++i) if(h->magic[i]!=prefix[i]) return -1;
    if(h->header!=64 || h->magic[7] || (h->version!=1 && h->version!=2) ||
       h->magic[6]!=(char)('0'+h->version)) return -1;
    if(!h->span || h->span>64*1024*1024 || (h->span&0x3fff) || (h->virt&0x3fff) ||
       h->virt<0xffff000000000000ULL || h->virt+h->span<h->virt ||
       h->entry<h->virt || h->entry-h->virt>=h->span || (h->entry&3) ||
       h->bytes!=size-64) return -1;
    if(h->version==1) {
        if(h->flags || h->ramdisk_bytes || h->bytes!=h->span) return -1;
    } else {
        if(h->flags!=1 || !h->ramdisk_bytes || h->ramdisk_bytes>64*1024*1024 ||
           (h->ramdisk_bytes&0xfff) || h->bytes!=h->span+h->ramdisk_bytes) return -1;
    }
    return 0;
}
int a6_package_layout(const struct a6_xnu_package *h,uint64_t allocation,uint64_t arena,struct a6_xnu_layout *l) {
    if((allocation&0x1fffff) || arena>A6_XNU_MAX_MEMORY || arena<0x200000 ||
       allocation>0x100000000ULL-arena) return -1;
    uint64_t padding=h->virt&0x1fffff;
    l->donated=arena-padding;
    if(h->span>l->donated || h->ramdisk_bytes>l->donated-h->span) return -1;
    uint64_t needed=h->span+0x14000+((h->ramdisk_bytes+0x3fff)&~0x3fffULL);
    if(needed>l->donated) return -1;
    l->kernel=allocation+padding;
    l->args=l->kernel+h->span;
    l->tree=l->args+0x4000;
    l->ramdisk=h->ramdisk_bytes ? l->tree+0x10000 : 0;
    l->top=l->kernel+needed;
    return 0;
}
