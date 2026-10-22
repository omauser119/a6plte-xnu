#!/usr/bin/env python3
"""Execute Apple's actual inline-xattr writer with the strict XNU copy guard."""
from pathlib import Path
import os
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
hfs=root/'reference/hfs/core'
text=(hfs/'hfs_xattr.c').read_text()
baseline=bool(os.environ.get('A6_HFS_XATTR_BASELINE'))
if baseline:
    text=subprocess.check_output(['git','-C',str(hfs),'show','HEAD:core/hfs_xattr.c'],text=True)
start=text.index('} else { /* Inline data */')
opening=text.index('{',start);end=opening+1;depth=1
while depth:
    depth+=(text[end]=='{')-(text[end]=='}');end+=1
inline=text[opening+1:end-1]
guard=(root/'xnu/osfmk/device/subrs.c').read_text()
start=guard.index('\n__memmove_chk(')+1;opening=guard.index('{',start);end=opening+1;depth=1
while depth:
    depth+=(guard[end]=='{')-(guard[end]=='}');end+=1
guard='void *\n'+guard[start:end].replace('__memmove_chk(', 'native_memmove_chk(',1)
bt=(hfs/'BTreesInternal.h').read_text(encoding='latin1')
start=bt.index('struct FSBufferDescriptor {');end=bt.index('};',start)+2
source=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
typedef char uuid_string_t[37];
#include "hfs_format.h"
typedef uint32_t ByteCount;
typedef uint32_t ItemCount;
''' + bt[start:end] + r'''
typedef struct FSBufferDescriptor FSBufferDescriptor;
typedef struct {const uint8_t *data;size_t size;int error;} *uio_t;
struct BTreeIterator {HFSPlusAttrKey key;};
struct hfsmount {int unused;};
struct vnop_setxattr_args {const char *a_name;};
static unsigned removals,inserts;static int allocation_error,removal_error;
static uint8_t *allocation;static size_t allocated;static int old_exists;
static const uint8_t *expected;static size_t expected_size;
static _Noreturn void panic(const char *format,...) {
    va_list ap;va_start(ap,format);vfprintf(stderr,format,ap);va_end(ap);fflush(stderr);_Exit(86);
}
#define __improbable(x) __builtin_expect(!!(x),0)
#define memmove_impl memmove
''' + guard + r'''
#undef bcopy
#define bcopy(src,dst,n) native_memmove_chk((dst),(src),(n),__builtin_object_size((dst),1))
static void *allocate(size_t size,int zero) {
    if(allocation_error)return NULL;
    assert(!allocation);allocation=malloc(size+32);assert(allocation);allocated=size;
    memset(allocation,0xa5,size+32);if(zero)memset(allocation+16,0,size);return allocation+16;
}
static void *hfs_malloc_data(size_t n){return allocate(n,0);}
static void *hfs_malloc_zero_data(size_t n){return allocate(n,1);}
static int uiomove(char *dst,size_t n,uio_t uio) {
    assert(uio && n<=uio->size);if(uio->error)return uio->error;memcpy(dst,uio->data,n);return 0;
}
static int remove_attribute_records(struct hfsmount *m,struct BTreeIterator *i) {
    (void)m;(void)i;++removals;assert(old_exists);if(removal_error)return removal_error;old_exists=0;return 0;
}
static int hfs_buildattrkey(uint32_t id,const char *name,HFSPlusAttrKey *key) {
    assert(id==42 && !strcmp(name,"com.test.inline"));memset(key,0,sizeof(*key));return 0;
}
static int BTInsertRecord(void *tree,struct BTreeIterator *i,FSBufferDescriptor *data,uint16_t len) {
    (void)tree;(void)i;++inserts;assert(!old_exists && data->itemCount==1 && data->itemSize==len);
    assert(len==16+expected_size+(expected_size&1) && len==allocated);
    HFSPlusAttrRecord *record=data->bufferAddress;
    assert(record->recordType==kHFSPlusAttrInlineData && record->attrData.attrSize==expected_size);
    assert(!record->attrData.reserved[0] && !record->attrData.reserved[1]);
    assert(!expected_size || !memcmp((uint8_t *)record+16,expected,expected_size));
    if(expected_size&1)assert(!*((uint8_t *)record+16+expected_size));
    return 0;
}
static int write_inline(const void *data_ptr,size_t attrsize,uio_t uio,int exists) {
    struct hfsmount mount={0},*hfsmp=&mount;
    struct BTreeIterator iter,*iterator=&iter;void *btfile=NULL;
    struct vnop_setxattr_args args={"com.test.inline"},*ap=&args;
    uint32_t target_id=42;FSBufferDescriptor btdata={0};
    HFSPlusAttrRecord *recp=NULL;size_t recp_size=0;int result=0;
''' + inline + r'''
exit:
    if(allocation){assert(recp==(void *)(allocation+16) && recp_size==allocated);
        for(unsigned i=0;i<16;++i)assert(allocation[i]==0xa5 && allocation[16+allocated+i]==0xa5);
        free(allocation);allocation=NULL;allocated=0;}
    return result;
}
int main(int argc,char **argv) {
    (void)argv;
    if(argc>1){uint8_t a[4]={},b[4]={};native_memmove_chk(a,b,3,2);assert(0);}
    _Static_assert(offsetof(HFSPlusAttrData,attrData)==16,"native payload offset");
    _Static_assert(sizeof(((HFSPlusAttrData *)0)->attrData)==2,"native placeholder");
    _Static_assert(sizeof(HFSPlusAttrData)==18,"unchanged disk format");
    const size_t lengths[]={37,0,1,2,3,16,255,256,4095,4096,8192,65517,65518};
    for(unsigned k=0;k<sizeof(lengths)/sizeof(lengths[0]);++k){
        size_t n=lengths[k];uint8_t *payload=malloc(n+1);assert(payload);
        for(size_t j=0;j<n;++j)payload[j]=(uint8_t)(j*29+n);
        expected=payload;expected_size=n;
        for(unsigned use_uio=0;use_uio<2;++use_uio)for(unsigned exists=0;exists<2;++exists){
            __typeof__(*(uio_t)0) io={payload,n,0};removals=inserts=0;old_exists=exists;
            assert(!write_inline(use_uio?NULL:payload,n,use_uio?&io:NULL,exists));
            assert(inserts==1 && removals==exists && !old_exists);
        }
        free(payload);
    }
    expected_size=37;uint8_t payload[37]={};expected=payload;
    __typeof__(*(uio_t)0) io={payload,sizeof(payload),EFAULT};
    removals=inserts=0;old_exists=1;
    assert(write_inline(NULL,37,&io,1)==EFAULT && old_exists && !removals && !inserts);
    assert(write_inline(NULL,37,NULL,1)==EPERM && old_exists && !removals && !inserts);
    allocation_error=1;assert(write_inline(payload,37,NULL,1)==ENOMEM && old_exists && !removals && !inserts);allocation_error=0;
    assert(write_inline(payload,65519,NULL,1)==E2BIG && old_exists && !removals && !inserts);
    assert(write_inline(payload,SIZE_MAX,NULL,1)==E2BIG && old_exists && !removals && !inserts);
    removal_error=EIO;assert(write_inline(payload,37,NULL,1)==EIO && old_exists && removals==1 && !inserts);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='hfs-inline-',dir=root/'artifacts') as directory:
    p=Path(directory);(p/'sys').mkdir();(p/'sys/appleapiopts.h').symlink_to(root/'xnu/bsd/sys/appleapiopts.h')
    (p/'test.c').write_text(source)
    subprocess.run(['clang','-std=gnu17','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function',
        '-fsanitize=address,undefined','-g','-I'+str(p),'-I'+str(hfs),str(p/'test.c'),'-o',str(p/'test')],check=True)
    result=subprocess.run([str(p/'test')],text=True,capture_output=True)
    if baseline:
        assert result.returncode==86 and '(2 < 37)' in result.stderr,result.stdout+result.stderr
        print('PASS: unmodified Apple inline-xattr writer reproduces the exact native (2 < 37) panic')
    else:
        assert result.returncode==0,result.stdout+result.stderr
        result=subprocess.run([str(p/'test'),'guard'],text=True,capture_output=True)
        assert result.returncode==86 and '(2 < 3)' in result.stderr,result.stdout+result.stderr
        print('PASS: actual HFS inline writer, strict native guard, 37-byte regression, kernel/UIO paths, record bounds/padding, 16-bit overflow and old-value preservation on failure')
