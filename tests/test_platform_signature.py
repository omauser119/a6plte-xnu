#!/usr/bin/env python3
"""Run the actual board MAC callback and native cs_blob/load-result propagation."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root/'xnu/bsd/dev/a6plte/compat.c').read_text()
def function(text, declaration):
    start=text.index(declaration);opening=text.index('{',start)
    end,depth=opening+1,1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]+'\n'
callback=function(source,'static bool system_code_path(')+function(source,'void a6_platform_signature(')
baseline=bool(os.environ.get('A6_PLATFORM_BASELINE'))
if baseline:
    patch=subprocess.check_output(['git','show','9eabb12:patches/xnu-a6plte-framebuffer.patch'],text=True)
    old=patch.split('diff --git c/bsd/dev/a6plte/compat.c w/bsd/dev/a6plte/compat.c',1)[1].split('diff --git',1)[0]
    old='\n'.join(line[1:] for line in old.splitlines() if line.startswith('+') and not line.startswith('+++'))
    callback+=function(old,'static int platform_signature(')
mac=(root/'xnu/security/mac_vfs.c').read_text()
start=mac.index('#if A6PLTE\n\tif (error == 0) {\n\t\textern void a6_platform_signature')
hook=mac[start:mac.index('#endif',start)+len('#endif')]
exec_source=(root/'xnu/bsd/kern/kern_exec.c').read_text()
assert '#define EXECUTABLE_KEY "executable_path="' in exec_source
ubc = (root/'xnu/bsd/kern/ubc_subr.c').read_text()
start = ubc.index('\ttmp_blob.csb_flags = cs_flags;')
end = ubc.index('\n\tif ((flags & MAC_VNODE_CHECK_DYLD_SIM)', start)
propagate = ubc[start:end]
start=ubc.index('#if A6PLTE\n\t/* A signature may have been attached before exec')
revalidate=ubc[start:ubc.index('#endif',start)+len('#endif')]
loader = (root/'xnu/bsd/kern/mach_loader.c').read_text()
start = loader.index('\t\tresult->csflags |= blob->csb_flags;')
end = loader.index('\n\t\tresult->cs_end_offset', start)
load_result = loader[start:end]

fixture = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define __enum_decl(name, type, ...) typedef type name; enum __VA_ARGS__
#include "kern/cs_blobs.h"
#define __unused __attribute__((unused))
#define MAXPATHLEN 1024
#define A6PLTE 1
#define MIN(a,b) ((a)<(b)?(a):(b))
#define VNODE_LOOKUP_NOCROSSMOUNT 1
typedef unsigned cpu_type_t;
struct label;
struct vnode { void *mount; unsigned uid; int regular; const char *path; };
typedef struct vnode *vnode_t;
struct cs_blob_platform_flags { unsigned csb_platform_binary:1,csb_platform_path:1; };
struct cs_blob { const CS_CodeDirectory *csb_cd; unsigned csb_flags,csb_signer_type;
    union { struct cs_blob_platform_flags csb_platform_flags;
        struct { unsigned csb_platform_binary:1,csb_platform_path:1; }; };
    const char *csb_teamid; };
#define zalloc_ro_update_field(zone,blob,field,value) memcpy(&(blob)->field,(value),sizeof((blob)->field))
struct nameidata { struct vnode *ni_vp,*ni_rootdir; };
struct image_params { struct vnode *ip_vp;struct nameidata *ip_ndp;char *ip_strings,*ip_strendp; };
struct vnode_attr { unsigned va_uid; int supported; };
#define VATTR_INIT(a) memset((a),0,sizeof(*(a)))
#define VATTR_WANTED(a,field) ((void)(a))
#define VATTR_IS_SUPPORTED(a,field) ((a)->supported)
static struct vnode root={.mount=(void *)1};
static struct vnode *rootvnode=&root;
static int selected=1,attr_error,attr_supported=1,path_error,path_mode,provider;
static const void *amfi;
static struct vnode *lookup_target;
static int lookup_error,references,lookups;
static int a6_userdata_root_selected(void) { return selected; }
static int vnode_isreg(struct vnode *vp) { return vp->regular; }
static void *vnode_mount(struct vnode *vp) { return vp->mount; }
static int vfs_context_current(void) { return 0; }
static int vnode_getattr(struct vnode *vp,struct vnode_attr *a,int context) {
    (void)context;a->va_uid=vp->uid;a->supported=attr_supported;return attr_error;
}
static int vn_getpath(struct vnode *vp,char *path,int *length) {
    if (path_error) return path_error;
    assert(*length==MAXPATHLEN);
    if (path_mode==1) { memset(path,'a',MAXPATHLEN);return 0; }
    if (path_mode==2) { *length=MAXPATHLEN+1;return 0; }
    if (path_mode==3) { *length=0;return 0; }
    size_t n=strlen(vp->path)+1;assert(n<=(size_t)*length);
    memcpy(path,vp->path,n);*length=(int)n;return 0;
}
static int vnode_lookup(const char *path,int flags,struct vnode **vp,int context) {
    (void)context;assert(flags==VNODE_LOOKUP_NOCROSSMOUNT && path && lookup_target);
    ++lookups;if(lookup_error)return lookup_error;
    *vp=lookup_target;++references;return 0;
}
static void vnode_put(struct vnode *vp) { assert(vp==lookup_target && references>0);--references; }
''' + callback + r'''
static unsigned classify(struct vnode *vp,struct cs_blob *blob,unsigned input) {
    unsigned output=input;
    a6_platform_signature(vp,blob,&output,NULL);
    assert((output&~CS_PLATFORM_BINARY)==(input&~CS_PLATFORM_BINARY));
    return output;
}
static unsigned after_mac(struct vnode *vp,struct cs_blob *cs_blob,unsigned input,
    int error,struct image_params *imgp) {
    unsigned output=input,*cs_flags=&output;
''' + hook + r'''
    assert(!references);
    return output;
}
static void revalidate_flags(struct cs_blob *blob,unsigned cs_flags,int error) {
''' + revalidate + r'''
}
int main(void) {
    CS_CodeDirectory cd={.platform=0};
    struct cs_blob original={.csb_cd=&cd};
    struct vnode file={.mount=(void *)1,.regular=1,.path="/sbin/mount"};
    unsigned native_flags=CS_VALID|CS_ADHOC|CS_HARD|CS_KILL|CS_ENFORCEMENT;
#ifdef BASELINE
    unsigned cs_flags=native_flags;
    assert(!platform_signature(&file,NULL,0,&original,&cs_flags,NULL,0,0,NULL,NULL));
#else
    unsigned cs_flags=classify(&file,&original,native_flags);
#endif
    unsigned signer_type=CS_SIGNER_TYPE_UNKNOWN;
    struct cs_blob tmp_blob=original;
''' + propagate + r'''
    struct { unsigned csflags;int platform_binary; } loaded={0},*result=&loaded;
    struct cs_blob *blob=&tmp_blob;
''' + load_result + r'''
#ifdef BASELINE
    assert(!(result->csflags&CS_PLATFORM_BINARY) && !result->platform_binary);
    puts("PASS: previous actual callback rejects a valid re-signed system boot task without the Apple platform marker");
    return 0;
#else
    assert((result->csflags&CS_PLATFORM_BINARY) && result->platform_binary);
    assert(!tmp_blob.csb_platform_path && !tmp_blob.csb_teamid);
    assert((result->csflags&(CS_HARD|CS_KILL|CS_ENFORCEMENT))==(CS_HARD|CS_KILL|CS_ENFORCEMENT));
    /* fcntl can attach a signature before exec. A later successful signature
     * revalidation must update native RO platform state, not just csb_flags. */
    struct cs_blob earlier=original;earlier.csb_teamid="test-team";
    revalidate_flags(&earlier,cs_flags,0);
    assert(earlier.csb_platform_binary && !earlier.csb_platform_path && !earlier.csb_teamid);
    earlier=original;earlier.csb_teamid="test-team";
    revalidate_flags(&earlier,cs_flags,EPERM);
    assert(!earlier.csb_platform_binary && earlier.csb_teamid);
    amfi=&provider;revalidate_flags(&earlier,cs_flags,0);
    assert(!earlier.csb_platform_binary && earlier.csb_teamid);amfi=NULL;
    const char *positive[]={"/sbin/mount","/sbin/launchd","/bin/launchctl","/usr/bin/log",
        "/usr/sbin/syslogd","/usr/libexec/xpcproxy","/usr/lib/dyld",
        "/System/Library/CoreServices/SpringBoard.app/SpringBoard",
        "/System/Cryptexes/OS/System/Library/Frameworks/Test.framework/Test"};
    for(unsigned i=0;i<sizeof(positive)/sizeof(positive[0]);++i) {
        file.path=positive[i];assert(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY);
    }
    const char *negative[]={"/private/var/tmp/mount","/tmp/mount","/sbin.evil/mount",
        "/usr/bin.evil/mount","/System/Library.evil/mount","/sbin/","/mount",
        "/private/var/containers/Bundle/Application/Test.app/Test"};
    for(unsigned i=0;i<sizeof(negative)/sizeof(negative[0]);++i) {
        file.path=negative[i];assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));
    }
    file.path="/sbin/mount";
    assert(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY);
    assert(classify(&file,&original,native_flags&~CS_ADHOC)&CS_PLATFORM_BINARY);
    assert(!(classify(&file,&original,native_flags&~CS_VALID)&CS_PLATFORM_BINARY));
    cd.platform=1;assert(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY);cd.platform=0;
    original.csb_cd=NULL;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));original.csb_cd=&cd;
    amfi=&provider;assert(classify(&file,&original,native_flags)==native_flags);
    assert(classify(&file,&original,native_flags|CS_PLATFORM_BINARY)==(native_flags|CS_PLATFORM_BINARY));amfi=NULL;
    selected=0;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));selected=1;
    rootvnode=NULL;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));rootvnode=&root;
    file.mount=(void *)2;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));file.mount=(void *)1;
    file.uid=501;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));file.uid=0;
    file.regular=0;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));file.regular=1;
    attr_error=EIO;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));attr_error=0;
    attr_supported=0;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));attr_supported=1;
    path_error=ENOENT;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));path_error=0;
    for(path_mode=1;path_mode<=3;++path_mode)
        assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));
    path_mode=0;
    assert(classify(NULL,&original,native_flags)==native_flags);
    assert(classify(&file,NULL,native_flags)==native_flags);
    a6_platform_signature(&file,&original,NULL,NULL);
    /* HFS may expose a private inode name or no cached path. Use the saved
     * exec name only when native namei root and a fresh lookup match this vnode. */
    file.path="/.HFS+ Private Directory Data/iNode123";
    char saved[MAXPATHLEN+32]="executable_path=/sbin/mount";
    struct nameidata nd={&file,&root};
    struct image_params image={&file,&nd,saved,saved+strlen(saved)+1};
    lookup_target=&file;
    assert(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY);
    path_error=ENOENT;
    assert(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY);
    path_error=0;
    assert(after_mac(&file,&original,native_flags,EPERM,&image)==native_flags);
    assert(after_mac(&file,&original,native_flags,EIO,&image)==native_flags);
    struct vnode other={.mount=(void *)1};
    lookup_target=&other;assert(!(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY));
    lookup_target=&file;lookup_error=ENOENT;
    assert(!(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY));lookup_error=0;
    nd.ni_rootdir=&other;assert(!(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY));nd.ni_rootdir=&root;
    nd.ni_vp=&other;assert(!(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY));nd.ni_vp=&file;
    image.ip_vp=&other;assert(!(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY));image.ip_vp=&file;
    const char *bad[]={"executable_path=/sbin/../private/var/mount","executable_path=/sbin/./mount",
        "executable_path=/private/var/mount","executable_path=sbin/mount","wrong_prefix=/sbin/mount"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);++i) {
        strcpy(saved,bad[i]);image.ip_strendp=saved+strlen(saved)+1;
        int count=lookups;assert(!(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY));assert(lookups==count);
    }
    memset(saved,'a',sizeof(saved));memcpy(saved,"executable_path=/sbin/",22);image.ip_strendp=saved+sizeof(saved);
    assert(!(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY));
    image.ip_strendp=NULL;assert(!(after_mac(&file,&original,native_flags,0,&image)&CS_PLATFORM_BINARY));
    assert(!references);
    puts("PASS: actual kernel platform policy and native cs_blob/load result, re-signed system binaries, saved exec path/HFS inode alias, vnode/root identity, traversal, MAC failure and bounded path checks");
    return 0;
#endif
}
'''
with tempfile.TemporaryDirectory(prefix='platform-signature-',dir=root/'artifacts') as directory:
    directory=Path(directory)
    (directory/'test.c').write_text(fixture)
    binary=directory/'test'
    subprocess.run(['clang','-std=gnu17','-Wall','-Wextra','-Werror','-Wno-unused-function',
                    '-Wno-unused-variable','-fsanitize=address,undefined','-g',
                    *(['-DBASELINE'] if os.environ.get('A6_PLATFORM_BASELINE') else []),
                    '-I'+str(root/'xnu/osfmk'),str(directory/'test.c'),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
