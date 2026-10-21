#!/usr/bin/env python3
"""Exercise native bindfs boot policy and userdata synchronization dispatch."""
from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]


def body(source, declaration):
    start = source.index(declaration)
    opening = source.index('{', start)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


compat = (root / 'xnu/bsd/dev/a6plte/compat.c').read_text()
bind = (root / 'xnu/bsd/miscfs/bindfs/bind_vfsops.c').read_text()
permission = body(bind, 'if (!IOCurrentTaskHasEntitlement(BINDFS_ENTITLEMENT)')
start = bind.index('\terror = vnode_lookup(data, 0, &lowerrootvp, ctx);')
lookup = bind[start:bind.index('\n\tif (error) {', start)]
policy = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define A6PLTE 1
#define BINDFS_ENTITLEMENT "com.apple.private.bindfs-allow"
struct vnode { void *mount; int regular, directory; };
typedef struct vnode *vnode_t;
struct proc { vnode_t p_textvp; };
typedef struct proc *proc_t;
struct context { proc_t process; int root; };
typedef struct context *vfs_context_t;
struct mount { vnode_t mnt_vnodecovered; struct { char f_mntonname[128]; } mnt_vfsstat; };
static struct vnode root={.mount=(void *)1},file={.mount=(void *)1,.regular=1};
static struct vnode firmware={.mount=(void *)1,.directory=1};
static vnode_t rootvnode=&root;
static struct proc process={&file};
static struct context context={&process,1};
static int selected=1,provider,entitled,refs,get_error,lookup_error=ENOENT,lookups;
static void *amfi;
static int a6_userdata_root_selected(void) { return selected; }
static int vnode_isreg(vnode_t v) { return v->regular; }
static int vnode_isdir(vnode_t v) { return v->directory; }
static void *vnode_mount(vnode_t v) { return v->mount; }
static proc_t vfs_context_proc(vfs_context_t c) { return c->process; }
static int vfs_context_issuser(vfs_context_t c) { return c->root; }
static int vnode_getwithref(vnode_t v) { assert(v==&firmware); if(get_error)return get_error; ++refs;return 0; }
static int vnode_lookup(const char *path,int flags,vnode_t *out,vfs_context_t c) {
    assert(path && !flags && c==&context);++lookups;*out=NULL;
    if(!lookup_error) { *out=&firmware;++refs; } return lookup_error;
}
static int IOCurrentTaskHasEntitlement(const char *key) {
    assert(!strcmp(key,BINDFS_ENTITLEMENT));return entitled;
}
static unsigned char boot_hash[48];static size_t hash_size=48;static int hash_missing;
bool IOGetBootManifestHash(char *out,size_t *size) {
    if(hash_missing)return false;assert(*size==48);memcpy(out,boot_hash,hash_size);*size=hash_size;return true;
}
'''
for declaration in ('int a6_platform_file(', 'int a6_bindfs_boot_allowed(', 'int a6_bindfs_firmware_source('):
    policy += body(compat, declaration)
policy += r'''
static int permission(vfs_context_t ctx) {
'''+permission+r'''
    return 0;
}
static int lower_lookup(struct mount *mp,const char *data,vfs_context_t ctx,vnode_t *out) {
    int error;vnode_t lowerrootvp=NULL;
'''+lookup+r'''
    *out=lowerrootvp;return error;
}
int main(void) {
    struct mount mp={.mnt_vnodecovered=&firmware};
    strcpy(mp.mnt_vfsstat.f_mntonname,"/usr/standalone/firmware");
    char source[256],original[256],hex[97];
    for(unsigned i=0;i<48;++i) { boot_hash[i]=i;snprintf(hex+2*i,3,"%02X",i); }
    snprintf(source,sizeof(source),"/private/preboot/%s/usr/standalone/firmware",hex);
    strcpy(original,source);vnode_t lower=NULL;
    assert(!entitled); /* Native unmodified permission gate would return EPERM. */
    assert(!permission(&context));
    assert(!lower_lookup(&mp,source,&context,&lower) && lower==&firmware && refs==1 && lookups==1);
    --refs;get_error=EIO;
    assert(lower_lookup(&mp,source,&context,&lower)==EIO && !lower && !refs);
    get_error=0;lookup_error=EACCES;
    assert(lower_lookup(&mp,source,&context,&lower)==EACCES && !lower && !refs);
    lookup_error=0;
    assert(!lower_lookup(&mp,"/real/preboot/path",&context,&lower) && lower==&firmware && refs==1);
    --refs;lookup_error=ENOENT;
    for(unsigned test=0;test<6;++test) {
        selected=test!=0;context.root=test!=1;amfi=test==2?&provider:NULL;
        file.regular=test!=3;file.mount=test==4?(void *)2:(void *)1;
        rootvnode=test==5?NULL:&root;
        assert(permission(&context)==EPERM);
        assert(lower_lookup(&mp,source,&context,&lower)==ENOENT && !lower && !refs);
    }
    selected=1;context.root=1;amfi=NULL;file.regular=1;file.mount=(void *)1;rootvnode=&root;
    assert(!a6_bindfs_boot_allowed(NULL));
    context.process=NULL;assert(!a6_bindfs_boot_allowed(&context));context.process=&process;
    for(unsigned test=0;test<6;++test) {
        strcpy(source,original);
        if(test==0)source[17]='F';
        if(test==1)strcat(source,"/../other");
        if(test==2)strcpy(mp.mnt_vfsstat.f_mntonname,"/another/target");
        if(test==3)firmware.mount=(void *)2;
        if(test==4)firmware.directory=0;
        if(test==5)mp.mnt_vnodecovered=NULL;
        assert(lower_lookup(&mp,source,&context,&lower)==ENOENT && !lower && !refs);
        strcpy(mp.mnt_vfsstat.f_mntonname,"/usr/standalone/firmware");
        firmware.mount=(void *)1;firmware.directory=1;mp.mnt_vnodecovered=&firmware;
    }
    strcpy(source,original);hash_size=20;
    assert(lower_lookup(&mp,source,&context,&lower)==ENOENT && !lower && !refs);
    hash_size=48;hash_missing=1;
    assert(lower_lookup(&mp,source,&context,&lower)==ENOENT && !lower && !refs);
    hash_missing=0;amfi=&provider;entitled=1;
    assert(!permission(&context));
    assert(lower_lookup(&mp,source,&context,&lower)==ENOENT && !lower && !refs);
    puts("PASS: native bindfs permission/lookup integration, exact current boot path, real covered vnode, no mountpoint relookup, original errors and root/provider/reference bounds");
}
'''

userdata = (root / 'xnu/bsd/dev/a6plte/userdata.c').read_text()
disk = (root / 'xnu/bsd/sys/disk.h').read_text()
end = disk.index('} dk_synchronize_t;') + len('} dk_synchronize_t;')
sync_type = disk[disk.rindex('typedef struct{', 0, end):end]
ioctl = body(userdata, 'static int device_ioctl(')
commands = sorted(set(re.findall(r'case (DK[A-Z0-9]+):', ioctl)))
flush = r'''
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <errno.h>
#include <sys/types.h>
#include "storage.h"
#define __unused __attribute__((unused))
#define DK_SYNCHRONIZE_OPTION_BARRIER 2
struct proc;
static struct a6_slice userdata={.count=8192,.first=1024,.writable=1};
static struct a6_emmc host;
static int published=1,a6_emmc_lock,flushes,flush_error;
static int minor(dev_t dev) { return dev; }
static void lck_mtx_lock(int *lock) { assert(!*lock);*lock=1; }
static void lck_mtx_unlock(int *lock) { assert(*lock==1);*lock=0; }
int a6_emmc_flush(void *p) { assert(p==&host && a6_emmc_lock);++flushes;return flush_error; }
'''
flush += 'enum { '+','.join(name+'='+str(i+1000) for i,name in enumerate(commands))+' };\n'
flush += sync_type + '\n' + body(userdata, 'static int to_errno(') + ioctl
flush += ioctl.replace(body(ioctl, 'case DKIOCSYNCHRONIZE: {'), '').replace('device_ioctl(', 'old_ioctl(', 1)
flush += r'''
int main(void) {
    dk_synchronize_t request={0};
    assert(old_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==ENOTTY && !flushes);
    for(unsigned option=0;option<=2;option+=2) {
        request.options=option;
        assert(!device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL));
        assert(!a6_emmc_lock);
    }
    assert(flushes==2);
    request=(dk_synchronize_t){.offset=userdata.count*512-1,.length=1};
    assert(!device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL));
    int before=flushes;request.length=2;
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==EINVAL && flushes==before);
    request=(dk_synchronize_t){.offset=UINT64_MAX,.length=1};
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==EINVAL && flushes==before);
    request=(dk_synchronize_t){.length=UINT64_MAX};
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==EINVAL && flushes==before);
    request=(dk_synchronize_t){.options=1};
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==EINVAL && flushes==before);
    request=(dk_synchronize_t){0};request.reserved0160[3]=1;
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==EINVAL && flushes==before);
    request=(dk_synchronize_t){0};userdata.count=UINT64_MAX;
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==EINVAL && flushes==before);
    userdata.count=8192;
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,NULL,0,NULL)==EINVAL && flushes==before);
    assert(device_ioctl(1,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==ENXIO && flushes==before);
    published=0;
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==ENXIO && flushes==before);
    published=1;flush_error=A6_IO_TIMEOUT;
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==ETIMEDOUT && !a6_emmc_lock);
    flush_error=A6_IO_OFFLINE;
    assert(device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL)==ENXIO && !a6_emmc_lock);
    flush_error=0;userdata.writable=0;
    assert(!device_ioctl(0,DKIOCSYNCHRONIZE,(caddr_t)&request,0,NULL));
    assert(!device_ioctl(0,DKIOCSYNCHRONIZECACHE,NULL,0,NULL));
    assert(device_ioctl(0,9999,NULL,0,NULL)==ENOTTY && !a6_emmc_lock);
    puts("PASS: native DKIOCSYNCHRONIZE ENOTTY reproduced and fixed; full/barrier flush, partition/overflow/option bounds, card errors, serialization and legacy flush");
}
'''
with tempfile.TemporaryDirectory(prefix='boot-mount-', dir=root / 'artifacts') as directory:
    p = Path(directory)
    for name, source in (('bindfs', policy), ('flush', flush)):
        (p / (name+'.c')).write_text(source)
        subprocess.run(['clang', '-std=gnu17', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-g', '-I'+str(root/'xnu/bsd/dev/a6plte'),
                        str(p/(name+'.c')), '-o', str(p/name)], check=True)
        subprocess.run([str(p/name)], check=True)
