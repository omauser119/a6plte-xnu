#!/usr/bin/env python3
"""Exercise actual Apple catalog writers/readers with XNU's strict copy guard."""
from pathlib import Path
import os
import re
import resource
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
HFS=ROOT/'reference/hfs/core'
catalog=(HFS/'hfs_catalog.c').read_text()
if os.environ.get('A6_HFS_BASELINE'):
    catalog=subprocess.check_output(['git','-C',str(HFS),'show','HEAD:core/hfs_catalog.c'],text=True)
header=(HFS/'hfs_catalog.h').read_text()
guard=(ROOT/'xnu/osfmk/device/subrs.c').read_text()
def function(text,name,result):
    start=text.index('\n'+name+'(')+1
    opening=text.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return result+'\n'+text[start:end]+'\n'
def structure(text,name):
    start=text.index('struct '+name+' {');opening=text.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end+1]+'\n'

source=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <sys/stat.h>
/* Apple uuid/uuid.h's public string type, used by the disk journal header. */
typedef char uuid_string_t[37];
#include "hfs_format.h"
typedef u_int32_t cnid_t;
''' + structure(header,'cat_desc') + header[header.index('struct cat_attr {'):header.index('/*\n * Catalog Node Fork')] + header[header.index('struct cat_fork {'):header.index('void hfs_fork_copy(')] + header[header.index('union CatalogKey {'):header.index('/* Constants for HFS fork types */')] + r'''
enum { FILE_HARDLINKS,DIR_HARDLINKS,btNotFound=-1,HFS_STANDARD=1,HFS_FOLDERCOUNT=2 };
/* Apple hfs_catalog.h and hfs_cnode.h constants; no native layout substitutes. */
enum { kHFSAliasType=0x66647270,kHFSAliasCreator=0x4D414353,kFinderInvisibleMask=1<<14 };
#define SF_IMMUTABLE 0x20000
#define UF_IMMUTABLE 2
#define UF_HIDDEN 0x8000
#define MNT_UNKNOWNPERMISSIONS 0x200000
#define HFSTOVCB(m) (m)
#define HFSTOVFS(m) (m)
#define howmany(n,d) (((n)+(d)-1)/(d))
#define SWAP_BE32(x) __builtin_bswap32(x)
#define OSSwapHostToBigConstInt16(x) __builtin_bswap16(x)
#define __improbable(x) __builtin_expect(!!(x),0)
#define memmove_impl memmove
#define memset_impl memset
struct hfsmount {
 uint32_t blockSize,hfs_uid,hfs_gid,hfs_dir_mask,hfs_file_mask,hfs_flags;
 struct cat_desc hfs_private_desc[2];char vcbVN[32];
};
static unsigned vfs_flags(struct hfsmount *m) { (void)m;return 0; }
static uint32_t to_hfs_time(time_t t) { return (uint32_t)(t+2082844800); }
static time_t to_bsd_time(uint32_t t) { return (time_t)t-2082844800; }
static _Noreturn void panic(const char *format,...) {
 va_list args;va_start(args,format);vfprintf(stderr,format,args);va_end(args);exit(86);
}
static void quiet(const char *format,...) { (void)format; }
#define printf quiet
''' + structure(catalog,'update_state') + function(guard,'__memmove_chk','void *').replace('__memmove_chk(', 'native_memmove_chk(',1) + function(guard,'__memset_chk','void *').replace('__memset_chk(', 'native_memset_chk(',1) + r'''
#undef bcopy
#undef bzero
#define bcopy(src,dst,n) native_memmove_chk((dst),(src),(n),__builtin_object_size((dst),1))
#define bzero(dst,n) native_memset_chk((dst),0,(n),__builtin_object_size((dst),1))
''' + function(catalog,'buildrecord','static void') + function(catalog,'catrec_update','static int') + function(catalog,'getbsdattr','static void') + r'''
_Static_assert(sizeof(HFSPlusCatalogFile)==248,"native on-disk file size");
_Static_assert(sizeof(HFSPlusCatalogFolder)==88,"native on-disk folder size");
_Static_assert(offsetof(HFSPlusCatalogFile,userInfo)==48,"file finder info offset");
_Static_assert(offsetof(HFSPlusCatalogFile,finderInfo)==64,"file extended finder info offset");
_Static_assert(offsetof(HFSPlusCatalogFolder,userInfo)==48,"folder finder info offset");
_Static_assert(offsetof(HFSPlusCatalogFolder,finderInfo)==64,"folder extended finder info offset");
int main(void) {
 const mode_t modes[]={S_IFDIR,S_IFREG,S_IFCHR,S_IFBLK,S_IFIFO,S_IFSOCK};
 for(unsigned alignment=0;alignment<16;alignment+=2)for(unsigned kind=0;kind<6;++kind) {
  _Alignas(16) unsigned char bytes[sizeof(CatalogRecord)+64];memset(bytes,0xa5,sizeof(bytes));
  size_t start=16+alignment;CatalogRecord *r=(void *)(bytes+start);uint32_t size=0;
  struct cat_attr attr={.ca_mode=modes[kind]|0640,.ca_uid=501,.ca_gid=20,
   .ca_fileid=42,.ca_linkcount=1,.ca_itime=100,.ca_rdev=0x123456};
  for(unsigned i=0;i<32;++i)attr.ca_finderinfo[i]=(unsigned char)(i*29+alignment+kind);
  buildrecord(&attr,42,7,r,&size);
  assert(size==(kind==0?88:248));
  assert(!memcmp(bytes+start+48,attr.ca_finderinfo,32));
  if(kind)for(size_t i=offsetof(HFSPlusCatalogFile,dataFork);i<248;++i)assert(!bytes[start+i]);
  for(size_t i=0;i<start;++i)assert(bytes[i]==0xa5);
  for(size_t i=start+size;i<sizeof(bytes);++i)assert(bytes[i]==0xa5);
  struct hfsmount mount={.blockSize=4096,.hfs_uid=0,.hfs_gid=0,.hfs_dir_mask=0755,.hfs_file_mask=0644};
  mount.hfs_private_desc[0].cd_cnid=10;mount.hfs_private_desc[1].cd_cnid=11;
  struct cat_desc desc={.cd_cnid=42,.cd_encoding=8};CatalogKey key={.hfsPlus.parentID=2};
  struct cat_fork datafork={.cf_size=10001,.cf_blocks=3,.cf_bytesread=8192},
   rsrcfork={.cf_size=20001,.cf_blocks=5,.cf_bytesread=12288};
  datafork.cf_extents[0]=(HFSPlusExtentDescriptor){100,3};
  rsrcfork.cf_extents[0]=(HFSPlusExtentDescriptor){200,5};
  struct update_state state={.s_desc=&desc,.s_attr=&attr,.s_hfsmp=&mount,
   .s_datafork=kind==1?&datafork:NULL,.s_rsrcfork=kind==1?&rsrcfork:NULL};
  for(unsigned i=0;i<32;++i)attr.ca_finderinfo[i]^=0x5a;
  attr.ca_entries=5;attr.ca_dircount=7;
  assert(!catrec_update(&key,r,&state));
  assert(!memcmp(bytes+start+48,attr.ca_finderinfo,32));
  if(kind==1) {
   assert(r->hfsPlusFile.dataFork.logicalSize==10001 && r->hfsPlusFile.resourceFork.logicalSize==20001);
   assert(r->hfsPlusFile.dataFork.extents[0].startBlock==100 && r->hfsPlusFile.resourceFork.extents[0].startBlock==200);
  }
  for(size_t i=0;i<start;++i)assert(bytes[i]==0xa5);
  for(size_t i=start+size;i<sizeof(bytes);++i)assert(bytes[i]==0xa5);
  struct { unsigned char before[16];struct cat_attr attr;unsigned char after[16]; } output;
  memset(&output,0x3c,sizeof(output));
  getbsdattr(&mount,(const HFSPlusCatalogFile *)r,&output.attr);
  assert(!memcmp(output.attr.ca_finderinfo,attr.ca_finderinfo,32));
  for(unsigned i=0;i<16;++i)assert(output.before[i]==0x3c && output.after[i]==0x3c);
  unsigned char previous[sizeof(CatalogRecord)];memcpy(previous,r,size);++attr.ca_fileid;
  assert(catrec_update(&key,r,&state)==btNotFound && !memcmp(previous,r,size));
 }
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='hfs-finderinfo-',dir=ROOT/'artifacts') as temp:
    temp=Path(temp);(temp/'sys').mkdir()
    # Reuse Apple's actual macro-only header; native format types stay intact.
    (temp/'sys/appleapiopts.h').symlink_to(ROOT/'xnu/bsd/sys/appleapiopts.h')
    (temp/'test.c').write_text(source)
    subprocess.run(['clang','-std=gnu17','-O2','-Wall','-Wextra','-Werror',
        '-fsanitize=address,undefined','-g','-I'+str(temp),'-I'+str(HFS),str(temp/'test.c'),
        '-o',str(temp/'test')],check=True)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    result=subprocess.run([str(temp/'test')],capture_output=True,text=True)
    if os.environ.get('A6_HFS_BASELINE'):
        assert result.returncode==86 and '(16 < 32)' in result.stderr,result.stdout+result.stderr
        print('PASS: unmodified Apple catalog writer reproduces the exact native memmove_chk (16 < 32) failure')
    else:
        assert result.returncode==0,result.stdout+result.stderr
        print('PASS: actual HFS build/update/read functions, strict native guard, all 32 Finder bytes, six types, 2-byte alignment, fork data, record sizes, neighboring guards and stale inode rejection')
