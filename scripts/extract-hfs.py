#!/usr/bin/env python3
"""Extract flat HFS+ sectors from a layout-NONE UDRW image created by hdiutil."""
import struct,sys
from pathlib import Path

def extract(data):
    if len(data)<2048 or data[1024:1026] not in (b'H+',b'HX'):
        raise ValueError('expected raw HFS+ volume at offset zero')
    block,blocks=struct.unpack_from('>II',data,1024+40)
    size=block*blocks
    if block<512 or block&(block-1) or not size or size>64*1024*1024 or size%4096 or size>len(data):
        raise ValueError('invalid HFS+ allocation geometry')
    if data[size-1024:size-1022]!=data[1024:1026]:
        raise ValueError('missing HFS+ alternate volume header')
    if data[size-1024+40:size-1024+48]!=data[1024+40:1024+48]:
        raise ValueError('HFS+ volume headers disagree on allocation geometry')
    if len(data)!=size:
        if len(data)<size+512 or data[-512:-508]!=b'koly':
            raise ValueError('expected uncompressed UDRW footer')
        offset,length=struct.unpack_from('>QQ',data,len(data)-512+24)
        if offset or length<size or length>len(data)-512:
            raise ValueError('UDRW sectors are not flat at offset zero')
    return data[:size]

if __name__=='__main__':
    disk=extract(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2]).write_bytes(disk)
    print(f'{sys.argv[2]}: {len(disk)} raw HFS+ bytes, primary/alternate headers checked')
