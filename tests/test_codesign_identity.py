#!/usr/bin/env python3
"""Reproduce missing CS_SIGNED through native exec/identity/csops bodies."""
from pathlib import Path
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


cs = (root / 'xnu/bsd/kern/kern_cs.c').read_text()
ubc = (root / 'xnu/bsd/kern/ubc_subr.c').read_text()
exe = (root / 'xnu/bsd/kern/kern_exec.c').read_text()
proc = (root / 'xnu/bsd/kern/kern_proc.c').read_text()
compat = (root / 'xnu/bsd/dev/a6plte/compat.c').read_text()
start = exe.index('if (load_result.csflags & CS_VALID) {')
exec_flags = exe[start:exe.index('if (proc_getcsflags(p) & CS_EXEC_SET_HARD)', start)]
fixture = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <sys/types.h>
#include <arpa/inet.h>
#define __enum_decl(name,type,...) typedef type name; enum __VA_ARGS__
#include "kern/cs_blobs.h"
#define A6PLTE 1
#define __unused __attribute__((unused))
#define CS_OPS_IDENTITY 11
#define CS_OPS_TEAMID 14
typedef uintptr_t vm_address_t;
typedef uintptr_t user_addr_t;
struct vnode;
struct cs_blob {
    unsigned csb_flags;
    const CS_CodeDirectory *csb_cd;
    void *csb_mem_kaddr;
    size_t csb_mem_size;
};
struct vnode { void *mount; int regular; struct cs_blob *blob; };
struct proc { struct vnode *p_textvp; off_t p_textoff; unsigned csflags; };
typedef struct proc *proc_t;
struct image_params { unsigned ip_csflags; };
static struct vnode root = {.mount = (void *)1, .regular = 1};
static struct vnode file = {.mount = (void *)1, .regular = 1};
static struct vnode *rootvnode = &root;
static int selected = 1, provider, locks, copies, copy_error_at;
static void *amfi;
static int a6_userdata_root_selected(void) { return selected; }
static int vnode_isreg(struct vnode *vp) { return vp->regular; }
static void *vnode_mount(struct vnode *vp) { return vp->mount; }
static unsigned proc_getcsflags(proc_t p) { return p->csflags; }
static void proc_lock(proc_t p) { assert(p && !locks); ++locks; }
static void proc_unlock(proc_t p) { assert(p && locks == 1); --locks; }
static struct cs_blob *ubc_cs_blob_get(struct vnode *vp, int cpu, int sub, off_t off) {
    assert(cpu == -1 && sub == -1 && off == 0); return vp->blob;
}
static void panic(const char *format, ...) { (void)format; abort(); }
static int copyout(const void *from, user_addr_t to, size_t size) {
    assert(!locks); if (++copies == copy_error_at) return EFAULT;
    memcpy((void *)to, from, size); return 0;
}
static const char *csproc_get_teamid(proc_t p) { (void)p; return NULL; }
'''
fixture += body(compat, 'int a6_platform_file(')
fixture += body(compat, 'void a6_platform_signature(')
fixture += body(ubc, 'const CS_GenericBlob *\ncsblob_find_blob_bytes(')
fixture += body(ubc, 'const CS_GenericBlob *\ncsblob_find_blob(')
fixture += body(cs, 'const char *\ncsblob_get_identity(')
fixture += body(cs, 'const char *\ncs_identity_get(')
fixture += r'''
static unsigned native_exec_flags(unsigned flags) {
    struct { unsigned csflags; } load_result = {flags};
    struct image_params image = {0}, *imgp = &image;
'''+exec_flags+r'''
    return imgp->ip_csflags;
}
static int query(proc_t pt, int ops, void *buffer, size_t usize) {
    user_addr_t uaddr = (uintptr_t)buffer; int error = 0;
    copies = 0;
    switch (ops) {
'''+body(proc, 'case CS_OPS_IDENTITY:\n\tcase CS_OPS_TEAMID: {')+r'''
    }
out:
    assert(!locks); return error;
}
int main(void) {
    uint8_t signature[512] = {0}, saved[512], output[128];
    const char identifier[] = "com.apple.mount";
    CS_SuperBlob *sb = (void *)signature;
    size_t cd_offset = sizeof(*sb) + sizeof(CS_BlobIndex);
    CS_CodeDirectory *cd = (void *)(signature + cd_offset);
    size_t cd_size = sizeof(*cd) + sizeof(identifier);
    sb->magic = htonl(CSMAGIC_EMBEDDED_SIGNATURE);
    sb->count = htonl(1); sb->length = htonl(cd_offset + cd_size);
    sb->index[0].type = htonl(CSSLOT_CODEDIRECTORY);
    sb->index[0].offset = htonl(cd_offset);
    cd->magic = htonl(CSMAGIC_CODEDIRECTORY);
    cd->length = htonl(cd_size); cd->identOffset = htonl(sizeof(*cd));
    memcpy((char *)cd + sizeof(*cd), identifier, sizeof(identifier));
    memcpy(saved, signature, sizeof(signature));
    struct cs_blob blob = {.csb_flags = CS_VALID | CS_ADHOC, .csb_cd = cd,
        .csb_mem_kaddr = signature, .csb_mem_size = cd_offset + cd_size};
    file.blob = &blob;
    struct proc process = {&file, 0, 0};
    /* Negative control: actual native constructor flags, platform-only policy,
     * native exec mask and identity syscall reproduce ENOENT with a real ID. */
    assert(!(CS_ALLOWED_MACHO & CS_SIGNED));
    unsigned old_flags = blob.csb_flags | CS_PLATFORM_BINARY;
    process.csflags = native_exec_flags(old_flags);
    assert(process.csflags & CS_VALID);
    assert(!cs_identity_get(&process));
    assert(query(&process, CS_OPS_IDENTITY, output, sizeof(output)) == ENOENT);
    unsigned flags = blob.csb_flags;
    a6_platform_signature(&file, &blob, &flags, NULL);
    assert(flags == (old_flags | CS_SIGNED));
    process.csflags = native_exec_flags(flags);
    assert(process.csflags & CS_SIGNED);
    assert(!strcmp(cs_identity_get(&process), identifier));
    memset(output, 0xa5, sizeof(output));
    assert(!query(&process, CS_OPS_IDENTITY, output, sizeof(output)));
    uint32_t length; memcpy(&length, output + 4, 4);
    assert(!memcmp(output, "\0\0\0\0", 4));
    assert(ntohl(length) == 8 + sizeof(identifier));
    assert(!strcmp((char *)output + 8, identifier));
    assert(output[8 + sizeof(identifier)] == 0xa5);
    assert(query(&process, CS_OPS_IDENTITY, output, 7) == ERANGE);
    assert(query(&process, CS_OPS_IDENTITY, output, 8) == ERANGE);
    assert(query(&process, CS_OPS_IDENTITY, output, 8 + sizeof(identifier) - 1) == ERANGE);
    assert(!query(&process, CS_OPS_IDENTITY, output, 8 + sizeof(identifier)));
    copy_error_at = 1;
    assert(query(&process, CS_OPS_IDENTITY, output, sizeof(output)) == EFAULT);
    copy_error_at = 2;
    assert(query(&process, CS_OPS_IDENTITY, output, sizeof(output)) == EFAULT);
    copy_error_at = 0;
    assert(query(&process, CS_OPS_TEAMID, output, sizeof(output)) == ENOENT);
    for (unsigned test = 0; test < 7; ++test) {
        flags = CS_VALID; selected = test != 0;
        file.mount = test == 1 ? (void *)2 : (void *)1;
        file.regular = test != 2; amfi = test == 3 ? &provider : NULL;
        rootvnode = test == 4 ? NULL : &root;
        blob.csb_cd = test == 5 ? NULL : cd;
        a6_platform_signature(&file, test == 6 ? NULL : &blob, &flags, NULL);
        assert(!(flags & CS_SIGNED));
    }
    selected = 1; file.mount = (void *)1; file.regular = 1;
    rootvnode = &root; amfi = NULL; blob.csb_cd = cd;
    flags = CS_ADHOC;
    a6_platform_signature(&file, &blob, &flags, NULL);
    assert(!(flags & (CS_VALID | CS_SIGNED)));
    a6_platform_signature(&file, &blob, NULL, NULL);
    assert(!memcmp(saved, signature, sizeof(signature)));
    assert(blob.csb_flags == (CS_VALID | CS_ADHOC));
    puts("PASS: native exec/csops identity ENOENT reproduced and fixed; original identifier, ABI/error paths, root/provider/unsigned/invalid bounds and signature bytes preserved");
}
'''
with tempfile.TemporaryDirectory(prefix='codesign-identity-', dir=root / 'artifacts') as directory:
    p = Path(directory)
    (p / 'test.c').write_text(fixture)
    subprocess.run(['clang', '-std=gnu17', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-g', '-I'+str(root / 'xnu/osfmk'),
                    str(p / 'test.c'), '-o', str(p / 'test')], check=True)
    subprocess.run([str(p / 'test')], check=True)
