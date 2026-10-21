#!/usr/bin/env python3
"""Exercise actual registry publication, boot-hash reader and native sysctl."""
from pathlib import Path
import hashlib
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


expert = (root / 'xnu/iokit/Kernel/arm/A6PLTEPlatformExpert.cpp').read_text()
iokit = (root / 'xnu/iokit/bsddev/IOKitBSDInit.cpp').read_text()
sysctl = (root / 'xnu/bsd/kern/kern_sysctl.c').read_text()
expected = hashlib.sha384(b'A6PLTE standalone boot identity v1' + bytes(range(16))).hexdigest().upper()
fixture = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <cstdio>
#include <string>
#include <vector>
#include <openssl/sha.h>
using SHA384_CTX = SHA512_CTX;
#define __unused __attribute__((unused))
#define STATIC static
#define MAXPATHLEN 1024
#define CCSHA384_OUTPUT_SIZE 48
#define bzero(p,n) memset(p,0,n)
struct OSObject { virtual ~OSObject() = default; };
struct OSData : OSObject {
    std::vector<uint8_t> bytes;
    unsigned getLength() const { return bytes.size(); }
    const void *getBytesNoCopy() const { return bytes.data(); }
};
#define OSDynamicCast(type,value) dynamic_cast<type *>(value)
static const void *gIODTPlane = (void *)1;
static int refs, writes, lookup_failure, set_failure;
struct IORegistryEntry {
    OSObject *property = nullptr;
    OSData generated;
    static IORegistryEntry *fromPath(const char *, const void *);
    OSObject *getProperty(const char *key) {
        assert(!strcmp(key,"boot-manifest-hash")); return property;
    }
    bool setProperty(const char *key, const void *data, unsigned length) {
        assert(!strcmp(key,"boot-manifest-hash") && length == 48); ++writes;
        if (set_failure) return false;
        generated.bytes.assign((const uint8_t *)data,(const uint8_t *)data+length);
        property = &generated; return true;
    }
    void release() { assert(refs > 0); --refs; }
} chosen;
IORegistryEntry *IORegistryEntry::fromPath(const char *path, const void *plane) {
    assert(!strcmp(path,"/chosen") && plane == gIODTPlane);
    if (lookup_failure) return nullptr; ++refs; return &chosen;
}
#define OSSafeReleaseNULL(object) do { if(object) (object)->release(); (object)=nullptr; } while(0)
static int _mh_execute_header;
static uint8_t image_uuid[16];
static unsigned long uuid_size = 16;
static int uuid_missing;
static void *getuuidfromheader(int *header, unsigned long *length) {
    assert(header == &_mh_execute_header); *length=uuid_size;
    return uuid_missing ? nullptr : image_uuid;
}
static bool IOGetBootObjectsPath(char *) { return false; }
struct sysctl_oid {};
struct sysctl_req { std::string result; int copy_error = 0; };
static int sysctl_io_string(sysctl_req *request,char *value,int size,int trunc,void *out) {
    assert(!size && !trunc && !out); if(request->copy_error)return request->copy_error;
    request->result=value; return 0;
}
'''
fixture += body(expert, 'static bool a6_publish_boot_hash(void)')
fixture += body(iokit, 'bool\nIOGetBootManifestHash(')
fixture += body(sysctl, 'STATIC int\nsysctl_bootobjectspath').replace('#if defined(__x86_64__)', '#if 0')
fixture += r'''
static void expect_missing() {
    sysctl_req req;
    assert(sysctl_bootobjectspath(nullptr,nullptr,0,&req)==ENOENT && req.result.empty());
    assert(!refs);
}
int main() {
    for(unsigned i=0;i<16;++i) image_uuid[i]=i;
    /* The unchanged native query reproduces the reported missing metadata. */
    expect_missing();
    assert(a6_publish_boot_hash() && writes==1 && !refs);
    assert(chosen.generated.getLength()==48);
    sysctl_req req;
    assert(!sysctl_bootobjectspath(nullptr,nullptr,0,&req));
    assert(req.result == EXPECTED_HASH && req.result.size()==96);
    uint8_t buffer[64]; memset(buffer,0xa5,sizeof(buffer)); size_t length=48;
    assert(IOGetBootManifestHash((char *)buffer,&length) && length==48);
    assert(!memcmp(buffer,chosen.generated.bytes.data(),48));
    for(unsigned i=48;i<sizeof(buffer);++i) assert(buffer[i]==0xa5);
    auto first=chosen.generated.bytes;
    assert(a6_publish_boot_hash() && writes==1 && chosen.generated.bytes==first && !refs);
    req.copy_error=EFAULT;
    assert(sysctl_bootobjectspath(nullptr,nullptr,0,&req)==EFAULT && !refs);
    chosen.property=nullptr;
    assert(a6_publish_boot_hash() && chosen.generated.bytes==first && !refs);
    image_uuid[0]^=1; chosen.property=nullptr;
    assert(a6_publish_boot_hash() && chosen.generated.bytes!=first && !refs);
    image_uuid[0]^=1;
    OSData real;
    for(unsigned size : {20U,48U}) {
        real.bytes.assign(size,0x5a); chosen.property=&real; int before=writes;
        assert(a6_publish_boot_hash() && chosen.property==&real && writes==before);
        length=48; memset(buffer,0xa5,sizeof(buffer));
        assert(IOGetBootManifestHash((char *)buffer,&length) && length==size);
        for(unsigned i=0;i<48;++i) assert(buffer[i]==(i<size?0x5a:0));
        req.copy_error=0;
        assert(!sysctl_bootobjectspath(nullptr,nullptr,0,&req) && req.result.size()==size*2);
        assert(!refs);
    }
    for(unsigned size : {0U,19U,21U,47U,49U}) {
        real.bytes.assign(size,0x5a); chosen.property=&real; int before=writes;
        assert(!a6_publish_boot_hash() && chosen.property==&real && writes==before && !refs);
    }
    OSObject wrong_type; chosen.property=&wrong_type;
    assert(!a6_publish_boot_hash() && !refs);
    chosen.property=nullptr; set_failure=1;
    assert(!a6_publish_boot_hash() && chosen.property==nullptr && !refs);
    set_failure=0;
    for(unsigned size : {0UL,15UL,17UL}) {
        uuid_size=size; assert(!a6_publish_boot_hash() && !chosen.property && !refs);
    }
    uuid_size=16; uuid_missing=1;
    assert(!a6_publish_boot_hash() && !chosen.property && !refs);
    uuid_missing=0; lookup_failure=1;
    assert(!a6_publish_boot_hash() && !chosen.property && !refs);
    puts("PASS: native boot-hash ENOENT reproduced and fixed; SHA384/UUID identity, native registry/sysctl readers, stable reboot/changed-image values, firmware preservation and resource/error bounds");
}
'''
fixture = '#define EXPECTED_HASH "'+expected+'"\n'+fixture
with tempfile.TemporaryDirectory(prefix='boot-hash-', dir=root / 'artifacts') as directory:
    p = Path(directory)
    (p / 'test.cpp').write_text(fixture)
    subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-Wno-deprecated-declarations',
                    '-fsanitize=address,undefined', '-g', str(p / 'test.cpp'),
                    '-lcrypto', '-o', str(p / 'test')], check=True)
    subprocess.run([str(p / 'test')], check=True)
