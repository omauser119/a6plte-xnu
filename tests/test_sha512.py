#!/usr/bin/env python3
"""Compare the actual scalar SHA2 code with hashlib across chunks and alignments."""
from pathlib import Path
import hashlib
import random
import struct
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
driver = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "a6plte_sha512.h"
int main(void) {
    uint32_t h[4];
    while (fread(h, sizeof(h), 1, stdin) == 1) {
        assert((h[0] == 48 || h[0] == 64) && h[1] <= 1048576 && h[2] && h[3] < 16);
        uint8_t *allocation = malloc((size_t)h[1] + 16), output[80];
        assert(allocation);
        uint8_t *p = allocation + h[3];
        assert(fread(p, 1, h[1], stdin) == h[1]);
        struct a6_sha512 ctx;
        a6_sha512_init(&ctx, h[0]);
        a6_sha512_update(&ctx, NULL, 0);
        for (uint32_t i = 0; i < h[1];) {
            uint32_t n = h[1] - i; if (n > h[2]) n = h[2];
            a6_sha512_update(&ctx, p + i, n); i += n;
        }
        memset(output, 0xa5, sizeof(output));
        a6_sha512_final(&ctx, output + 3, h[0]);
        for (unsigned i = 0; i < sizeof(ctx); ++i) assert(!((uint8_t *)&ctx)[i]);
        for (unsigned i = 0; i < sizeof(output); ++i)
            if (i < 3 || i >= 3 + h[0]) assert(output[i] == 0xa5);
        assert(fwrite(output + 3, 1, h[0], stdout) == h[0]);
        free(allocation);
    }
}
'''
rng = random.Random(8796)
cases = []
for size in (0, 1, 3, 7, 63, 64, 111, 112, 113, 127, 128, 129, 255, 256, 257, 4096):
    for chunk in (1, 7, 111, 128, 4096):
        for output in (48, 64):
            cases.append((output, rng.randbytes(size), chunk, rng.randrange(16)))
for data in (b'', b'abc', b'a' * 1000000):
    for output in (48, 64):
        cases.append((output, data, 1703, 1))
for _ in range(500):
    cases.append((rng.choice((48, 64)), rng.randbytes(rng.randrange(8193)), rng.randrange(1, 1025), rng.randrange(16)))
wire = b''.join(struct.pack('<4I', output, len(data), chunk, offset) + data for output, data, chunk, offset in cases)
expected = b''.join((hashlib.sha384 if output == 48 else hashlib.sha512)(data).digest() for output, data, _, _ in cases)
with tempfile.TemporaryDirectory(prefix='sha512-', dir=root / 'artifacts') as directory:
    directory = Path(directory)
    (directory / 'driver.c').write_text(driver)
    binary = directory / 'test'
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-g',
                    '-fsanitize=address,undefined', '-I'+str(root/'xnu/libkern/crypto'),
                    str(directory/'driver.c'), str(root/'xnu/libkern/crypto/a6plte_sha512.c'), '-o', str(binary)], check=True)
    actual = subprocess.check_output([str(binary)], input=wire)
    assert actual == expected
print(f'PASS: SHA-384/SHA-512, {len(cases)} vectors including million bytes, padding/chunks/alignment and erasure')
