#!/usr/bin/env python3
"""Exercise the actual legacy SHA1 wrappers and native ccdigest ABI without a kext."""
from pathlib import Path
import hashlib
import os
import random
import struct
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
xnu = root / 'xnu'
wrapper = (xnu / 'libkern/crypto/corecrypto_sha1.c').read_text()
if os.environ.get('A6_SHA1_BASELINE'):
    wrapper = subprocess.check_output(
        ['git', '-C', str(xnu), 'show', 'HEAD:libkern/crypto/corecrypto_sha1.c'], text=True)
# Keep the actual hashing functions; the unrelated hardware-kext hook needs IOKit.
wrapper = wrapper.split('/*\n * This function is called by the SHA1 hardware kext')[0]
wrapper = '\n'.join(line for line in wrapper.splitlines() if not line.startswith('#include'))
selector = (xnu / 'bsd/nfs/gss/ccrypto.c').read_text()
selector = selector.split('const struct ccdigest_info *\nccsha1_di(void)', 1)[1]
selector = 'const struct ccdigest_info *\nccsha1_di(void)' + selector.split('\nvoid\nccdes_key_set_odd_parity', 1)[0]

prefix = r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define KERNEL 1
#include <libkern/crypto/sha1.h>
#undef KERNEL
#include <corecrypto/ccdigest.h>
#include <corecrypto/ccsha1.h>
/* Only the external provider fixture is modeled; all digest/context types,
 * wrappers, streaming, finalization and compression use the real XNU source. */
static struct provider {
    void (*ccdigest_init_fn)(const struct ccdigest_info *, ccdigest_ctx_t);
    void (*ccdigest_update_fn)(const struct ccdigest_info *, ccdigest_ctx_t, size_t, const void *);
    const struct ccdigest_info *ccsha1_di;
} *g_crypto_funcs;
'''
driver = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
static unsigned init_calls, update_calls;
static struct ccdigest_info provider_di;
static void provider_init(const struct ccdigest_info *di, ccdigest_ctx_t ctx) {
    assert(di == &provider_di); ++init_calls; ccdigest_init(di, ctx);
}
static void provider_update(const struct ccdigest_info *di, ccdigest_ctx_t ctx, size_t n, const void *p) {
    assert(di == &provider_di); ++update_calls; ccdigest_update(di, ctx, n, p);
}
int main(void) {
    uint32_t h[4];
    provider_di = ccsha1_ltc_di;
    struct provider provider = {provider_init, provider_update, &provider_di};
    assert(ccsha1_ltc_di.output_size == 20 && ccsha1_ltc_di.state_size == 20);
    assert(ccsha1_ltc_di.block_size == 64 && ccsha1_ltc_di.oid_size == 7);
    assert(!memcmp(ccsha1_ltc_di.oid, CC_DIGEST_OID_SHA1, 7));
    while (fread(h, sizeof(h), 1, stdin) == 1) {
        assert(h[0] <= 1048576 && h[1] && h[2] < 16 && h[3] < 2);
        uint8_t *allocation = malloc((size_t)h[0] + 16), output[32];
        assert(allocation);
        uint8_t *data = allocation + h[2];
        assert(fread(data, 1, h[0], stdin) == h[0]);
        g_crypto_funcs = h[3] ? &provider : NULL;
        assert(ccsha1_di() == (h[3] ? &provider_di : &ccsha1_ltc_di));
        init_calls = update_calls = 0;
        struct { uint64_t before; SHA1_CTX ctx; uint64_t after; } guarded;
        memset(&guarded, 0xa5, sizeof(guarded));
        SHA1Init(&guarded.ctx);
        SHA1Update(&guarded.ctx, NULL, 0);
        unsigned updates = 1;
        for (uint32_t i = 0; i < h[0];) {
            uint32_t n = h[0] - i; if (n > h[1]) n = h[1];
            SHA1Update(&guarded.ctx, data + i, n); i += n; ++updates;
        }
        assert(guarded.ctx.c.b64[0] == h[0]);
        SHA1_CTX snapshot = guarded.ctx;
        memset(output, 0xa5, sizeof(output));
        SHA1Final(output + 3, &guarded.ctx);
        assert(!memcmp(&snapshot, &guarded.ctx, sizeof(snapshot)));
        assert(guarded.before == UINT64_C(0xa5a5a5a5a5a5a5a5));
        assert(guarded.after == UINT64_C(0xa5a5a5a5a5a5a5a5));
        for (unsigned i = 0; i < sizeof(output); ++i)
            if (i < 3 || i >= 23) assert(output[i] == 0xa5);
        uint8_t reverse[20];
        SHA1Final_r(&guarded.ctx, reverse);
        assert(!memcmp(reverse, output + 3, 20));
        assert(init_calls == h[3] && update_calls == (h[3] ? updates : 0));
        assert(fwrite(output + 3, 1, 20, stdout) == 20);
        free(allocation);
    }
}
'''

rng = random.Random(8796)
cases = []
vectors = [b'', b'abc', b'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq', b'a' * 1000000]
for data in vectors:
    for provider in (0, 1):
        cases.append((data, 1703, 1, provider))
for size in (0, 1, 3, 7, 55, 56, 57, 63, 64, 65, 119, 120, 127, 128, 129, 255, 4096):
    for chunk in (1, 7, 63, 64, 4096):
        for provider in (0, 1):
            cases.append((rng.randbytes(size), chunk, rng.randrange(16), provider))
for _ in range(300):
    cases.append((rng.randbytes(rng.randrange(8193)), rng.randrange(1, 1025), rng.randrange(16), rng.randrange(2)))
wire = b''.join(struct.pack('<4I', len(data), chunk, offset, provider) + data
                for data, chunk, offset, provider in cases)
expected = b''.join(hashlib.sha1(data).digest() for data, _, _, _ in cases)
with tempfile.TemporaryDirectory(prefix='sha1-', dir=root / 'artifacts') as directory:
    directory = Path(directory)
    source = directory / 'driver.c'
    source.write_text(prefix + wrapper + selector + driver)
    binary = directory / 'test'
    sources = [xnu / 'libkern/crypto/a6plte_sha1_digest.c']
    sources += [xnu / 'osfmk/corecrypto' / name for name in
                ('ccdigest_init.c', 'ccdigest_update.c', 'ccdigest_final_64be.c', 'cc_clear.c')]
    subprocess.run(['clang', '-std=gnu17', '-Wall', '-Wextra', '-Werror', '-g',
                    '-fsanitize=address,undefined', '-DXNU_KERNEL_PRIVATE=1', '-DA6PLTE=1',
                    '-I'+str(xnu/'EXTERNAL_HEADERS'), '-I'+str(xnu/'EXTERNAL_HEADERS/corecrypto'),
                    '-I'+str(xnu/'libkern'), str(source), *map(str, sources), '-o', str(binary)], check=True)
    actual = subprocess.check_output([str(binary)], input=wire)
    assert actual == expected
print(f'PASS: native SHA1 wrappers/ccdigest ABI, {len(cases)} vectors; absent/present provider, padding, chunks, alignment and guards')
