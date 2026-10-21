#!/usr/bin/env python3
"""Run the actual root-cache predicate and native owner/CSR/directory policy."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
native=(ROOT/'xnu/bsd/vm/vm_unix.c').read_text()
diag=(ROOT/'xnu/bsd/dev/a6plte/dyld_diag.c').read_text()
baseline=bool(os.environ.get('A6_DYLD_BASELINE'))
if baseline:
    native=subprocess.check_output(['git','-C',str(ROOT/'xnu'),'show','HEAD:bsd/vm/vm_unix.c'],text=True)
def function(text,name,result):
    start=text.index('\n'+name+'(')+1 if '\n'+name+'(' in text else text.index(name+'(')
    opening=text.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return result+'\n'+text[start:end]+'\n'
start=native.index('\t\t/* The shared cache file must be owned by root */')
end=native.index('\t\t/* get vnode size */',start)
policy=native[start:end]
paths=native[native.index('#if XNU_TARGET_OS_OSX\n\n#if defined (__x86_64__)'):native.index('#ifndef SECURE_KERNEL\nstatic int sysctl_scdir_enforce')]
source=r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define A6PLTE 1
#define CONFIG_CSR 1
#define XNU_TARGET_OS_OSX 1
#define SF_RESTRICTED 0x80000
#define CSR_ALLOW_UNRESTRICTED_FS 2
#define VNODE_LOOKUP_NOCROSSMOUNT 1
#define SHARED_REGION_TRACE_ERROR(args) ((void)0)
#define A6_SR_STAGE(value) ((void)0)
struct vnode { const char *v_name;struct vnode *parent;void *mount;unsigned uid,flags;int regular; };
typedef struct vnode *vnode_t;
struct vnode_attr { unsigned va_uid,va_flags,supported; };
#define VATTR_INIT(a) memset((a),0,sizeof(*(a)))
#define VATTR_WANTED(a,n) ((void)(a))
#define VATTR_IS_SUPPORTED(a,n) ((a)->supported)
static int selected=1,attr_error,attr_supported=1,csr_unrestricted,references;
static struct vnode root={.mount=(void *)1},cache_dir={.mount=(void *)1},other_dir={.mount=(void *)1};
static vnode_t rootvnode=&root;
static int a6_userdata_root_selected(void) { return selected; }
static int vnode_isreg(vnode_t vp) { return vp->regular; }
static void *vnode_mount(vnode_t vp) { return vp->mount; }
static vnode_t vnode_parent(vnode_t vp) { return vp->parent; }
static int vfs_context_current(void) { return 0; }
static int vnode_getattr(vnode_t vp,struct vnode_attr *a,int context) {
    (void)context;a->va_uid=vp->uid;a->va_flags=vp->flags;a->supported=attr_supported;return attr_error;
}
static int vnode_lookup(const char *path,int flags,vnode_t *vp,int context) {
    (void)context;assert(flags==0 || flags==VNODE_LOOKUP_NOCROSSMOUNT);
    if (!strcmp(path,"/System/Library/Caches/com.apple.dyld")) {
        *vp=&cache_dir;++references;return 0;
    }
    return ENOENT;
}
static void vnode_put(vnode_t vp) { assert(vp==&cache_dir && references>0);--references; }
static int csr_check(int mask) { assert(mask==CSR_ALLOW_UNRESTRICTED_FS);return csr_unrestricted?0:EPERM; }
''' + paths + function(diag,'a6_dyld_root_cache','int') + r'''
static int native_policy(vnode_t vp,vnode_t rdir_vp) {
    (void)rdir_vp;
    int error=0,is_driverkit=0;
    struct { vnode_t vp; } entry={vp},*srfmp=&entry;
    struct vnode_attr va;
''' + policy + r'''
    return 0;
done:
    return error;
}
int main(void) {
    (void)other_dir;
    struct vnode file={.v_name="dyld_shared_cache_arm64.42.dyldlinkedit",
        .mount=(void *)1,.parent=&cache_dir,.regular=1};
    assert(a6_dyld_root_cache(&file,&root));
#ifdef BASELINE
    assert(native_policy(&file,&root)==EPERM);
    puts("PASS: original macOS CSR policy reproduces EPERM on a valid root-owned HFS cache without SF_RESTRICTED");
#else
    assert(native_policy(&file,&root)==0);
    scdir_enforce=1;assert(native_policy(&file,&root)==0);
    char name[96];
    for(unsigned i=0;i<44;++i) {
        snprintf(name,sizeof(name),"dyld_shared_cache_arm64.%u.dyldlinkedit",i);
        file.v_name=name;assert(native_policy(&file,&root)==0);
    }
    file.v_name="dyld_shared_cache_arm64.42.dyldlinkedit";
    file.uid=501;assert(!a6_dyld_root_cache(&file,&root) && native_policy(&file,&root)==EPERM);file.uid=0;
    file.mount=(void *)2;assert(!a6_dyld_root_cache(&file,&root) && native_policy(&file,&root)==EPERM);file.mount=(void *)1;
    file.parent=&other_dir;assert(!a6_dyld_root_cache(&file,&root) && native_policy(&file,&root)==EPERM);file.parent=&cache_dir;
    selected=0;assert(!a6_dyld_root_cache(&file,&root) && native_policy(&file,&root)==EPERM);selected=1;
    file.regular=0;assert(!a6_dyld_root_cache(&file,&root));file.regular=1;
    assert(!a6_dyld_root_cache(&file,&other_dir));
    file.v_name="dyld_shared_cache_arm64evil";assert(!a6_dyld_root_cache(&file,&root));
    file.v_name="launchd";assert(!a6_dyld_root_cache(&file,&root) && native_policy(&file,&root)==EPERM);
    file.v_name="dyld_shared_cache_arm64";
    attr_error=EIO;assert(!a6_dyld_root_cache(&file,&root) && native_policy(&file,&root)==EIO);attr_error=0;
    attr_supported=0;assert(!a6_dyld_root_cache(&file,&root));attr_supported=1;
    rootvnode=NULL;assert(!a6_dyld_root_cache(&file,&root));rootvnode=&root;
    /* Native SIP-protected files keep the original path; no global CSR change. */
    selected=0;file.flags=SF_RESTRICTED;assert(native_policy(&file,&root)==0);
    assert(!references && !csr_unrestricted);
    puts("PASS: actual native owner/CSR/directory policy; root-owned HFS caches accepted, 44 filenames, foreign roots/mounts/parents, non-root ownership, unsupported attributes and I/O failures rejected; native SIP path and vnode references preserved");
#endif
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='dyld-policy-',dir=ROOT/'artifacts') as d:
    p=Path(d);(p/'test.c').write_text(source)
    subprocess.run(['clang','-std=gnu17','-Wall','-Wextra','-Werror','-Wno-unused-label',
        '-fsanitize=address,undefined','-g',*(['-DBASELINE'] if baseline else []),str(p/'test.c'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
