#!/usr/bin/env python3
"""Check the complete kernel-only Android image and its explicit userdata root profile."""
import importlib.util, struct, subprocess, sys, zlib
from pathlib import Path

root=Path(__file__).resolve().parents[1]
kernel,image=map(Path,sys.argv[1:])
spec=importlib.util.spec_from_file_location('pack',root/'scripts/pack-xnu.py')
pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)
k=kernel.read_bytes();b=image.read_bytes()
assert b'Darwin Kernel Version 22.6.0:' in k
assert b'xnu-8796.141.3/DEVELOPMENT_ARM64_A6PLTE' in k
assert struct.unpack_from('<4I',k)==(0xfeedfacf,0x100000c,0,2)
assert not subprocess.check_output(['llvm-nm','--undefined-only',str(kernel)],text=True).strip()
symbols=subprocess.check_output(['llvm-nm',str(kernel)],text=True)
for name in ('_a6_userdata_root','_a6_userdata_root_selected','_IOA6UserdataBSDRoot','_a6_hfs_volume_check','_hfs_vfsops'):
    assert name in symbols,name
assert b[:8]==b'ANDROID!'
ks,ka,rs,ra,ss,sa,tags,page=struct.unpack_from('<8I',b,8)
assert (ka,ra,ss,sa,tags,page)==(0x80080000,0xa0000000,0,0,0x81e00000,2048)
align=lambda n:(n+page-1)&~(page-1)
bridge=b[page:page+ks];off=page+align(ks);payload=b[off:off+rs]
assert payload==pack.pack(k)
magic,version,size,va,entry,span,length,crc,flags,ramdisk=pack.HEADER.unpack_from(payload)
assert (magic,version,size,flags,ramdisk)==(b'A6XNU01\0',1,64,0,0)
assert span==length and len(payload)==64+span and zlib.crc32(payload[64:])==crc
assert b'rd=a6userdata launchdsuffix=release\0' in bridge
assert b'unentitled_ios_sim_launch=1 ' in bridge
assert '_unentitled_ios_sim_launch' in symbols
assert b'cpus=8 ' in bridge and b'A6PLTE Cortex-A53 SMP8 PSCI\0' in k
assert '_a6_start_other_cpus' in symbols and '_a6_secondary_entry' in symbols
assert b'Root: userdata HFS+; PID1: /sbin/launchd\n\0' in bridge
assert b'rd=md0' not in bridge and b'a6_usb=1' not in bridge
print('PASS: complete CRC, native kernel, no embedded rootfs, userdata HFS+ root, iOS launch compatibility, launchd PID1 and USB disabled')
