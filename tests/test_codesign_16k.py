#!/usr/bin/env python3
"""Exercise native CodeDirectory validation and 4K faults against 16K signatures."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / 'xnu/bsd/kern/ubc_subr.c').read_text()

def function(name, result):
    start = text.index('\n' + name + '(') + 1
    opening = text.index('{', start)
    end, depth = opening + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return result + '\n' + text[start:end] + '\n'

source = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stdarg.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <errno.h>
#include <openssl/sha.h>
static void host_sha1_init(void *p) { (void)SHA1_Init(p); }
static void host_sha1_update(void *p,const void *d,size_t n) { (void)SHA1_Update(p,d,n); }
static void host_sha1_final(void *d,void *p) { (void)SHA1_Final(d,p); }
static void host_sha256_init(void *p) { (void)SHA256_Init(p); }
static void host_sha256_update(void *p,const void *d,size_t n) { (void)SHA256_Update(p,d,n); }
static void host_sha256_final(void *d,void *p) { (void)SHA256_Final(d,p); }
static void host_sha384_init(void *p) { (void)SHA384_Init(p); }
static void host_sha384_update(void *p,const void *d,size_t n) { (void)SHA384_Update(p,d,n); }
static void host_sha384_final(void *d,void *p) { (void)SHA384_Final(d,p); }
#define SHA1_Init host_sha1_init
#define SHA1_Update host_sha1_update
#define SHA1_Final host_sha1_final
#define SHA256_Init host_sha256_init
#define SHA256_Update host_sha256_update
#define SHA256_Final host_sha256_final
#define SHA384_Init host_sha384_init
#define SHA384_Update host_sha384_update
#define SHA384_Final host_sha384_final
#define __enum_decl(name, type, ...) typedef type name; enum __VA_ARGS__
#include "kern/cs_blobs.h"
#define A6PLTE 1
#define CRYPTO_SHA2 1
#define PAGE_SHIFT 12
#define PAGE_SHIFT_4K 12
#define FOURK_PAGE_SIZE 4096
#define TRUE 1
#define FALSE 0
#define MIN(a,b) ((a)<(b)?(a):(b))
#define CS_VALIDATE_TAINTED 1
#define CS_VALIDATE_NX 2
#define EBADEXEC 85
#define Z_WAITOK 1
#define Z_ZERO 2
#define UIO_READ 0
#define UIO_SYSSPACE 0
#define SHA1_CTX SHA_CTX
#define SHA384_CTX SHA512_CTX
#define SHA1Init SHA1_Init
#define SHA1Update SHA1_Update
#define SHA1Final SHA1_Final
#define OSSwapBigToHostInt64(x) __builtin_bswap64(x)
#define CAST_DOWN(t,x) ((t)(uintptr_t)(x))
typedef int boolean_t;
typedef size_t vm_size_t;
typedef uintptr_t vm_offset_t;
typedef void *memory_object_t;
typedef uint64_t memory_object_offset_t;
static int cs_debug;
static unsigned long cs_validate_page_no_hash, cs_validate_page_bad_hash;
static void quiet(const char *format, ...) { (void)format; }
#define printf quiet
#define panic(...) abort()
''' + text[text.index('typedef void (*cs_md_init)'):text.index('uint8_t\ncs_hash_type(')] + '\n' + text[text.index('static const struct cs_hash cs_hash_sha1'):text.index('/*\n * Choose among different hash algorithms.')] + r'''
struct cs_blob {
 struct cs_blob *csb_next;
 off_t csb_base_offset, csb_start_offset, csb_end_offset;
 vm_size_t csb_mem_size;
 vm_offset_t csb_mem_offset;
 void *csb_mem_kaddr;
 const struct cs_hash *csb_hashtype;
 int csb_hash_pageshift, csb_hash_firstlevel_pageshift;
 unsigned char *csb_a6_4k_hashes;
 vm_size_t csb_a6_4k_hash_bytes;
 const CS_CodeDirectory *csb_cd;
};
struct vnode { char *v_name; unsigned char *data; size_t size; };
static int fail_read, short_read, fail_alloc, allocations, live_allocations;
static void *kalloc_data(size_t n,int flags) {
 if (++allocations==fail_alloc) return NULL;
 void *p=(flags & Z_ZERO)?calloc(1,n):malloc(n);
 if (p) ++live_allocations;
 return p;
}
static void kfree_data(void *p,size_t n) { (void)n; assert(p); --live_allocations; free(p); }
static int vfs_context_current(void) { return 0; }
static int kauth_cred_get(void) { return 0; }
static int current_proc(void) { return 0; }
static int vnode_size(struct vnode *vp,off_t *n,int ctx) { (void)ctx;*n=vp->size;return 0; }
static int vn_rdwr(int op,struct vnode *vp,char *p,int n,off_t off,int space,int flags,int cred,int *resid,int proc) {
 (void)op;(void)space;(void)flags;(void)cred;(void)proc;
 assert(off>=0 && (uint64_t)off<=vp->size && (uint64_t)n<=vp->size-(uint64_t)off);
 if (fail_read) return EIO;
 memcpy(p,vp->data+off,n);*resid=short_read;return 0;
}
''' + function('cs_valid_range', 'static boolean_t') + function('hashes', 'static const unsigned char *') + function('cs_validate_codedirectory', 'static int') + function('a6_cs_slot_hash', 'static const unsigned char *') + function('a6_cs_prepare_4k_hashes', 'static int') + function('cs_validate_hash', 'static boolean_t') + r'''
static unsigned char cd_storage[4096], disk[200000];
static struct vnode vnode={"fixture",disk,sizeof(disk)};
static struct cs_blob blob;
static CS_CodeDirectory *cd=(void *)cd_storage;
static void cleanup(void) {
 if(blob.csb_a6_4k_hashes) kfree_data(blob.csb_a6_4k_hashes,blob.csb_a6_4k_hash_bytes);
 blob.csb_a6_4k_hashes=NULL;blob.csb_a6_4k_hash_bytes=0;
 assert(live_allocations==0);
}
static void digest(const struct cs_hash *md,const void *p,size_t n,void *out) {
 union cs_hash_union ctx;md->cs_init(&ctx);md->cs_update(&ctx,p,n);md->cs_final(out,&ctx);
}
static void fixture(const struct cs_hash *md,unsigned shift,unsigned limit) {
 memset(cd_storage,0,sizeof(cd_storage));memset(&blob,0,sizeof(blob));
 for(unsigned i=0;i<sizeof(disk);++i) disk[i]=(unsigned char)(i*137+i/65536);
 unsigned page=1u<<shift,count=(limit+page-1)/page;
 cd->magic=htonl(CSMAGIC_CODEDIRECTORY);cd->length=htonl(1024+count*md->cs_size);
 cd->version=htonl(CS_SUPPORTSCODELIMIT64);cd->hashOffset=htonl(1024);
 cd->hashSize=md->cs_size;cd->hashType=md->cs_type;cd->pageSize=shift;
 cd->codeLimit=htonl(limit);cd->nCodeSlots=htonl(count);
 blob.csb_base_offset=4096;blob.csb_end_offset=(limit+page-1)&~(page-1);
 blob.csb_cd=cd;blob.csb_mem_kaddr=cd_storage;blob.csb_mem_size=sizeof(cd_storage);
 blob.csb_hash_pageshift=shift;blob.csb_hashtype=md;
 for(unsigned i=0;i<count;++i) {
  unsigned char d[CS_HASH_MAX_SIZE];
  digest(md,disk+4096+i*page,MIN(page,limit-i*page),d);
  memcpy(cd_storage+1024+i*md->cs_size,d,md->cs_size);
 }
 allocations=fail_alloc=fail_read=short_read=0;
}
static void fault(unsigned offset,int expected_valid,unsigned expected_taint) {
 unsigned char *page=malloc(4096);assert(page);
 memcpy(page,disk+blob.csb_base_offset+offset,4096);
 vm_size_t processed=0;unsigned tainted=0;
 assert(cs_validate_hash(&blob,NULL,blob.csb_base_offset+offset,page,&processed,&tainted)==expected_valid);
 assert(tainted==expected_taint);
 assert(processed==(expected_valid?4096:0));
 free(page);
}
int main(void) {
 (void)oop_jit_conversion;
 const struct cs_hash *algorithms[]={&cs_hash_sha1,&cs_hash_sha256,&cs_hash_sha256_truncate,&cs_hash_sha384};
 for(unsigned a=0;a<4;++a) {
  const struct cs_hash *md=algorithms[a];
  fixture(md,14,81920+1234);
  assert(cs_validate_codedirectory(cd,sizeof(cd_storage))==0);
  unsigned char original[4096];memcpy(original,cd_storage,sizeof(original));
  assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==0);
  assert(memcmp(original,cd_storage,sizeof(original))==0);
  for(unsigned off=0;off<81920+1234;off+=4096) fault(off,TRUE,off>=81920?CS_VALIDATE_NX:0);
  for(unsigned quarter=0;quarter<4;++quarter) {
   unsigned off=quarter*4096;disk[4096+off+43]^=1;
   fault(off,TRUE,CS_VALIDATE_TAINTED);disk[4096+off+43]^=1;
  }
  cleanup();
  for(unsigned quarter=0;quarter<4;++quarter) {
   fixture(md,14,65536);disk[4096+quarter*4096+43]^=1;
   assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==EBADEXEC);cleanup();
  }
  fixture(md,14,16384+8193);
  assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==0);
  fault(16384,TRUE,CS_VALIDATE_NX);fault(20480,TRUE,CS_VALIDATE_NX);fault(24576,TRUE,CS_VALIDATE_NX);cleanup();
  fixture(md,12,16384);assert(cs_validate_codedirectory(cd,sizeof(cd_storage))==0);
  assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==0 && !blob.csb_a6_4k_hashes);
  for(unsigned off=0;off<16384;off+=4096) fault(off,TRUE,0);
  fixture(md,15,65536);assert(cs_validate_codedirectory(cd,sizeof(cd_storage))==EBADEXEC);
  assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==EBADEXEC);
 }
 fixture(&cs_hash_sha256,14,65536);cd->nCodeSlots=0;
 assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==EBADEXEC);
 fixture(&cs_hash_sha256,14,65536);blob.csb_base_offset=-1;
 assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==EBADEXEC);
 fixture(&cs_hash_sha256,14,65536);vnode.size=5000;
 assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==EBADEXEC);vnode.size=sizeof(disk);
 for(unsigned fail=1;fail<=2;++fail) {
  fixture(&cs_hash_sha256,14,65536);fail_alloc=fail;
  assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==ENOMEM);cleanup();
 }
 fixture(&cs_hash_sha256,14,65536);fail_read=1;
 assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==EIO);cleanup();
 fixture(&cs_hash_sha256,14,65536);short_read=1;
 assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==EIO);cleanup();
 fixture(&cs_hash_sha256,14,65536);
 SC_Scatter *s=(void *)(cd_storage+512);cd->scatterOffset=htonl(512);
 s[0].base=0;s[0].count=htonl(1);s[1].base=htonl(2);s[1].count=htonl(1);
 memcpy(cd_storage+1056,cd_storage+1088,32);cd->nCodeSlots=htonl(2);
 assert(cs_validate_codedirectory(cd,sizeof(cd_storage))==0);
 assert(a6_cs_prepare_4k_hashes(&vnode,&blob)==0);
 fault(0,TRUE,0);fault(16384,FALSE,0);fault(32768,TRUE,0);fault(49152,FALSE,0);cleanup();
 assert(live_allocations==0);
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='codesign-16k-', dir=ROOT / 'artifacts') as tmp:
    tmp = Path(tmp)
    (tmp / 'test.c').write_text(source)
    subprocess.run(['clang', '-std=gnu17', '-Wall', '-Wextra', '-Werror',
                    '-Wno-deprecated-declarations', '-fsanitize=address,undefined', '-g',
                    '-I' + str(ROOT / 'xnu/osfmk'), str(tmp / 'test.c'), '-lcrypto',
                    '-o', str(tmp / 'test')], check=True)
    subprocess.run([str(tmp / 'test')], check=True)
print('16K signatures: SHA1/SHA256/truncated-SHA256/SHA384, 4K faults, edits, partial NX, scatter gaps, I/O/allocation failures passed')
