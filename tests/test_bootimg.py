# SPDX-License-Identifier: BSD-2-Clause
import hashlib, importlib.util, struct, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('bootimg',Path(__file__).resolve().parents[1]/'scripts/mkbootimg-v0.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BootImage(unittest.TestCase):
    def make(self,k=b'kernel',r=b'',cmd='test',base=0x80000000):
        return m.build(k,r,2048,base,0x80000,0x20000000,0x1e00000,'a6plte',cmd)
    def test_layout(self):
        k=b'K'*3000;r=b'R'*17;b=self.make(k,r,'a'*600)
        self.assertEqual(b[:8],b'ANDROID!')
        self.assertEqual(struct.unpack_from('<10I',b,8),(3000,0x80080000,17,0xa0000000,0,0,0x81e00000,2048,0,0))
        self.assertEqual(b[2048:5048],k);self.assertEqual(b[6144:6161],r)
        self.assertEqual(len(b),8192)
        self.assertEqual(b[64:576],b'a'*512);self.assertEqual(b[608:696],b'a'*88)
        h=hashlib.sha1()
        for d in (k,r,b''):h.update(d);h.update(struct.pack('<I',len(d)))
        self.assertEqual(b[576:608],h.digest()+b'\0'*12)
    def test_empty_ramdisk_address(self):
        self.assertEqual(struct.unpack_from('<I',self.make(),20)[0],0)
    def test_reject_invalid(self):
        for kwargs in ({'k':b''},{'cmd':'a'*1536},{'base':2**32},{'cmd':'a\0b'}):
            with self.assertRaises(ValueError):self.make(**kwargs)
if __name__=='__main__':unittest.main()
