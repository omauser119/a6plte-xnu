#include "../shim/apple_dt.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned nodes, ctrr, seed_seen, kernel_seen, ramdisk_seen;
static uint8_t seed[256];
static uint32_t u32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static uint64_t u64(const uint8_t *p) { return u32(p) | (uint64_t)u32(p+4)<<32; }

/* Independent bounded reader: verify counts, padding and native property values. */
static size_t read_node(const uint8_t *b, size_t size, size_t off, unsigned depth) {
    assert(depth<8 && off+8<=size);
    unsigned props=u32(b+off), kids=u32(b+off+4);
    assert(props && props<=16 && kids<=8);
    off+=8; ++nodes;
    char name[32]={0};
    for(unsigned i=0;i<props;++i) {
        assert(off+36<=size && memchr(b+off,0,32));
        const char *key=(const char *)(b+off);
        unsigned len=u32(b+off+32);
        off+=36;
        assert(len<=size-off);
        const uint8_t *data=b+off;
        if(i==0) {
            assert(!strcmp(key,"name") && len && len<=sizeof(name) && data[len-1]==0);
            memcpy(name,data,len);
        }
        if(!strcmp(name,"chosen") && !strcmp(key,"kernel-ctrr-to-be-enabled")) {
            assert(len==4 && u32(data)==0); ++ctrr;
        }
        if(!strcmp(name,"chosen") && !strcmp(key,"random-seed")) {
            assert(len==sizeof(seed) && !memcmp(data,seed,len)); ++seed_seen;
        }
        if(!strcmp(name,"memory-map") && !strcmp(key,"Kernel")) {
            assert(len==16 && u64(data)==0x44a04000 && u64(data+8)==0x1400000); ++kernel_seen;
        }
        if(!strcmp(name,"memory-map") && !strcmp(key,"RAMDisk")) {
            assert(len==16 && u64(data)==0x47000000 && u64(data+8)==0x2000000); ++ramdisk_seen;
        }
        off+=len;
        unsigned pad=(4-len%4)%4;
        assert(pad<=size-off);
        for(unsigned j=0;j<pad;++j) assert(b[off+j]==0);
        off+=pad;
    }
    if(!strcmp(name,"chosen")) assert(props==7 && kids==1);
    for(unsigned i=0;i<kids;++i) off=read_node(b,size,off,depth+1);
    return off;
}

int main(void) {
    uint8_t storage[4096+32];
    for(unsigned i=0;i<sizeof(seed);++i) seed[i]=(uint8_t)i;
    for(unsigned mode=0;mode<2;++mode) {
        uint64_t rd=mode ? 0x47000000 : 0,bytes=mode ? 0x2000000 : 0;
        nodes=ctrr=seed_seen=kernel_seen=ramdisk_seen=0;
        memset(storage,0xa5,sizeof(storage));
        unsigned size=a6_make_adt(storage+16,4096,0x44a04000,0x7ffc000,0x1400000,19200000,seed,sizeof(seed),rd,bytes);
        assert(size && size<4096);
        assert(read_node(storage+16,size,0,0)==size);
        assert(nodes==7 && ctrr==1 && seed_seen==1 && kernel_seen==1 && ramdisk_seen==mode);
        for(unsigned cap=0;cap<size;++cap) {
            memset(storage,0xa5,sizeof(storage));
            assert(a6_make_adt(storage+16,cap,0x44a04000,0x7ffc000,0x1400000,19200000,seed,sizeof(seed),rd,bytes)==0);
            for(unsigned i=0;i<16;++i) assert(storage[i]==0xa5);
            for(unsigned i=16+cap;i<sizeof(storage);++i) assert(storage[i]==0xa5);
        }
    }
    puts("PASS: Apple DT counts, CTRR absent, boot entropy, kernel range and every truncated capacity");
}
