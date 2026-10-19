#!/usr/bin/env python3
"""Check the first static ARM64 Darwin process, including its actual entry point."""
import struct,sys
from pathlib import Path
b=Path(sys.argv[1]).read_bytes()
magic,cpu,sub,kind,ncmds,commands,flags,_=struct.unpack_from('<8I',b)
assert (magic,cpu,sub&0xffffff,kind)==(0xfeedfacf,0x100000c,0,2)
assert flags&1, 'process must have no unresolved symbols'
off=32;entry=None;segments=[]
for _ in range(ncmds):
    cmd,size=struct.unpack_from('<II',b,off)
    assert 8<=size<=32+commands-off
    assert cmd not in (0xc,0xe,0x80000018,0x8000001f), 'probe must run without dyld or runtime dylibs'
    if cmd==0x19:
        va,vs,fo,fs,maxp,prot=struct.unpack_from('<QQQQii',b,off+24)
        assert fs<=vs and fo<=len(b) and fs<=len(b)-fo
        if fs:segments.append((va,fo,fs,prot))
    elif cmd==5:
        assert size==288 and struct.unpack_from('<II',b,off+8)==(6,68)
        entry=struct.unpack_from('<Q',b,off+16+32*8)[0]
    off+=size
assert off==32+commands and entry is not None
assert any(va<=entry<va+fs and prot&4 for va,fo,fs,prot in segments)
assert entry<0xffff000000000000
print(f'PASS: static ARM64 PID1, LC_UNIXTHREAD entry {entry:#x}, no dyld/dylib dependency')
