#!/usr/bin/env python3
"""Exercise the actual BSD strategy against bounded in-memory GPT slice I/O."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/'xnu/bsd/dev/a6plte/userdata.c').read_text()
def function(name,result):
    start=text.index(name+'(')
    opening=text.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return result+'\n'+text[start:end]+'\n'

source=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include "storage.h"
typedef char *caddr_t;
typedef int64_t daddr64_t;
typedef unsigned u_int;
enum { B_READ=1, BLOCKS=16384 };
struct buffer { uint32_t count,resid;daddr64_t block;int flags,minor,error,done,mapped;char *data; };
typedef struct buffer *buf_t;
static unsigned char media[BLOCKS*512];
static unsigned reads,writes,flushes,yields,fail_read;
static int published=1,a6_emmc_lock;
static uint32_t buf_count(buf_t b) { return b->count; }
static daddr64_t buf_blkno(buf_t b) { return b->block; }
static int buf_flags(buf_t b) { return b->flags; }
static int buf_device(buf_t b) { return b->minor; }
static int minor(int dev) { return dev; }
static void buf_setresid(buf_t b,uint32_t n) { b->resid=n; }
static void buf_setcount(buf_t b,uint32_t n) { b->count=n; }
static void buf_seterror(buf_t b,int e) { b->error=e; }
static int buf_map(buf_t b,caddr_t *p) { assert(!b->mapped);b->mapped=1;*p=b->data;return 0; }
static void buf_unmap(buf_t b) { assert(b->mapped);b->mapped=0; }
static void buf_biodone(buf_t b) { assert(!b->mapped);++b->done; }
static void lck_mtx_lock(int *p) { assert(!*p);*p=1; }
static void lck_mtx_unlock(int *p) { assert(*p);*p=0; }
static int lck_mtx_yield(int *p) { assert(*p);++yields;return 0; }
static int disk_read(void *p,uint64_t lba,uint32_t n,void *out) {
    assert(p==media && lba<BLOCKS && n<=BLOCKS-lba && n<=A6_EMMC_READ_BATCH);++reads;
    if(reads==fail_read)return A6_IO_ERROR;
    memcpy(out,media+lba*512,(size_t)n*512);return 0;
}
static int disk_write(void *p,uint64_t lba,uint32_t n,const void *in) {
    assert(p==media && lba<BLOCKS && n<=BLOCKS-lba);++writes;
    memcpy(media+lba*512,in,(size_t)n*512);return 0;
}
static int disk_flush(void *p) { assert(p==media);++flushes;return 0; }
static struct a6_blockdev disk={media,BLOCKS,disk_read,disk_write,disk_flush};
static struct a6_slice userdata={.disk=&disk,.first=1024,.count=8192,.writable=1};
''' + function('to_errno','static int') + function('strategy','static void') + function('bound_transfer','static u_int') + r'''
int main(void) {
    for(size_t i=0;i<sizeof(media);++i) media[i]=(unsigned char)(i*73+i/512);
    const uint32_t length=1024*1024;unsigned char *memory=malloc(length+32);assert(memory);
    memset(memory,0xa5,length+32);
    struct buffer b={.count=length,.block=9,.flags=B_READ,.data=(char *)memory+16};
    strategy(&b);assert(!b.error && !b.resid && b.done==1 && reads==16 && yields==15);
    assert(!memcmp(memory+16,media+(userdata.first+9)*512,length));
    for(unsigned i=0;i<16;++i)assert(memory[i]==0xa5 && memory[16+length+i]==0xa5);
    uint32_t prefix=a6_storage_crc32(media,userdata.first*512);
    uint32_t suffix=a6_storage_crc32(media+(userdata.first+userdata.count)*512,
        sizeof(media)-(userdata.first+userdata.count)*512);
    b=(struct buffer){.count=length,.block=(daddr64_t)userdata.count-length/512,.data=(char *)memory+16};
    strategy(&b);assert(!b.error && !b.resid && b.done==1 && writes==1 && flushes==1);
    assert(!memcmp(memory+16,media+(userdata.first+userdata.count)*512-length,length));
    assert(a6_storage_crc32(media,userdata.first*512)==prefix);
    assert(a6_storage_crc32(media+(userdata.first+userdata.count)*512,
        sizeof(media)-(userdata.first+userdata.count)*512)==suffix);
    ++b.block;b.done=0;b.error=0;strategy(&b);
    assert(b.error==EINVAL && b.resid==length && b.done==1 && writes==1);
    b=(struct buffer){.count=length,.block=1,.data=(char *)memory+16};userdata.writable=0;
    strategy(&b);assert(b.error==EROFS && writes==1 && flushes==1);userdata.writable=1;
    b=(struct buffer){.count=65537,.block=1,.flags=B_READ,.data=(char *)memory+16};
    strategy(&b);assert(b.error==EINVAL && b.resid==65537 && reads==16);
    b=(struct buffer){.count=512,.block=-1,.flags=B_READ,.data=(char *)memory+16};
    strategy(&b);assert(b.error==EINVAL && reads==16);
    b=(struct buffer){.count=512,.block=(daddr64_t)userdata.count,.flags=B_READ,.data=(char *)memory+16};
    strategy(&b);assert(!b.error && b.resid==512 && b.done==1 && reads==16);
    b=(struct buffer){.count=length,.block=(daddr64_t)userdata.count-1,.flags=B_READ,.data=(char *)memory+16};
    strategy(&b);assert(b.error==EINVAL && b.resid==length && b.done==1 && reads==16 && yields==15);
    memset(memory,0xa5,length+32);fail_read=18;
    b=(struct buffer){.count=length,.block=9,.flags=B_READ,.data=(char *)memory+16};
    strategy(&b);assert(b.error==EIO && b.resid==length-65536 && b.done==1 && reads==18 && yields==16);
    assert(!memcmp(memory+16,media+(userdata.first+9)*512,65536));
    for(unsigned i=16+65536;i<length+32;++i)assert(memory[i]==0xa5);
    b=(struct buffer){.count=length};assert(bound_transfer(&b)==65536 && b.count==65536);
    free(memory);return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='userdata-strategy-',dir=ROOT/'artifacts') as temp:
    temp=Path(temp);(temp/'test.c').write_text(source)
    subprocess.run(['clang','-std=gnu17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',
        '-I'+str(ROOT/'xnu/bsd/dev/a6plte'),str(temp/'test.c'),str(ROOT/'xnu/bsd/dev/a6plte/gpt.c'),
        '-o',str(temp/'test')],check=True)
    subprocess.run([str(temp/'test')],check=True)
print('PASS: native strategy bounded reads/yield/partial-error residual, 1-MiB writes, buffer guards, whole-request bounds, readonly, EOF and raw I/O cap')
