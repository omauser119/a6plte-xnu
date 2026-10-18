#include "../xnu/libkern/crypto/a6plte_kmem_rng.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static unsigned hex(char c) { return c>='a' ? (unsigned)(c-'a'+10) : (unsigned)(c-'0'); }
static void store64(uint8_t *p,uint64_t v) {
    for(unsigned i=0;i<8;++i) p[i]=(uint8_t)(v>>(i*8));
}
int main(void) {
    uint8_t seed[44]={0}, actual[64], expected[64];
    for(unsigned i=0;i<32;++i) seed[i]=(uint8_t)i;
    seed[35]=9; seed[39]=0x4a;
    struct a6_kmem_rng r;
    a6_kmem_rng_init(&r,seed);
    r.state[12]=1;
    /* RFC 8439 section 2.3.2, ChaCha20 block-function test vector. */
    const char *kat=
        "10f1e7e4d13b5915500fdd1fa32071c4c7d1f4c733c068030422aa9ac3d46c4e"
        "d2826446079faa0914c2d705d98b02a2b5129cd1de164eb9cbd083e8a2503c4e";
    for(unsigned i=0;i<64;++i) expected[i]=(uint8_t)(hex(kat[2*i])*16+hex(kat[2*i+1]));
    a6_kmem_rng_generate(&r,actual,sizeof(actual));
    assert(!memcmp(actual,expected,sizeof(actual)));

    /* Partial calls must retain unused bytes across block boundaries. */
    uint8_t whole[1025], parts[1025];
    struct a6_kmem_rng other;
    a6_kmem_rng_init(&r,seed); a6_kmem_rng_init(&other,seed);
    a6_kmem_rng_generate(&r,whole,sizeof(whole));
    size_t off=0;
    const size_t chunks[]={1,63,65,7,128,3,256,502};
    for(unsigned i=0;i<sizeof(chunks)/sizeof(chunks[0]);++i) {
        a6_kmem_rng_generate(&other,parts+off,chunks[i]); off+=chunks[i];
    }
    assert(off==sizeof(parts) && !memcmp(whole,parts,sizeof(parts)));
    struct a6_kmem_rng before=other;
    a6_kmem_rng_generate(&other,NULL,0);
    assert(!memcmp(&before,&other,sizeof(other)));

    /* Counter rollover must not repeat a block after the low 32 bits wrap. */
    a6_kmem_rng_init(&r,seed);
    r.state[12]=UINT32_MAX; r.state[13]=UINT32_MAX; r.state[14]=17;
    a6_kmem_rng_generate(&r,actual,sizeof(actual));
    assert(r.state[12]==0 && r.state[13]==0 && r.state[14]==18);

    /* Force rejection of a sample in the incomplete residue range. */
    uint64_t value=123;
    a6_kmem_rng_init(&r,seed); r.used=0;
    store64(r.block,5); store64(r.block+8,23);
    assert(a6_kmem_rng_uniform(&r,10,&value)==0 && value==3);
    r.used=0; store64(r.block,0); store64(r.block+8,UINT64_MAX-1);
    assert(a6_kmem_rng_uniform(&r,UINT64_MAX,&value)==0 && value==UINT64_MAX-1);
    value=123;
    assert(a6_kmem_rng_uniform(&r,0,&value)==-1 && value==123);
    const uint64_t bounds[]={1,2,3,64,UINT64_C(0x8000000000000001),UINT64_MAX};
    a6_kmem_rng_init(&r,seed);
    for(unsigned i=0;i<sizeof(bounds)/sizeof(bounds[0]);++i) {
        for(unsigned j=0;j<256;++j) {
            assert(a6_kmem_rng_uniform(&r,bounds[i],&value)==0 && value<bounds[i]);
        }
    }
    assert(sizeof(r)<=256);
    puts("PASS: kmem RNG RFC 8439 vector, stream boundaries, counter carry and unbiased bounds");
}
