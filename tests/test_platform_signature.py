#!/usr/bin/env python3
"""Run the actual board MAC callback and native cs_blob/load-result propagation."""
from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root/'xnu/bsd/dev/a6plte/compat.c').read_text()
start = source.index('static int platform_signature(')
opening = source.index('{', start)
end, depth = opening + 1, 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
callback = source[start:end]
assert '.mpo_vnode_check_signature=platform_signature' in source
ubc = (root/'xnu/bsd/kern/ubc_subr.c').read_text()
start = ubc.index('\ttmp_blob.csb_flags = cs_flags;')
end = ubc.index('\n\tif ((flags & MAC_VNODE_CHECK_DYLD_SIM)', start)
propagate = ubc[start:end]
loader = (root/'xnu/bsd/kern/mach_loader.c').read_text()
start = loader.index('\t\tresult->csflags |= blob->csb_flags;')
end = loader.index('\n\t\tresult->cs_end_offset', start)
load_result = loader[start:end]

fixture = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define __enum_decl(name, type, ...) typedef type name; enum __VA_ARGS__
#include "kern/cs_blobs.h"
#define __unused __attribute__((unused))
#define MAXPATHLEN 1024
typedef unsigned cpu_type_t;
struct label;
struct vnode { void *mount; unsigned uid; int regular; const char *path; };
struct cs_blob { const CS_CodeDirectory *csb_cd; unsigned csb_flags,csb_signer_type;
    int csb_platform_binary,csb_platform_path; const char *csb_teamid; };
struct vnode_attr { unsigned va_uid; int supported; };
#define VATTR_INIT(a) memset((a),0,sizeof(*(a)))
#define VATTR_WANTED(a,field) ((void)(a))
#define VATTR_IS_SUPPORTED(a,field) ((a)->supported)
static struct vnode root={.mount=(void *)1};
static struct vnode *rootvnode=&root;
static int selected=1,attr_error,attr_supported=1,path_error,path_mode,provider;
static const void *amfi;
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
''' + callback + r'''
static unsigned classify(struct vnode *vp,struct cs_blob *blob,unsigned input) {
    unsigned output=input,signer_type=CS_SIGNER_TYPE_UNKNOWN;
    char *fatal=NULL;size_t fatal_length=0;
    assert(!platform_signature(vp,NULL,0,blob,&output,&signer_type,0,0,&fatal,&fatal_length));
    assert(!fatal && !fatal_length && signer_type==CS_SIGNER_TYPE_UNKNOWN);
    assert((output&~CS_PLATFORM_BINARY)==(input&~CS_PLATFORM_BINARY));
    return output;
}
int main(void) {
    CS_CodeDirectory cd={.platform=1};
    struct cs_blob original={.csb_cd=&cd};
    struct vnode file={.mount=(void *)1,.regular=1,.path="/sbin/mount"};
    unsigned native_flags=CS_VALID|CS_HARD|CS_KILL|CS_ENFORCEMENT;
#ifdef BASELINE
    /* Previously the registered policy had no vnode_check_signature callback. */
    unsigned cs_flags=native_flags;
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
    puts("PASS: original absent MAC callback leaves the signed boot task non-platform");
    return 0;
#else
    assert((result->csflags&CS_PLATFORM_BINARY) && result->platform_binary);
    assert(!tmp_blob.csb_platform_path && !tmp_blob.csb_teamid);
    assert((result->csflags&(CS_HARD|CS_KILL|CS_ENFORCEMENT))==(CS_HARD|CS_KILL|CS_ENFORCEMENT));
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
    assert(!(classify(&file,&original,native_flags|CS_ADHOC)&CS_PLATFORM_BINARY));
    assert(!(classify(&file,&original,native_flags&~CS_VALID)&CS_PLATFORM_BINARY));
    cd.platform=0;assert(!(classify(&file,&original,native_flags)&CS_PLATFORM_BINARY));cd.platform=1;
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
    assert(!platform_signature(&file,NULL,0,&original,NULL,NULL,0,0,NULL,NULL));
    puts("PASS: actual platform-signature MAC callback, native cs_blob and Mach-O load result; system boot tasks accepted, ad-hoc/user/foreign-root/provider/error cases preserved");
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
