/* SPDX-License-Identifier: BSD-2-Clause */
#include "fdt.h"
#include "package.h"
static uint32_t be32(const void *v) { const uint8_t *p=v; return (uint32_t)p[0]<<24|(uint32_t)p[1]<<16|(uint32_t)p[2]<<8|p[3]; }
static uint64_t cells(const uint8_t *p,unsigned n) { return n==2 ? (uint64_t)be32(p)<<32|be32(p+4) : be32(p); }
static int eq(const char *a,const char *b) { while(*a && *a==*b) { ++a;++b; } return *a==*b; }
static int has_string(const uint8_t *p,unsigned n,const char *s) {
    for(unsigned i=0;i<n;) { unsigned j=i; while(j<n && p[j]) ++j; if(j==n) return 0; if(eq((const char *)p+i,s)) return 1; i=j+1; } return 0;
}
struct node { unsigned ac,sc,pac,psc; int reserved,mem,fb,chosen; const uint8_t *reg; unsigned reglen; uint32_t w,h,stride,format; int disabled; };
static int add(struct range *r,unsigned *n,unsigned max,uint64_t b,uint64_t s) { if(!s) return 0; if(*n==max || b+s<b) return -1; r[(*n)++]=(struct range){b,s}; return 0; }
int platform_parse(const void *blob,struct platform *out) {
    const uint8_t *b=blob;
    if(be32(b)!=0xd00dfeed) return -1;
    uint32_t total=be32(b+4),so=be32(b+8),st=be32(b+12),ro=be32(b+16),ns=be32(b+32),sz=be32(b+36);
    if(total<40 || total>2*1024*1024 || so>total || sz>total-so || st>total || ns>total-st || ro>total || (ro&7)) return -1;
    *out=(struct platform){0};
    /* FDT reserve map, including firmware allocations outside reserved-memory. */
    for(;;ro+=16) { if(ro>total || total-ro<16) return -1; uint64_t a=cells(b+ro,2),n=cells(b+ro+8,2); if(!a&&!n) break; if(add(out->reserved,&out->nr_reserved,96,a,n)) return -1; }
    struct node stack[32]; int d=-1, found=0;
    const uint8_t *p=b+so,*end=p+sz;
    while(end-p>=4) {
        uint32_t token=be32(p); p+=4;
        if(token==1) {
            const uint8_t *name=p; while(p<end && *p) ++p; if(p==end || ++d>=32) return -1;
            uint64_t len=(uint64_t)(p-name)+1, al=(len+3)&~3ULL; if(al>(uint64_t)(end-name)) return -1; p=name+al;
            struct node *n=&stack[d]; *n=(struct node){.ac=2,.sc=1,.pac=2,.psc=1};
            if(d) { n->pac=stack[d-1].ac; n->psc=stack[d-1].sc; n->reserved=stack[d-1].reserved; }
            if(d==1 && eq((const char *)name,"reserved-memory")) n->reserved=1;
            if(d==1 && eq((const char *)name,"chosen")) n->chosen=1;
        } else if(token==3) {
            if(d<0 || end-p<8) return -1;
            unsigned nbytes=be32(p),off=be32(p+4); p+=8;
            uint64_t al=((uint64_t)nbytes+3)&~3ULL;
            if(al>(uint64_t)(end-p) || off>=ns) return -1;
            const char *key=(const char *)b+st+off;
            unsigned k=off; while(k<ns && b[st+k]) ++k; if(k==ns) return -1;
            struct node *n=&stack[d];
            if(eq(key,"#address-cells")) { if(nbytes!=4 || !be32(p)||be32(p)>2) return -1; n->ac=be32(p); }
            if(eq(key,"#size-cells")) { if(nbytes!=4 || be32(p)>2) return -1; n->sc=be32(p); }
            if(eq(key,"device_type") && has_string(p,nbytes,"memory")) n->mem=1;
            if(eq(key,"compatible") && has_string(p,nbytes,"simple-framebuffer")) n->fb=1;
            if(eq(key,"status") && !has_string(p,nbytes,"okay") && !has_string(p,nbytes,"ok")) n->disabled=1;
            if(eq(key,"reg")) { n->reg=p; n->reglen=nbytes; }
            if(nbytes==4) {
                if(eq(key,"width")) n->w=be32(p);
                if(eq(key,"height")) n->h=be32(p);
                if(eq(key,"stride")) n->stride=be32(p);
            }
            if(eq(key,"format")) {
                if(has_string(p,nbytes,"r8g8b8")) n->format=A6_RGB888;
                if(has_string(p,nbytes,"x8r8g8b8")) n->format=A6_XRGB8888;
                if(has_string(p,nbytes,"r5g6b5")) n->format=A6_RGB565;
            }
            if(n->chosen && (nbytes==4||nbytes==8)) {
                if(eq(key,"linux,initrd-start")) out->initrd_start=cells(p,nbytes/4);
                if(eq(key,"linux,initrd-end")) out->initrd_end=cells(p,nbytes/4);
            }
            if(n->chosen && eq(key,"rng-seed")) {
                unsigned size=nbytes<sizeof(out->rng_seed)?nbytes:sizeof(out->rng_seed);
                for(unsigned i=0;i<size;++i) out->rng_seed[i]=p[i];
                out->rng_seed_size=size;
            }
            p+=al;
        } else if(token==2) {
            if(d<0) return -1; struct node *n=&stack[d--];
            if(n->disabled || !n->reg || !(n->mem||n->reserved||n->fb)) continue;
            unsigned step=(n->pac+n->psc)*4;
            if(!n->psc || n->reglen%step) return -1;
            for(unsigned i=0;i<n->reglen;i+=step) {
                uint64_t a=cells(n->reg+i,n->pac),s=cells(n->reg+i+n->pac*4,n->psc);
                if(n->mem && add(out->ram,&out->nr_ram,16,a,s)) return -1;
                if((n->reserved||n->fb) && add(out->reserved,&out->nr_reserved,96,a,s)) return -1;
                if(n->fb) { if(found++ || a6_fb_init(&out->fb,(uintptr_t)a,s,n->w,n->h,n->stride,n->format)) return -1; }
            }
        } else if(token==9) return d==-1 && found==1 && out->nr_ram ? 0 : -1;
        else if(token!=4) return -1;
    }
    return -1;
}
static int overlap(uint64_t a,uint64_t n,struct range r) { return n && r.size && a<r.base+r.size && r.base<a+n; }
int platform_alloc(const struct platform *p,uint64_t size,uint64_t align,struct range image,uint64_t *result) {
    if(!p || !result || p->nr_ram>16 || p->nr_reserved>96 ||
       !size || !align || (align&(align-1)) || align>0x100000000ULL ||
       size>A6_XNU_MAX_MEMORY || image.size>UINT64_MAX-image.base) return -1;
    for(unsigned j=0;j<p->nr_reserved;++j)
        if(p->reserved[j].size>UINT64_MAX-p->reserved[j].base) return -1;
    for(unsigned i=0;i<p->nr_ram;++i) {
        uint64_t base=p->ram[i].base;
        if(p->ram[i].size>UINT64_MAX-base) return -1;
        uint64_t end=base+p->ram[i].size;
        if(end>0x100000000ULL) end=0x100000000ULL;
        if(base>=end) continue;
        uint64_t a=(base+align-1)&~(align-1);
        for(;a<end && size<=end-a;a+=align) {
            int bad=overlap(a,size,image);
            for(unsigned j=0;j<p->nr_reserved;++j) bad|=overlap(a,size,p->reserved[j]);
            if(p->initrd_end>p->initrd_start) bad|=overlap(a,size,(struct range){p->initrd_start,p->initrd_end-p->initrd_start});
            if(!bad) { *result=a; return 0; }
        }
    }
    return -1;
}
int platform_alloc_xnu(const struct platform *p,struct range image,struct range *out) {
    if(!out) return -1;
    *out=(struct range){0};
    if(!p || p->nr_reserved>=96 || !p->fb.base || !p->fb.size ||
       p->fb.size>UINT64_MAX-(uintptr_t)p->fb.base) return -1;
    struct platform bounded=*p;
    /* Native start.s installs the framebuffer's identity L2 table separately.
     * Until that map is retired, kernel RAM must use different L1 entries;
     * otherwise the framebuffer mapping would replace a live kernel table.
     * Reserve the covering 1-GiB entries, not just the visible pixel bytes. */
    uint64_t fb_base=(uintptr_t)p->fb.base,fb_end=fb_base+p->fb.size;
    uint64_t first=fb_base&~UINT64_C(0x3fffffff);
    if(fb_end>UINT64_MAX-0x3fffffff) return -1;
    uint64_t end=(fb_end+0x3fffffff)&~UINT64_C(0x3fffffff);
    bounded.reserved[bounded.nr_reserved++]=(struct range){first,end-first};
    /* Use only a whole verified window within a real bank, never firmware
     * holes. Keep the old 256-MiB fallback on fragmented/smaller devices. */
    for(uint64_t size=A6_XNU_MAX_MEMORY;size>=0x10000000;size-=0x08000000) {
        uint64_t address;
        if(!platform_alloc(&bounded,size,0x200000,image,&address)) {
            *out=(struct range){address,size};return 0;
        }
    }
    return -1;
}
