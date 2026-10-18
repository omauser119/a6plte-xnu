#!/usr/bin/env python3
"""Generate the syscall ABI and dispatch sources using XNU's own generator."""
from pathlib import Path
import subprocess
root = Path(__file__).resolve().parents[1]
out = root/'build/xnu/bsd'
headers = root/'build/kernel-headers/sys'
headers.mkdir(parents=True, exist_ok=True)
for mode in ('proto', 'header', 'table', 'names', 'audit', 'systrace'):
    subprocess.run(['sh', str(root/'xnu/bsd/kern/makesyscalls.sh'),
                    str(root/'xnu/bsd/kern/syscalls.master'), mode], cwd=out, check=True)
for name in ('sysproto.h', 'syscall.h'):
    (headers/name).write_bytes((out/name).read_bytes())
