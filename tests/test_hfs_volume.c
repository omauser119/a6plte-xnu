/* SPDX-License-Identifier: BSD-2-Clause */
#include "../xnu/bsd/dev/a6plte/storage.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t primary[512],alternate[512];
static unsigned reads,writes,flushes,fail_read;
static uint64_t backup;
static void put16(uint8_t *p,unsigned x) { p[0]=(uint8_t)(x>>8);p[1]=(uint8_t)x; }
static void put32(uint8_t *p,uint32_t x) { put16(p,x>>16);put16(p+2,x); }
static int read_disk(void *cookie,uint64_t lba,uint32_t count,void *out) {
    assert(!cookie && count==1);++reads;
    if (fail_read==reads) return A6_IO_TIMEOUT;
    assert(lba==102 || lba==100+backup);
    memcpy(out,lba==102?primary:alternate,512);return 0;
}
static int write_disk(void *c,uint64_t l,uint32_t n,const void *p) {
    (void)c;(void)l;(void)n;(void)p;++writes;return A6_IO_ERROR;
}
static int flush_disk(void *c) { (void)c;++flushes;return A6_IO_ERROR; }
static struct a6_blockdev disk={NULL,1u<<24,read_disk,write_disk,flush_disk};
static struct a6_slice slice={&disk,100,1u<<20,0,1};
static void fixture(unsigned signature,unsigned version,unsigned block_size,unsigned blocks) {
    memset(primary,0,sizeof(primary));memset(alternate,0,sizeof(alternate));
    put16(primary,signature);put16(primary+2,version);put32(primary+4,1u<<8);
    put32(primary+40,block_size);put32(primary+44,blocks);put32(primary+48,blocks/2);
    memcpy(alternate,primary,512);backup=(uint64_t)block_size*blocks/512-2;
    reads=writes=flushes=fail_read=0;
}
static void reject(void) {
    struct a6_hfs_volume v={.bytes=1};
    assert(a6_hfs_volume_check(&slice,&v)!=0 && !v.bytes && !writes && !flushes);
}
int main(void) {
    struct a6_hfs_volume v;
    for (unsigned bs=512;bs<=65536;bs*=2) {
        fixture(0x482b,4,bs,64);
        assert(!a6_hfs_volume_check(&slice,&v));
        assert(v.bytes==(uint64_t)bs*64 && v.block_size==bs && v.signature==0x482b && reads==2);
        assert(!writes && !flushes && backup<slice.count-2);
    }
    fixture(0x4858,5,4096,64);assert(!a6_hfs_volume_check(&slice,&v));
    fixture(0x482b,4,4096,64);put32(primary+4,(1u<<8)|(1u<<13));put32(primary+12,4);
    assert(!a6_hfs_volume_check(&slice,&v));
    fixture(0x482b,4,4096,64);put32(primary+4,1u<<13);reject();
    fixture(0x482b,4,4096,64);put32(primary+4,1u<<13);put32(primary+12,64);reject();
    fixture(0x482b,4,4096,64);primary[0]=0;reject();
    fixture(0x482b,5,4096,64);reject();
    fixture(0x4858,4,4096,64);reject();
    fixture(0x4244,4,4096,64);reject(); /* Embedded/partitioned HFS is not a bare HFS+ root. */
    fixture(0x482b,4,4096,64);put32(primary+40,0);reject();
    fixture(0x482b,4,4096,64);put32(primary+40,768);reject();
    fixture(0x482b,4,4096,64);put32(primary+40,1u<<21);reject();
    fixture(0x482b,4,4096,64);put32(primary+44,0);reject();
    fixture(0x482b,4,4096,64);put32(primary+48,65);reject();
    fixture(0x482b,4,4096,64);put32(primary+44,0xffffffff);reject();
    fixture(0x482b,4,4096,64);alternate[0]=0;reject();
    fixture(0x482b,4,4096,64);put32(alternate+44,63);reject();
    fixture(0x482b,4,4096,64);put16(alternate,0x4858);put16(alternate+2,5);reject();
    for (unsigned n=1;n<=2;++n) {
        fixture(0x482b,4,4096,64);fail_read=n;
        assert(a6_hfs_volume_check(&slice,&v)==A6_IO_TIMEOUT && !v.bytes);
    }
    fixture(0x482b,4,4096,64);uint64_t old=slice.count;
    slice.count=7;reject();assert(!reads);
    slice.count=UINT64_MAX/512+1;reject();assert(!reads);slice.count=old;
    assert(a6_hfs_volume_check(NULL,&v)==A6_IO_INVALID);
    assert(a6_hfs_volume_check(&slice,NULL)==A6_IO_INVALID);
    puts("PASS: userdata HFS+/HFSX headers, copied-volume bounds, alternate geometry, journal bounds, failures and zero writes");
}
