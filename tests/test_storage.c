/* SPDX-License-Identifier: BSD-2-Clause */
#include "../xnu/bsd/dev/a6plte/storage.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
enum { BLOCKS=4096 };
static uint8_t media[BLOCKS*512];
static unsigned reads,writes,flushes;
static uint64_t last_lba;
static uint32_t last_count;
static int read_disk(void *cookie,uint64_t lba,uint32_t n,void *buf) {
    assert(cookie==media && lba<BLOCKS && n<=BLOCKS-lba);
    ++reads;memcpy(buf,media+lba*512,(size_t)n*512);return 0;
}
static int write_disk(void *cookie,uint64_t lba,uint32_t n,const void *buf) {
    assert(cookie==media && lba<BLOCKS && n<=BLOCKS-lba);
    ++writes;last_lba=lba;last_count=n;memcpy(media+lba*512,buf,(size_t)n*512);return 0;
}
static int flush_disk(void *cookie) { assert(cookie==media);++flushes;return 0; }
static struct a6_blockdev disk={media,BLOCKS,read_disk,write_disk,flush_disk};
static void put32(uint8_t *p,uint32_t n) { for(unsigned i=0;i<4;++i)p[i]=(uint8_t)(n>>(i*8)); }
static void put64(uint8_t *p,uint64_t n) { put32(p,(uint32_t)n);put32(p+4,(uint32_t)(n>>32)); }
static unsigned stride=128;
static void entry(unsigned index,uint64_t first,uint64_t last,const char *name,uint64_t attrs) {
    uint8_t *p=media+1024+index*stride;memset(p,0,stride);
    p[0]=0xaf;p[16]=(uint8_t)(index+1);put64(p+32,first);put64(p+40,last);put64(p+48,attrs);
    for(unsigned i=0;name[i] && i<36;++i)p[56+i*2]=(uint8_t)name[i];
}
static void checksum_header(uint8_t *h) { put32(h+16,0);put32(h+16,a6_storage_crc32(h,92)); }
static void seal(void) {
    unsigned bytes=128*stride,sectors=bytes/512;
    memcpy(media+(BLOCKS-1-sectors)*512,media+1024,bytes);
    for(unsigned copy=0;copy<2;++copy) {
        uint8_t *p=media+(copy?BLOCKS-1:1)*512;memset(p,0,512);
        memcpy(p,"EFI PART",8);put32(p+8,0x10000);put32(p+12,92);
        put64(p+24,copy?BLOCKS-1:1);put64(p+32,copy?1:BLOCKS-1);
        put64(p+40,2+sectors);put64(p+48,BLOCKS-2-sectors);p[56]=0x42;
        put64(p+72,copy?BLOCKS-1-sectors:2);put32(p+80,128);put32(p+84,stride);
        put32(p+88,a6_storage_crc32(media+1024,bytes));checksum_header(p);
    }
}
static void fixture(unsigned size) {
    stride=size;memset(media,0,sizeof(media));reads=writes=flushes=0;
    media[510]=0x55;media[511]=0xaa;media[450]=0xee;put32(media+454,1);put32(media+458,BLOCKS-1);
    entry(0,512,3071,"userdata",0);entry(1,200,240,"boot",0);seal();
}
static void rejected(void) {
    struct a6_slice p={.first=9,.count=123,.writable=1};
    assert(a6_gpt_userdata(&disk,&p)!=0);
    assert(!p.disk && !p.count && !p.writable && writes==0);
}
int main(void) {
    assert(a6_storage_crc32("123456789",9)==0xcbf43926);
    assert(a6_storage_crc32(NULL,0)==0);
    struct a6_slice part;
    uint8_t data[1024],got[1024];memset(data,0x5a,sizeof(data));
    for(unsigned size=128;size<=512;size*=2) {
        fixture(size);assert(!a6_gpt_userdata(&disk,&part));
        assert(part.first==512 && part.count==2560 && !part.writable);
        unsigned before=reads;
        assert(a6_slice_io(&part,1,0,1,data)==A6_IO_READONLY && writes==0 && flushes==0);
        assert(a6_slice_io(&part,0,part.count,1,data)==A6_IO_INVALID);
        assert(a6_slice_io(&part,1,part.count-1,2,data)==A6_IO_INVALID);
        assert(a6_slice_io(&part,1,UINT64_MAX,1,data)==A6_IO_INVALID);
        assert(a6_slice_io(&part,0,0,UINT32_MAX,data)==A6_IO_INVALID);
        assert(a6_slice_io(&part,0,0,1,NULL)==A6_IO_INVALID && reads==before);
        assert(!a6_slice_io(&part,0,part.count,0,NULL));
        part.writable=1;
        uint32_t boot_crc=a6_storage_crc32(media,part.first*512);
        uint32_t tail_crc=a6_storage_crc32(media+(part.first+part.count)*512,(BLOCKS-part.first-part.count)*512);
        assert(!a6_slice_io(&part,1,part.count-2,2,data));
        assert(writes==1 && flushes==1 && last_lba==3070 && last_count==2);
        assert(!a6_slice_io(&part,0,part.count-2,2,got) && !memcmp(got,data,sizeof(data)));
        assert(a6_storage_crc32(media,part.first*512)==boot_crc);
        assert(a6_storage_crc32(media+(part.first+part.count)*512,(BLOCKS-part.first-part.count)*512)==tail_crc);
    }
    fixture(128);entry(0,512,3071,"userdata",UINT64_C(1)<<60);seal();
    assert(!a6_gpt_userdata(&disk,&part));part.writable=1;
    assert(a6_slice_io(&part,1,0,1,data)==A6_IO_READONLY && !writes);
    fixture(128);media[510]=0;rejected();
    fixture(128);media[466]=0x83;rejected(); /* Hybrid MBR. */
    fixture(128);media[512+90]^=1;rejected();
    fixture(128);media[(BLOCKS-1)*512+12]=0xff;rejected();
    fixture(128);media[1024+90]^=1;rejected();
    fixture(128);put64(media+512+24,2);checksum_header(media+512);rejected();
    fixture(128);put64(media+512+72,UINT64_MAX);checksum_header(media+512);rejected();
    fixture(128);put32(media+512+80,129);checksum_header(media+512);rejected();
    fixture(128);entry(2,300,350,"userdata",0);seal();rejected();
    fixture(128);entry(2,600,700,"other",0);seal();rejected(); /* Overlap with userdata. */
    fixture(128);entry(2,300,350,"other",0);media[1024+2*128+16]=1;seal();rejected(); /* Duplicate GUID. */
    fixture(128);entry(0,512,BLOCKS-1,"userdata",0);seal();rejected();
    fixture(128);entry(0,512,511,"userdata",0);seal();rejected();
    fixture(128);entry(0,512,3071,"userdataX",0);seal();rejected();
    fixture(128);media[(BLOCKS-33)*512+16]^=1;rejected(); /* Backup array differs. */
    puts("PASS: both GPT CRCs, table equality, names/GUIDs/overlap, readonly, overflow and userdata write confinement");
}
