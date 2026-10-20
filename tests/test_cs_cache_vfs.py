#!/usr/bin/env python3
"""Run the actual VFS adapter with counted vnode/permission/I/O fault injection."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
native=(ROOT/'xnu/bsd/dev/a6plte/cs_cache_vfs.c').read_text()
native=native[native.index('struct a6_cs_cache {'):native.rindex('#endif')]
source=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <sys/types.h>
#include <time.h>
#include <openssl/sha.h>
#include "cs_cache.h"
#define FREAD 1
#define FWRITE 2
#define F_FULLFSYNC 51
#define VNODE_LOOKUP_NOFOLLOW 1
#define VNODE_LOOKUP_NOCROSSMOUNT 2
#define UIO_READ 0
#define UIO_WRITE 1
#define UIO_SYSSPACE 0
#define IO_UNIT 8
#define Z_WAITOK 1
#define Z_ZERO 2
#define LCK_GRP_DECLARE(n,s) int n __attribute__((unused))
#define LCK_MTX_DECLARE(n,g) int n
enum { va_fileid,va_data_size,va_modify_time,va_change_time,va_uid,va_mode,va_nlink };
struct vnode_attr {
 uint64_t active,supported,va_fileid,va_data_size,va_nlink;
 unsigned va_uid,va_mode;struct timespec va_modify_time,va_change_time;
};
struct vnode { char *v_name;struct vnode_attr attr;int mount,reg;struct vnode *parent; };
typedef struct vnode *vnode_t;
static struct vnode root,source_file,cache_file;
static vnode_t rootvnode=&root;
static int selected=1,readonly,symlink_file,getattr_error,missing_attr,fail_write,short_io,live,opens,closes,writes,syncs;
static char filename[96];
static unsigned char media[256*1024];
static void quiet(const char *p,...) { (void)p; }
#define printf quiet
#define VATTR_INIT(a) memset(a,0,sizeof(*(a)))
#define VATTR_WANTED(a,f) ((a)->active|=1u<<(f))
#define VATTR_IS_SUPPORTED(a,f) (((a)->supported&(1u<<(f)))!=0)
#define VATTR_SET(a,f,x) ((a)->f=(x),(a)->active|=1u<<(f))
static void *allocate(size_t n) { void *p=calloc(1,n);if(p)++live;return p; }
static void release(void *p) { assert(p);--live;free(p); }
#define kalloc_type(t,f) ((t *)allocate(sizeof(t)))
#define kfree_type(t,p) release(p)
static void lck_mtx_lock(int *p) { assert(!*p);*p=1; }
static void lck_mtx_unlock(int *p) { assert(*p);*p=0; }
static int vfs_context_kernel(void) { return 7; }
static int vfs_context_ucred(int c) { assert(c==7);return 9; }
static int vfs_context_proc(int c) { assert(c==7);return 11; }
static int vnode_isreg(vnode_t v) { return v->reg; }
static int vnode_mount(vnode_t v) { return v->mount; }
static vnode_t vnode_parent(vnode_t v) { return v->parent; }
static int vnode_getattr(vnode_t v,struct vnode_attr *a,int c) {
 assert(c==7);if(getattr_error)return EIO;
 *a=v->attr;if(missing_attr)a->supported=0;return 0;
}
static int vnode_setattr(vnode_t v,struct vnode_attr *a,int c) {
 assert(v==&cache_file && c==7 && (a->active&(1u<<va_data_size)));
 if(fail_write)return ENOSPC;
 assert(a->va_data_size<=sizeof(media));
 if(a->va_data_size>v->attr.va_data_size)
  memset(media+v->attr.va_data_size,0,a->va_data_size-v->attr.va_data_size);
 v->attr.va_data_size=a->va_data_size;return 0;
}
static int vnode_open(const char *path,int mode,int cmode,int flags,vnode_t *v,int ctx) {
 assert(ctx==7 && (mode&O_NOFOLLOW) && flags==(VNODE_LOOKUP_NOFOLLOW|VNODE_LOOKUP_NOCROSSMOUNT));
 assert(!strncmp(path,"/.a6cs4k-v2-",12) && strlen(path)==76);
 *v=NULL;if(symlink_file)return ELOOP;
 if(readonly && (mode&FWRITE))return EROFS;
 if(strcmp(filename,path)) {
  assert(!readonly && (mode&O_CREAT) && cmode==0600);
  strcpy(filename,path);memset(media,0,sizeof(media));cache_file.attr.va_data_size=0;
 }
 *v=&cache_file;++opens;return 0;
}
static int vnode_close(vnode_t v,int flags,int c) {
 assert(v==&cache_file && c==7 && (flags&FREAD));++closes;return 0;
}
static int vn_rdwr(int op,vnode_t v,char *p,int n,off_t off,int space,int flags,int cred,int *resid,int proc) {
 assert(v==&cache_file && n>=0 && off>=0 && space==UIO_SYSSPACE && cred==9 && proc==11);
 assert((uint64_t)off<=sizeof(media) && (uint64_t)n<=sizeof(media)-(uint64_t)off);
 *resid=short_io;
 if(op==UIO_READ) {
  if((uint64_t)off+n>v->attr.va_data_size)return EIO;
  memcpy(p,media+off,n);
 } else {
  assert(op==UIO_WRITE && flags==IO_UNIT && !readonly);
  if(fail_write)return ENOSPC;
  memcpy(media+off,p,n);++writes;
  if((uint64_t)off+n>v->attr.va_data_size)v->attr.va_data_size=(uint64_t)off+n;
 }
 return 0;
}
static int VNOP_IOCTL(vnode_t v,int command,void *p,int flags,int c) {
 assert(v==&cache_file && command==F_FULLFSYNC && !p && !flags && c==7);
 ++syncs;return 0;
}
int a6_userdata_root_selected(void) { return selected; }
''' + native + r'''
int main(void) {
 root.mount=1;
 source_file=(struct vnode){.v_name="dyld_shared_cache_arm64.44",.mount=1,.reg=1};
 source_file.attr=(struct vnode_attr){.supported=127,.va_fileid=41,.va_data_size=100000000,
  .va_modify_time={100,0},.va_change_time={101,0}};
 cache_file=(struct vnode){.v_name="cache",.mount=1,.reg=1,.parent=&root};
 cache_file.attr=(struct vnode_attr){.supported=127,.va_uid=0,.va_mode=0600,.va_nlink=1};
 const unsigned char cd[]={1,2,3,4};uint64_t position;
 const uint64_t limit=2*A6_CSC_SOURCE_CHUNK+17;
 unsigned char hashes[100000],loaded[100000];
 for(unsigned i=0;i<sizeof(hashes);++i)hashes[i]=(unsigned char)(i*119);
 struct a6_cs_cache *c=a6_cs_cache_open(&source_file,cd,sizeof(cd),0,limit,32,loaded,&position);
 assert(c && !position && syncs==1);
 assert(!a6_cs_cache_save(c,hashes,65536) && syncs==1); /* no partial checkpoint */
 assert(!a6_cs_cache_save(c,hashes,A6_CSC_SOURCE_CHUNK) && syncs==2);
 assert(!a6_cs_cache_close(c) && !live && opens==closes && !cache_lock);
 c=a6_cs_cache_open(&source_file,cd,sizeof(cd),0,limit,32,loaded,&position);
 assert(c && position==A6_CSC_SOURCE_CHUNK && !memcmp(loaded,hashes,32768));
 assert(!a6_cs_cache_save(c,hashes,2*A6_CSC_SOURCE_CHUNK));
 assert(!a6_cs_cache_save(c,hashes,limit));assert(!a6_cs_cache_close(c));
 readonly=1;int previous=writes;
 c=a6_cs_cache_open(&source_file,cd,sizeof(cd),0,limit,32,loaded,&position);
 assert(c && position==limit && !memcmp(loaded,hashes,65568) && writes==previous);
 assert(!a6_cs_cache_close(c));readonly=0;
 /* Changes during verification invalidate the journal and reject publication. */
 c=a6_cs_cache_open(&source_file,cd,sizeof(cd),0,limit,32,loaded,&position);assert(c);
 ++source_file.attr.va_modify_time.tv_sec;
 assert(a6_cs_cache_close(c)==ESTALE && !cache_file.attr.va_data_size);
 c=a6_cs_cache_open(&source_file,cd,sizeof(cd),0,limit,32,loaded,&position);
 assert(c && !position);fail_write=1;
 assert(a6_cs_cache_save(c,hashes,A6_CSC_SOURCE_CHUNK)==ENOSPC);
 assert(!a6_cs_cache_save(c,hashes,A6_CSC_SOURCE_CHUNK)); /* stop retrying unavailable disk */
 assert(!a6_cs_cache_close(c));fail_write=0;
 previous=writes;
 for(unsigned bad=0;bad<7;++bad) {
  cache_file.reg=bad!=0;cache_file.mount=bad==1?2:1;cache_file.parent=bad==2?NULL:&root;
  cache_file.attr.va_mode=bad==3?0666:0600;cache_file.attr.va_nlink=bad==4?2:1;
  cache_file.attr.va_uid=bad==5?501:0;symlink_file=bad==6;
  assert(!a6_cs_cache_open(&source_file,cd,sizeof(cd),0,limit,32,loaded,&position));
  assert(!position && !live && opens==closes && !cache_lock && writes==previous);
 }
 symlink_file=0;cache_file.reg=1;cache_file.mount=1;cache_file.parent=&root;
 cache_file.attr.va_mode=0600;cache_file.attr.va_nlink=1;cache_file.attr.va_uid=0;
 missing_attr=1;
 assert(!a6_cs_cache_open(&source_file,cd,sizeof(cd),0,limit,32,loaded,&position) && !live);
 missing_attr=0;source_file.mount=2;
 assert(!a6_cs_cache_open(&source_file,cd,sizeof(cd),0,limit,32,loaded,&position) && !live);
 source_file.mount=1;selected=0;
 assert(!a6_cs_cache_open(&source_file,cd,sizeof(cd),0,limit,32,loaded,&position) && !live);
 assert(opens==closes && !cache_lock);
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='cs-cache-vfs-',dir=ROOT/'artifacts') as temp:
    temp=Path(temp);(temp/'test.c').write_text(source)
    subprocess.run(['clang','-std=gnu17','-Wall','-Wextra','-Werror','-Wno-deprecated-declarations',
        '-fsanitize=address,undefined','-g','-I'+str(ROOT/'xnu/bsd/dev/a6plte'),str(temp/'test.c'),
        str(ROOT/'xnu/bsd/dev/a6plte/cs_cache.c'),'-lcrypto','-o',str(temp/'test')],check=True)
    subprocess.run([str(temp/'test')],check=True)
print('PASS: native VFS cache adapter, incremental flush/resume, source changes, readonly, ENOSPC, root/mount/mode/symlink/hardlink restrictions and balanced vnode/lock/allocation lifetimes')
