#!/usr/bin/env python3
"""Pack a zero-slide, thin ARM64 MH_EXECUTE kernel (not an Apple kernel collection)."""
import argparse
import struct
import zlib
from pathlib import Path
HEADER = struct.Struct('<8sIIQQQQIIQ')

def pack(data):
    if len(data) < 32:
        raise ValueError('truncated Mach-O')
    magic, cpu, sub, kind, nc, commands, flags, _ = struct.unpack_from('<8I', data)
    if (magic, cpu, sub & 0xffffff, kind) != (0xfeedfacf, 0x100000c, 0, 2):
        raise ValueError('requires thin ARM64_ALL MH_EXECUTE, not ARM64e, fat, IMG4 or MH_FILESET')
    if commands > len(data)-32 or nc > commands//8:
        raise ValueError('invalid load command table')
    segments=[]; entry=None; off=32
    for _ in range(nc):
        cmd, size=struct.unpack_from('<II',data,off)
        if size<8 or size%8 or size>32+commands-off:
            raise ValueError('invalid load command size')
        if cmd==0x19:
            if size<72: raise ValueError('short segment')
            _,_,name,va,vs,fo,fs,maxp,prot,nsects,sflags=struct.unpack_from('<II16sQQQQiiII',data,off)
            if size != 72+80*nsects or fs>vs or fo>len(data) or fs>len(data)-fo or va+vs>2**64:
                raise ValueError('invalid segment bounds')
            if name.rstrip(b'\0') != b'__PAGEZERO' and vs:
                if va<0xffff000000000000: raise ValueError('kernel segment must have a high virtual address')
                segments.append((va,vs,fo,fs,prot))
        elif cmd==5:
            if size!=288 or struct.unpack_from('<II',data,off+8)!=(6,68):
                raise ValueError('requires ARM_THREAD_STATE64')
            entry=struct.unpack_from('<Q',data,off+16+32*8)[0]
        elif cmd in (0x80000034,0x80000035):
            raise ValueError('chained fixups/fileset are unsupported')
        off+=size
    if off!=32+commands or not segments or entry is None:
        raise ValueError('missing segments or LC_UNIXTHREAD')
    segments.sort(); base=segments[0][0]; end=max(v+s for v,s,*_ in segments)
    if base%0x4000 or end-base>64*1024*1024 or entry%4:
        raise ValueError('invalid kernel alignment/size/entry')
    for a,b in zip(segments,segments[1:]):
        if a[0]+a[1]>b[0]: raise ValueError('overlapping VM segments')
    if not any(v<=entry<v+fs and prot&4 for v,vs,fo,fs,prot in segments):
        raise ValueError('entry is outside file-backed executable segment')
    if not any(v==base and fo==0 and fs>=32 for v,vs,fo,fs,prot in segments):
        raise ValueError('Mach header must reside at virtBase')
    image=bytearray((end-base+0x3fff)&~0x3fff)
    for va,vs,fo,fs,_ in segments:
        image[va-base:va-base+fs]=data[fo:fo+fs]
    return HEADER.pack(b'A6XNU01\0',1,HEADER.size,base,entry,len(image),len(image),zlib.crc32(image),0,0)+image

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('kernel',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args()
    try: result=pack(a.kernel.read_bytes())
    except ValueError as e: p.error(str(e))
    a.output.write_bytes(result)
    print(f'{a.output}: {len(result)} bytes. Requires a Cortex-A53/A6PLTE kernel; not a stock macOS kernel.')
if __name__=='__main__': main()
