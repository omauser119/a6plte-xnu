import importlib.util
import struct
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('pack_xnu',Path(__file__).resolve().parents[1]/'scripts/pack-xnu.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def fixture():
    base=0xfffffff007004000
    header=struct.pack('<8I',0xfeedfacf,0x100000c,0,2,2,72+288,0,0)
    segment=struct.pack('<II16sQQQQiiII',0x19,72,b'__TEXT',base,0x4000,0,0x1000,7,5,0,0)
    state=bytearray(272); struct.pack_into('<Q',state,32*8,base+0x400)
    thread=struct.pack('<4I',5,288,6,68)+state
    return bytearray((header+segment+thread).ljust(0x1000,b'\0'))

class TestPack(unittest.TestCase):
    def test_ramdisk_v2(self):
        disk=bytes(range(256))*16
        result=m.pack(fixture(),disk);h=m.HEADER.unpack_from(result)
        self.assertEqual(h[:3],(b'A6XNU02\0',2,64))
        self.assertEqual(h[5],0x4000)
        self.assertEqual(h[6],0x5000)
        self.assertEqual(h[8:],(1,0x1000))
        self.assertEqual(result[64+h[5]:],disk)
        self.assertEqual(h[7],m.zlib.crc32(result[64:]))
        for invalid in (b'',b'x',bytes(4097)):
            with self.assertRaises(ValueError):m.pack(fixture(),invalid)
    def test_zero_fill_and_crc(self):
        result=m.pack(fixture()); h=m.HEADER.unpack_from(result)
        self.assertEqual(h[0],b'A6XNU01\0'); self.assertEqual(h[5],0x4000)
        self.assertEqual(result[64+0x1000:],bytes(0x3000))
        self.assertEqual(h[7],m.zlib.crc32(result[64:]))
    def test_reject_arm64e(self):
        d=fixture(); struct.pack_into('<I',d,8,2)
        with self.assertRaises(ValueError): m.pack(d)
    def test_reject_fileset(self):
        d=fixture(); struct.pack_into('<I',d,12,12)
        with self.assertRaises(ValueError): m.pack(d)
    def test_reject_out_of_file(self):
        d=fixture(); struct.pack_into('<Q',d,32+48,0x2000)
        with self.assertRaises(ValueError): m.pack(d)
    def test_reject_nonexec_entry(self):
        d=fixture(); struct.pack_into('<i',d,32+60,1)
        with self.assertRaises(ValueError): m.pack(d)
    def test_reject_bad_command(self):
        d=fixture(); struct.pack_into('<I',d,36,8)
        with self.assertRaises(ValueError): m.pack(d)
    def test_reject_truncated(self):
        with self.assertRaises(ValueError): m.pack(fixture()[:30])
if __name__=='__main__': unittest.main()
