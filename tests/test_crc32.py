#!/usr/bin/env python3
"""Verify package CRC compatibility against Python/zlib, including streaming."""
import ctypes
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
import zlib

class PackageCRC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(__file__).resolve().parents[1]
        library = Path(cls.tmp.name)/'crc32.so'
        subprocess.run(['clang', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                        str(root/'shim/crc32.c'), '-o', str(library)], check=True)
        cls.library = ctypes.CDLL(str(library))
        cls.crc = cls.library.a6_crc32
        cls.crc.argtypes = (ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t)
        cls.crc.restype = ctypes.c_uint32

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def calculate(self, data, seed=0):
        buf = ctypes.create_string_buffer(data)
        return self.crc(seed, buf, len(data))

    def test_standard_vector(self):
        self.assertEqual(self.calculate(b'123456789'), 0xcbf43926)
        self.assertEqual(self.calculate(b''), 0)

    def test_zlib_and_streaming(self):
        rng = random.Random(53)
        for size in (1, 15, 16, 4095, 4096, 131073):
            data = rng.randbytes(size)
            expected = zlib.crc32(data)
            self.assertEqual(self.calculate(data), expected)
            crc = 0
            for start in range(0, size, 113):
                crc = self.calculate(data[start:start+113], crc)
            self.assertEqual(crc, expected)

if __name__ == '__main__':
    unittest.main()
