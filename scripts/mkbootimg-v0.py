#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Write the legacy Android boot image v0 layout used by this board (no signing)."""
import argparse, hashlib, struct
from pathlib import Path

def build(kernel, ramdisk, page, base, kernel_offset, ramdisk_offset, tags_offset, board, cmdline):
    if page not in (2048,4096,8192,16384):
        raise ValueError('unsupported page size')
    if not kernel: raise ValueError('empty kernel')
    board=board.encode('ascii');cmdline=cmdline.encode('ascii')
    if len(board)>15 or len(cmdline)>1535 or b'\0' in board+cmdline:
        raise ValueError('board/cmdline too long or contains NUL')
    def address(offset):
        value=base+offset
        if not 0<=value<2**32: raise ValueError('address exceeds v0 field')
        return value
    digest=hashlib.sha1()
    for data in (kernel,ramdisk,b''):
        digest.update(data);digest.update(struct.pack('<I',len(data)))
    header=struct.pack('<8s10I16s512s32s1024s',b'ANDROID!',
        len(kernel),address(kernel_offset),len(ramdisk),address(ramdisk_offset) if ramdisk else 0,
        0,0,address(tags_offset),page,0,0,
        board,cmdline[:512],digest.digest(),cmdline[512:])
    def pad(data): return data+b'\0'*((-len(data))%page)
    return pad(header)+pad(kernel)+pad(ramdisk)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('kernel','output'): p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--ramdisk',type=Path)
    for name,default in [('pagesize',2048),('base',0x80000000),('kernel_offset',0x80000),
                         ('ramdisk_offset',0x2000000),('tags_offset',0x1e00000)]:
        p.add_argument('--'+name,type=lambda s:int(s,0),default=default)
    p.add_argument('--header_version',type=int,choices=[0],default=0)
    p.add_argument('--board',default='a6plte');p.add_argument('--cmdline',default='')
    a=p.parse_args()
    image=build(a.kernel.read_bytes(),a.ramdisk.read_bytes() if a.ramdisk else b'',
                a.pagesize,a.base,a.kernel_offset,a.ramdisk_offset,a.tags_offset,a.board,a.cmdline)
    a.output.write_bytes(image)
