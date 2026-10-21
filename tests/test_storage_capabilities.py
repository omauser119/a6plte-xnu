#!/usr/bin/env python3
"""Check the board's presence-only storage flag through the native data setter."""
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


expert = (root / 'xnu/iokit/Kernel/arm/A6PLTEPlatformExpert.cpp').read_text()
registry = (root / 'xnu/iokit/Kernel/IORegistryEntry.cpp').read_text()
fixture = r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#include <map>
#include <string>
#include <vector>
struct OSObject { virtual ~OSObject() = default; };
static bool allocation_failure, publication_failure, lookup_failure;
static unsigned refs, writes, data_refs;
struct OSSymbol {
    std::string name;
    static const OSSymbol *withCString(const char *name) { return new OSSymbol{name}; }
    void release() const { delete this; }
};
struct OSData : OSObject {
    std::vector<unsigned char> bytes;
    static OSData *withBytes(const void *input, unsigned length) {
        if (allocation_failure) return nullptr;
        assert(input || !length);
        auto *data = new OSData;
        if (length) data->bytes.assign((const unsigned char *)input,
                                       (const unsigned char *)input+length);
        ++data_refs; return data;
    }
    void release() { assert(data_refs); --data_refs; delete this; }
};
static const void *gIODTPlane = (void *)1;
struct IORegistryEntry {
    std::map<std::string, std::vector<unsigned char>> values;
    OSObject present;
    static IORegistryEntry *fromPath(const char *, const void *);
    OSObject *getProperty(const char *name) {
        return values.count(name) ? &present : nullptr;
    }
    bool setProperty(const char *name, void *input, unsigned length);
    bool setProperty(const OSSymbol *key, OSData *data) {
        ++writes;
        if (publication_failure) return false;
        values[key->name] = data->bytes; return true;
    }
    void release() { assert(refs); --refs; }
} defaults;
IORegistryEntry *IORegistryEntry::fromPath(const char *path, const void *plane) {
    assert(!strcmp(path,"/defaults") && plane == gIODTPlane);
    if (lookup_failure) return nullptr;
    ++refs; return &defaults;
}
'''
fixture += body(registry, 'bool\nIORegistryEntry::setProperty( const char *      aKey,\n    void *            bytes,')
fixture += body(expert, 'static bool a6_publish_storage_capabilities(void)')
fixture += r'''
int main() {
    /* Missing differs from present-but-empty for the native registry ABI. */
    assert(!defaults.getProperty("no-effaceable-storage"));
    assert(a6_publish_storage_capabilities() && !refs && !data_refs);
    assert(defaults.getProperty("no-effaceable-storage"));
    assert(defaults.values.at("no-effaceable-storage").empty() && writes == 1);
    assert(!defaults.getProperty("content-protect"));
    assert(defaults.values.size() == 1);
    assert(a6_publish_storage_capabilities() && writes == 1 && !refs && !data_refs);
    /* Existing firmware flags are presence-only, regardless of payload. */
    defaults.values["no-effaceable-storage"] = {1,0,0,0};
    auto existing = defaults.values;
    assert(a6_publish_storage_capabilities() && defaults.values == existing && writes == 1);
    defaults.values.clear();
    allocation_failure = true;
    assert(!a6_publish_storage_capabilities() && defaults.values.empty() && !refs && !data_refs);
    allocation_failure = false; publication_failure = true;
    assert(!a6_publish_storage_capabilities() && defaults.values.empty() && !refs && !data_refs);
    publication_failure = false; lookup_failure = true;
    assert(!a6_publish_storage_capabilities() && defaults.values.empty() && !refs && !data_refs);
    lookup_failure = false;
    /* Capability publication must not erase unrelated DT metadata. */
    defaults.values["unrelated"] = {9,8,7};
    assert(a6_publish_storage_capabilities() && !refs && !data_refs);
    assert((defaults.values.at("unrelated") == std::vector<unsigned char>{9,8,7}));
    puts("PASS: board no-effaceable-storage presence, native OSData setter, firmware preservation and publication/reference errors");
}
'''
with tempfile.TemporaryDirectory(prefix='storage-capabilities-', dir=root / 'artifacts') as directory:
    path = Path(directory)
    (path / 'test.cpp').write_text(fixture)
    subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-g', str(path / 'test.cpp'),
                    '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
