#!/usr/bin/env python3
"""Reject absolute pointer tables in code used before the MMU is enabled."""
import struct,sys
from pathlib import Path

def check(path):
    data=path.read_bytes()
    magic,cpu,subtype,kind,ncmds,commands,flags,reserved=struct.unpack_from('<8I',data)
    assert (magic,cpu,kind)==(0xfeedfacf,0x100000c,1),'expected ARM64 Mach-O object'
    offset=32
    for _ in range(ncmds):
        command,length=struct.unpack_from('<2I',data,offset)
        assert 8<=length<=len(data)-offset
        if command==0x19:
            nsects=struct.unpack_from('<I',data,offset+64)[0]
            assert 72+80*nsects<=length
            for n in range(nsects):
                section=offset+72+80*n
                name=data[section:section+16].split(b'\0')[0].decode()
                rel,records=struct.unpack_from('<2I',data,section+56)
                assert rel+records*8<=len(data)
                # Unwind/debug metadata is not read by the physical console.
                if name=='__compact_unwind' or name.startswith('__debug'):continue
                for r in range(records):
                    address,info=struct.unpack_from('<2I',data,rel+r*8)
                    assert (info>>28)!=0, f'{path}: absolute pointer relocation in {name}+{address:#x}; unsafe before MMU'
        offset+=length
    assert offset==32+commands

if __name__=='__main__':
    for arg in sys.argv[1:]:check(Path(arg))
    print('PASS: physical framebuffer objects contain no absolute pointer relocations')
