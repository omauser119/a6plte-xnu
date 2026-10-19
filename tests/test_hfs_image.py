import importlib.util,struct,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('extract_hfs',Path(__file__).resolve().parents[1]/'scripts/extract-hfs.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixture():
    b=bytearray(4096)
    for off in (1024,3072):
        b[off:off+2]=b'H+'
        struct.pack_into('>H',b,off+2,4)
        struct.pack_into('>II',b,off+40,512,8)
    return b
class TestHFSImage(unittest.TestCase):
    def test_raw_and_udrw(self):
        b=fixture();self.assertEqual(m.extract(b),b)
        footer=bytearray(512);footer[:4]=b'koly';struct.pack_into('>QQ',footer,24,0,len(b))
        self.assertEqual(m.extract(b+footer),b)
        struct.pack_into('>QQ',footer,24,512,len(b))
        with self.assertRaises(ValueError):m.extract(b+footer)
    def test_corrupt_geometry(self):
        for offset,value in ((1024,0),(3072,0),(1064,0),(3112,1)):
            b=fixture();struct.pack_into('>I',b,offset,value)
            with self.assertRaises(ValueError):m.extract(b)
        with self.assertRaises(ValueError):m.extract(fixture()[:-1])
        with self.assertRaises(ValueError):m.extract(fixture()+bytes(512))
if __name__=='__main__':unittest.main()
