#!/usr/bin/env python3
"""Exercise native pre-exec F_GETSIGSINFO and process/fd/task platform queries."""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
def function(text,declaration):
    start=text.index(declaration);opening=text.index('{',start)
    end,depth=opening+1,1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]+'\n'
compat=(root/'xnu/bsd/dev/a6plte/compat.c').read_text()
cs=(root/'xnu/bsd/kern/kern_cs.c').read_text()
descrip=(root/'xnu/bsd/kern/kern_descrip.c').read_text()
exe=(root/'xnu/bsd/kern/kern_exec.c').read_text()
case=function(descrip,'case F_GETSIGSINFO:')
original_descrip=subprocess.check_output(['git','-C',str(root/'xnu'),'show','HEAD:bsd/kern/kern_descrip.c'],text=True)
original_case=function(original_descrip,'case F_GETSIGSINFO:')
start=exe.index('#if A6PLTE\n\tif (a6_platform_file(imgp->ip_vp))')
exec_policy=exe[start:exe.index('#endif',start)+len('#endif')]
fcntl=(root/'xnu/bsd/sys/fcntl.h').read_text()
start=fcntl.index('typedef struct fgetsigsinfo {')
fg_type=fcntl[start:fcntl.index('} fgetsigsinfo_t;',start)+len('} fgetsigsinfo_t;')]
fixture=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
#define __enum_decl(name,type,...) typedef type name; enum __VA_ARGS__
#include "kern/cs_blobs.h"
#define A6PLTE 1
#define __unused __attribute__((unused))
#define TRUE 1
#define F_GETSIGSINFO 105
#define GETSIGSINFO_PLATFORM_BINARY 1
#define CPU_TYPE_ANY -1
#define CPU_SUBTYPE_ANY -1
#define DTYPE_VNODE 1
struct vnode;
struct cs_blob { struct vnode *csb_vnode;unsigned csb_flags;int csb_platform_binary;const CS_CodeDirectory *csb_cd; };
struct ubc_info { struct cs_blob *cs_blobs; };
struct vnode { void *mount;int regular;struct ubc_info *v_ubcinfo;struct cs_blob *blob; };
typedef struct vnode *vnode_t;
struct proc { struct vnode *p_textvp;struct cs_blob *blob; };
struct fileglob { int type;void *data; };
struct fileproc { int f_type;void *data; };
struct image_params { struct vnode *ip_vp; };
#define UBCINFOEXISTS(vp) ((vp)->v_ubcinfo!=NULL)
#define FILEGLOB_DTYPE(fg) ((fg)->type)
static void *fg_get_data(struct fileglob *fg) { return fg->data; }
static void *fp_get_data(struct fileproc *fp) { return fp->data; }
static struct cs_blob *csproc_get_blob(struct proc *p) { return p->blob; }
static int locks,refs,fdunlocks,copyin_error,copyout_error,getref_error;
static void vnode_lock(struct vnode *vp) { assert(vp && !locks);++locks; }
static void vnode_unlock(struct vnode *vp) { assert(vp && locks==1);--locks; }
static int vnode_getwithref(struct vnode *vp) { assert(vp);if(getref_error)return getref_error;++refs;return 0; }
static void vnode_put(struct vnode *vp) { assert(vp && refs>0);--refs; }
static void proc_fdunlock(int p) { (void)p;++fdunlocks; }
static int copyin(const void *p,void *out,size_t n) { if(copyin_error)return copyin_error;memcpy(out,p,n);return 0; }
static int copyout(const void *p,uintptr_t out,size_t n) { if(copyout_error)return copyout_error;memcpy((void *)out,p,n);return 0; }
typedef uintptr_t vm_address_t;
static struct cs_blob *ubc_cs_blob_get(struct vnode *vp,int cpu,int subtype,off_t offset) {
    assert(cpu==CPU_TYPE_ANY && subtype==CPU_SUBTYPE_ANY);
    return offset>=-1?vp->blob:NULL;
}
static struct vnode root={.mount=(void *)1,.regular=1},file={.mount=(void *)1,.regular=1};
static vnode_t rootvnode=&root;
static int selected=1,provider;
static const void *amfi;
static int a6_userdata_root_selected(void) { return selected; }
static int vnode_isreg(vnode_t vp) { return vp->regular; }
static void *vnode_mount(vnode_t vp) { return vp->mount; }
'''+fg_type+'\n'
fixture+=function(compat,'int a6_platform_file(')+function(compat,'void a6_platform_signature(')
for name,decl in (('csblob_get_platform_binary','int\n'),('csproc_get_platform_binary','int\n'),('csfg_get_platform_binary','int\n')):
    fixture+=function(cs,decl+name+'(')
fixture+=r'''
static int query(struct fileproc *fp,fgetsigsinfo_t *io) {
    void *argp=io;int p=0,error=0;struct vnode *vp;
    switch(F_GETSIGSINFO) {
'''+case+r'''
    }
out:
outdrop:
    assert(!refs && !locks);return error;
}
static int original_query(struct fileproc *fp,fgetsigsinfo_t *io) {
    void *argp=io;int p=0,error=0;struct vnode *vp;
    switch(F_GETSIGSINFO) {
'''+original_case+r'''
    }
out:
outdrop:
    assert(!refs && !locks);return error;
}
static void exec_status(struct image_params *imgp,unsigned *flags,int *platform) {
    struct { unsigned csflags;int platform_binary; } load_result={*flags,*platform};
'''+exec_policy+r'''
    *flags=load_result.csflags;*platform=load_result.platform_binary;
}
int main(void) {
    struct proc process={&file,NULL};struct fileglob fg={DTYPE_VNODE,&file};
    struct fileproc fp={DTYPE_VNODE,&file};
    /* Real launchd path: query the open file BEFORE exec has attached a blob.
     * Both normal offset zero and native wildcard offset -1 must succeed. */
    for(int64_t offset=-1;offset<=0;++offset) {
        fgetsigsinfo_t info={.fg_file_start=offset,.fg_info_request=GETSIGSINFO_PLATFORM_BINARY};
        assert(!file.blob && !file.v_ubcinfo);
        assert(original_query(&fp,&info)==ENOENT && !info.fg_sig_is_platform);
        assert(query(&fp,&info)==0 && info.fg_sig_is_platform==1);
    }
    assert(csproc_get_platform_binary(&process));
    assert(csfg_get_platform_binary(&fg));
    unsigned flags=CS_ADHOC|CS_HARD|CS_KILL;int platform=0;
    struct image_params image={&file};exec_status(&image,&flags,&platform);
    assert(platform && (flags&CS_PLATFORM_BINARY) && !(flags&CS_VALID));
    unsigned signed_flags=CS_VALID|CS_ADHOC|CS_ENFORCEMENT;
    a6_platform_signature(&file,NULL,&signed_flags,NULL);
    assert(signed_flags==(CS_VALID|CS_ADHOC|CS_ENFORCEMENT|CS_PLATFORM_BINARY));
    a6_platform_signature(&file,NULL,NULL,NULL);
    struct cs_blob blob={.csb_vnode=&file};file.blob=&blob;process.blob=&blob;
    assert(csblob_get_platform_binary(&blob));
    /* Explicit bypass is only a view of platform status. Original native
     * validity/ADHOC flags and signature payloads are not fabricated. */
    assert(!blob.csb_flags && !blob.csb_platform_binary);
    copyout_error=EFAULT;fgetsigsinfo_t info={.fg_info_request=GETSIGSINFO_PLATFORM_BINARY};
    assert(query(&fp,&info)==EFAULT);copyout_error=0;
    copyin_error=EFAULT;assert(query(&fp,&info)==EFAULT);copyin_error=0;
    getref_error=EIO;assert(query(&fp,&info)==EIO);getref_error=0;
    info.fg_info_request=999;assert(query(&fp,&info)==EINVAL);info.fg_info_request=GETSIGSINFO_PLATFORM_BINARY;
    info.fg_file_start=-2;assert(query(&fp,&info)==ENOENT);info.fg_file_start=0;
    fp.f_type=2;assert(query(&fp,&info)==EBADF);fp.f_type=DTYPE_VNODE;
    fg.type=2;assert(!csfg_get_platform_binary(&fg));fg.type=DTYPE_VNODE;
    file.blob=NULL;process.blob=NULL;
    for(unsigned test=0;test<5;++test) {
        selected=test!=0;file.mount=test==1?(void *)2:(void *)1;
        file.regular=test!=2;amfi=test==3?&provider:NULL;rootvnode=test==4?NULL:&root;
        assert(!csproc_get_platform_binary(&process) && !csfg_get_platform_binary(&fg));
        info.fg_sig_is_platform=0;assert(query(&fp,&info)==ENOENT && !info.fg_sig_is_platform);
    }
    rootvnode=&root;selected=1;file.regular=1;file.mount=(void *)1;amfi=NULL;
    /* Native signed platform binaries on other mounts keep their status. */
    file.mount=(void *)2;blob.csb_platform_binary=1;file.blob=&blob;process.blob=&blob;
    struct ubc_info ubc={&blob};file.v_ubcinfo=&ubc;
    assert(csproc_get_platform_binary(&process) && csfg_get_platform_binary(&fg));
    info.fg_sig_is_platform=0;assert(!query(&fp,&info) && info.fg_sig_is_platform==1);
    assert(!csblob_get_platform_binary(NULL));
    assert(!locks && !refs && fdunlocks>0);
    puts("PASS: actual F_GETSIGSINFO before exec without a blob, wildcard -1, csops/proc/file/task status, native signature flags, other mounts/provider and error/resource paths");
}
'''
with tempfile.TemporaryDirectory(prefix='platform-bypass-',dir=root/'artifacts') as directory:
    p=Path(directory);(p/'test.c').write_text(fixture)
    subprocess.run(['clang','-std=gnu17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',
                    '-I'+str(root/'xnu/osfmk'),str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
