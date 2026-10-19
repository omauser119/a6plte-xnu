#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Ignore raw entitlement blobs without granting rights or inventing a provider."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
text = (ROOT / 'xnu/bsd/kern/ubc_subr.c').read_text()
start = text.index('\naccelerate_entitlement_queries(') + 1
opening = text.index('{', start)
end, depth = opening + 1, 1
while depth:
    depth += (text[end] == '{') - (text[end] == '}')
    end += 1
body = text[start:end]
source = r'''
#include <cassert>
#include <cstdio>
using kern_return_t = int;
using errno_t = int;
enum { KERN_SUCCESS = 0, KERN_NOT_SUPPORTED = 46, EPERM = 1, ENOTSUP = 45 };
struct cs_blob {
    void *csb_entitlements;
    void *csb_entitlements_blob;
    void *csb_der_entitlements_blob;
};
int calls = 0, result = 0;
int modern(void *ent, cs_blob *blob, const void *monitor) {
    assert(ent == blob->csb_entitlements && !monitor); ++calls; return result;
}
int legacy(void *ent, cs_blob *blob) {
    assert(ent == blob->csb_entitlements); ++calls; return result;
}
struct Provider {
    struct {
        int (*adjustContext)(void *, cs_blob *, const void *);
        int (*adjustContextWithoutMonitor)(void *, cs_blob *);
    } OSEntitlements;
} provider{{modern, legacy}}, *amfi = nullptr;
static errno_t
''' + body + r'''
int main() {
    cs_blob blob{};
#if A6PLTE
    assert(accelerate_entitlement_queries(&blob) == 0);
    for (unsigned mask = 1; mask != 8; ++mask) {
        blob = {mask & 1 ? &blob : nullptr, mask & 2 ? &blob : nullptr,
                mask & 4 ? &blob : nullptr};
        assert(accelerate_entitlement_queries(&blob) == (mask & 1 ? ENOTSUP : 0));
    }
    assert(calls == 0);
    blob = {};
    Provider missing{};
    amfi = &missing;
    assert(accelerate_entitlement_queries(&blob) == ENOTSUP);
#endif
    amfi = &provider;
    blob.csb_entitlements = &blob;
    assert(accelerate_entitlement_queries(&blob) == 0 && calls == 1);
    result = 5;
    assert(accelerate_entitlement_queries(&blob) == EPERM && calls == 2);
    provider.OSEntitlements.adjustContext = nullptr;
    result = 0;
    assert(accelerate_entitlement_queries(&blob) == 0 && calls == 3);
    result = 5;
    assert(accelerate_entitlement_queries(&blob) == EPERM && calls == 4);
}
'''
with tempfile.TemporaryDirectory(prefix='amfi-signature-', dir=ROOT / 'artifacts') as temp:
    temp = Path(temp)
    (temp / 'signature.cpp').write_text(source)
    for a6 in (0, 1):
        binary = str(temp / f'signature-{a6}')
        subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-g', '-DCODE_SIGNING_MONITOR=0',
                        f'-DA6PLTE={a6}', str(temp / 'signature.cpp'), '-o', binary], check=True)
        subprocess.run([binary], check=True)
print('Signature context: raw XML/DER ignored, orphaned context rejected, provider dispatch passed')
