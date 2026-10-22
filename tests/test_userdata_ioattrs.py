#!/usr/bin/env python3
"""Run native VFS I/O-attribute discovery through the actual userdata ioctl."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
driver = (ROOT / 'xnu/bsd/dev/a6plte/userdata.c').read_text()
vfs = (ROOT / 'xnu/bsd/vfs/vfs_subr.c').read_text()
disk = (ROOT / 'xnu/bsd/sys/disk.h').read_text()
mount = (ROOT / 'xnu/bsd/sys/mount_internal.h').read_text()


def function(source, declaration):
    start = source.index(declaration)
    opening = source.index('{', start)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


ioctl = function(driver, 'static int device_ioctl(')
initialize = function(vfs, 'errno_t\nvfs_init_io_attributes(')
used = set(re.findall(r'\bDK[A-Z_]+\b', ioctl + initialize))
used.update(('DKIOCGETBSDUNIT', 'DKIOCGETCOMMANDPOOLSIZE',
             'DKIOCISSOLIDSTATE', 'DKIOCGETTHROTTLEMASK'))
defines = '\n'.join(line for line in disk.splitlines()
                    if re.match(r'#define\s+(\w+)', line)
                    and re.match(r'#define\s+(\w+)', line)[1] in used)
mount_names = set(re.findall(r'\bMNT[A-Z_]+\b', initialize))
defines += '\n' + '\n'.join(line for line in mount.splitlines()
                             if re.match(r'#define\s+(\w+)', line)
                             and re.match(r'#define\s+(\w+)', line)[1] in mount_names)
ioccom = (ROOT / 'xnu/bsd/sys/ioccom.h').read_text()
ioccom = ioccom[ioccom.index('#define IOCPARM_MASK'):ioccom.rindex('#endif')]

source = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
#include "storage.h"
#define __unused __attribute__((unused))
#define FALSE 0
#define TRUE 1
#define CONFIG_IOSCHED 0
#define MNT_REMOVABLE 0x200
#define MAX_UPL_SIZE_BYTES (64*1024*1024)
#define PAGE_SIZE 4096
#define PAGE_MASK 4095
typedef int errno_t, boolean_t;
typedef void *vfs_context_t;
struct proc;
typedef struct { uint64_t offset,length; uint32_t options; uint8_t reserved0160[4]; } dk_synchronize_t;
typedef struct { uint32_t flags; } dk_corestorage_info_t;
typedef uint32_t dk_apfs_flavour_t;
enum { DK_APFS_FUSION=2 };
struct mount {
    uint64_t mnt_throttle_mask;
    uint32_t mnt_devbsdunit,mnt_kern_flag,mnt_devblocksize,mnt_maxreadcnt,mnt_maxwritecnt,mnt_flag;
    uint16_t mnt_segreadcnt,mnt_segwritecnt;
    uint32_t mnt_maxsegreadsize,mnt_maxsegwritesize,mnt_alignmentmask,mnt_ioqueue_depth;
    uint32_t mnt_ioscale,mnt_ioflags,mnt_minsaturationbytecount;
};
typedef struct mount *mount_t;
struct vnode { unsigned unused; } root;
typedef struct vnode *vnode_t;
static vnode_t rootvp=&root;
static uint32_t rootunit=UINT32_MAX;
static int published=1,a6_emmc_lock,host;
static unsigned flushes,locked;
static struct a6_blockdev disk;
static struct a6_slice userdata={.disk=&disk,.first=1024,.count=8192,.writable=1};
static int minor(dev_t dev) { return (int)dev; }
int a6_emmc_flush(void *p) { assert(p==&host && locked);++flushes;return 0; }
static void lck_mtx_lock(int *p) { assert(p==&a6_emmc_lock && !locked);locked=1; }
static void lck_mtx_unlock(int *p) { assert(p==&a6_emmc_lock && locked);locked=0; }
static vfs_context_t vfs_context_current(void) { return NULL; }
static unsigned num_trailing_0(uint64_t n) { return n?__builtin_ctzll(n):64; }
static void set_fsblocksize(vnode_t vp) { assert(vp==rootvp); }
''' + ioccom + '\n' + defines + '\n'
source += function(driver, 'static int to_errno(') + ioctl
source += r'''
static unsigned long fail_command;
static int legacy;
static int VNOP_IOCTL(vnode_t vp,unsigned long cmd,caddr_t data,int flags,vfs_context_t ctx) {
    assert(vp==rootvp && !ctx);
    if(cmd==fail_command) return EIO;
    if(legacy && (cmd==DKIOCGETCOMMANDPOOLSIZE || cmd==DKIOCISSOLIDSTATE ||
                   cmd==DKIOCGETTHROTTLEMASK)) return ENOTTY;
    return device_ioctl(0,cmd,data,flags,NULL);
}
''' + initialize + r'''
static struct mount initial_mount(void) {
    return (struct mount){.mnt_throttle_mask=63,.mnt_maxreadcnt=1024*1024,
        .mnt_maxwritecnt=1024*1024,.mnt_segreadcnt=32,.mnt_segwritecnt=32,
        .mnt_alignmentmask=PAGE_MASK,.mnt_ioqueue_depth=MNT_DEFAULT_IOQUEUE_DEPTH,.mnt_ioscale=1};
}
int main(void) {
    /* Reproduce the old failure in the real VFS consumer: attributes are
     * left at a 64-MiB maximum before applying any advertised constraints. */
    struct mount m=initial_mount();legacy=1;
    assert(vfs_init_io_attributes(rootvp,&m)==ENOTTY);
    assert(m.mnt_maxreadcnt==MAX_UPL_SIZE_BYTES && m.mnt_maxwritecnt==MAX_UPL_SIZE_BYTES);
    assert(!(m.mnt_kern_flag&MNTK_SSD));legacy=0;

    m=initial_mount();
    assert(vfs_init_io_attributes(rootvp,&m)==0);
    assert(m.mnt_maxreadcnt==65536 && m.mnt_maxwritecnt==65536);
    /* PIO maps the buffer in virtual memory; it has no one-physical-page
     * scatter/gather restriction. Zero lets native VFS derive the count. */
    assert(m.mnt_segreadcnt==16 && m.mnt_segwritecnt==16);
    assert(m.mnt_maxsegreadsize==65536 && m.mnt_maxsegwritesize==65536);
    assert(!m.mnt_alignmentmask && m.mnt_ioscale==1);
    assert(m.mnt_throttle_mask==1 && m.mnt_devbsdunit==0 && rootunit==0);
    assert(m.mnt_kern_flag&MNTK_SSD);
    assert(!(m.mnt_kern_flag&MNTK_VIRTUALDEV) && !m.mnt_ioflags && !m.mnt_minsaturationbytecount);
    assert(!flushes && !locked);

    /* Guard the native 32/64-bit reply widths, not just their values. */
    unsigned long commands[]={DKIOCGETCOMMANDPOOLSIZE,DKIOCISSOLIDSTATE,
        DKIOCGETTHROTTLEMASK,DKIOCGETBSDUNIT,DKIOCGETMAXBYTECOUNTREAD,
        DKIOCGETMAXSEGMENTCOUNTREAD,DKIOCGETMAXSEGMENTCOUNTWRITE};
    uint64_t expected[]={1,1,1,0,65536,0,0};
    for(unsigned i=0;i<sizeof(commands)/sizeof(*commands);++i) {
        unsigned n=IOCPARM_LEN(commands[i]);assert(n==4 || n==8);
        unsigned char *b=malloc(n+16);assert(b);memset(b,0xa5,n+16);
        assert(!device_ioctl(0,commands[i],(caddr_t)b,0,NULL));
        uint64_t value=0;memcpy(&value,b,n);assert(value==expected[i]);
        for(unsigned j=n;j<n+16;++j)assert(b[j]==0xa5);
        free(b);
    }
    fail_command=DKIOCGETMAXBYTECOUNTREAD;m=initial_mount();
    assert(vfs_init_io_attributes(rootvp,&m)==EIO);fail_command=0;
    uint64_t reply=UINT64_MAX;
    assert(device_ioctl(1,DKIOCGETCOMMANDPOOLSIZE,(caddr_t)&reply,0,NULL)==ENXIO);
    published=0;
    assert(device_ioctl(0,DKIOCGETCOMMANDPOOLSIZE,(caddr_t)&reply,0,NULL)==ENXIO);
    assert(reply==UINT64_MAX && !flushes && !locked);
    puts("PASS: native VFS discovers complete PIO limits, SSD classification and controller unit; old ENOTTY reproduced; reply widths and real errors preserved");
}
'''

with tempfile.TemporaryDirectory(prefix='userdata-ioattrs-', dir=ROOT / 'artifacts') as directory:
    path = Path(directory)
    (path / 'test.c').write_text(source)
    subprocess.run(['clang', '-std=gnu17', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-g', '-I'+str(ROOT / 'xnu/bsd/dev/a6plte'),
                    str(path / 'test.c'), '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
