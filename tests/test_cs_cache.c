/* SPDX-License-Identifier: BSD-2-Clause */
/* Real journal protocol with reset/torn-write fault injection. */
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include "cs_cache.h"
struct media { unsigned char bytes[256*1024]; uint64_t size; int fail_write,fail_sync; unsigned reads,writes,syncs; };
static struct media media, saved;
static unsigned char hashes[128*1024], loaded[128*1024];
static int read_at(void *cookie,uint64_t off,void *p,size_t n) {
    struct media *m=cookie; ++m->reads;
    if (off>m->size || n>m->size-off) return EIO;
    memcpy(p,m->bytes+off,n);return 0;
}
static int write_at(void *cookie,uint64_t off,const void *p,size_t n) {
    struct media *m=cookie; ++m->writes;
    assert(off<=sizeof(m->bytes) && n<=sizeof(m->bytes)-off);
    if (m->fail_write) return ENOSPC;
    memcpy(m->bytes+off,p,n); if (off+n>m->size) m->size=off+n;return 0;
}
static int resize(void *cookie,uint64_t n) {
    struct media *m=cookie;assert(n<=sizeof(m->bytes));
    if (m->fail_write) return ENOSPC;
    if (n>m->size) memset(m->bytes+m->size,0,n-m->size);
    m->size=n;return 0;
}
static int sync_media(void *cookie) {
    struct media *m=cookie; ++m->syncs; return m->fail_sync?EIO:0;
}
static struct a6_csc fresh(unsigned size,uint64_t limit) {
    struct a6_csc c={.io={&media,read_at,write_at,resize,sync_media,media.size},
        .hash_size=size,.limit=limit,.writable=1};
    for (unsigned i=0;i<32;++i) c.key[i]=(unsigned char)(i*7+1);
    return c;
}
int main(void) {
    for (unsigned h=20;h<=48;h+=h==20?12:16) {
        memset(&media,0,sizeof(media));
        uint64_t limit=2*A6_CSC_SOURCE_CHUNK+12345;
        size_t total=(size_t)((limit+4095)/4096*h),chunk=(size_t)(A6_CSC_SOURCE_CHUNK/4096*h);
        for (size_t i=0;i<total;++i) hashes[i]=(unsigned char)(i*117+i/4096);
        struct a6_csc c=fresh(h,limit);
        assert(!a6_csc_load(&c,loaded) && !c.position && media.syncs==1);
        assert(!a6_csc_save(&c,hashes,A6_CSC_SOURCE_CHUNK) && media.syncs==2);
        /* Simulate a restart after the FIRST checkpoint, before completion. */
        c=fresh(h,limit);memset(loaded,0,sizeof(loaded));
        assert(!a6_csc_load(&c,loaded) && c.position==A6_CSC_SOURCE_CHUNK);
        assert(!memcmp(loaded,hashes,chunk) && !loaded[chunk]);
        assert(!a6_csc_save(&c,hashes,2*A6_CSC_SOURCE_CHUNK));
        saved=media;
        assert(!a6_csc_save(&c,hashes,limit));
        c=fresh(h,limit);memset(loaded,0,sizeof(loaded));
        assert(!a6_csc_load(&c,loaded) && c.position==limit && !memcmp(loaded,hashes,total));
        assert(a6_csc_save(&c,hashes,limit)==EINVAL);
        /* Every possible torn length of the final record leaves 2 good chunks. */
        struct media complete=media;
        for (uint64_t n=saved.size;n<complete.size;++n) {
            media=complete;media.size=n;c=fresh(h,limit);
            assert(!a6_csc_load(&c,loaded) && c.position==2*A6_CSC_SOURCE_CHUNK);
        }
        media=complete;media.bytes[complete.size-1]^=0x80;c=fresh(h,limit);
        memset(loaded,0xa5,sizeof(loaded));
        assert(!a6_csc_load(&c,loaded) && c.position==2*A6_CSC_SOURCE_CHUNK);
        assert(!loaded[2*chunk] && !memcmp(loaded,hashes,2*chunk));
        /* A torn/corrupt intermediate record cannot expose valid later ones. */
        media=complete;media.bytes[512+512+chunk+13]^=1;c=fresh(h,limit);
        assert(!a6_csc_load(&c,loaded) && c.position==A6_CSC_SOURCE_CHUNK);
        assert(!a6_csc_save(&c,hashes,2*A6_CSC_SOURCE_CHUNK));
        assert(media.size==saved.size); /* stale suffix removed before resume */
        c=fresh(h,limit);assert(!a6_csc_load(&c,loaded) && c.position==2*A6_CSC_SOURCE_CHUNK);
        /* Different identity/CD/geometry never loads an earlier table. */
        media=complete;c=fresh(h,limit);c.key[0]^=1;
        assert(!a6_csc_load(&c,loaded) && !c.position && media.size==512);
        media=complete;c=fresh(h,limit+4096);
        assert(!a6_csc_load(&c,loaded) && !c.position);
        media=complete;c=fresh(h,limit);media.bytes[150]^=1;
        assert(!a6_csc_load(&c,loaded) && !c.position);
        /* Full disk/failed flush cannot advertise an uncommitted checkpoint. */
        media=saved;c=fresh(h,limit);assert(!a6_csc_load(&c,loaded));
        media.fail_write=1;assert(a6_csc_save(&c,hashes,limit)==ENOSPC && c.position==2*A6_CSC_SOURCE_CHUNK);
        media.fail_write=0;media.fail_sync=1;
        assert(a6_csc_save(&c,hashes,limit)==EIO && c.position==2*A6_CSC_SOURCE_CHUNK);
        /* Read-only boot can reuse an existing complete journal without writes. */
        media=complete;c=fresh(h,limit);c.writable=0;unsigned writes=media.writes;
        assert(!a6_csc_load(&c,loaded) && c.position==limit && writes==media.writes);
        c.key[0]^=1;assert(!a6_csc_load(&c,loaded) && !c.position && writes==media.writes);
        c=fresh(h,limit);c.position=0;
        assert(a6_csc_save(&c,hashes,1)==EINVAL);
        assert(a6_csc_save(&c,hashes,2*A6_CSC_SOURCE_CHUNK)==EINVAL);
        assert(a6_csc_save(&c,hashes,limit+1)==EINVAL);
    }
    struct a6_csc c=fresh(32,0);assert(a6_csc_load(&c,loaded)==EINVAL);
    c=fresh(32,UINT64_MAX);assert(a6_csc_load(&c,loaded)==EINVAL);
    c=fresh(49,4096);assert(a6_csc_load(&c,loaded)==EINVAL);
    puts("PASS: persistent hash journal, reboot/resume, all torn tail lengths, corruption, identity changes, full disk, fsync failure and readonly reuse");
}
