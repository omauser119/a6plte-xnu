#!/usr/bin/env python3
"""Generate DriverKit RPC glue with the IIG shipped with Xcode."""
from pathlib import Path
import os, re, shlex, subprocess
root=Path(__file__).resolve().parents[1]
x=root/'xnu'
out=root/'build/xnu/iokit'
makefile=(out/'Makefile').read_text().replace('\\\n',' ')
match=re.search(r'^CXXFILES\s*=([^\n]*)',makefile,re.M)
iig=subprocess.check_output(['xcrun','--find','iig'],text=True).strip()
flags=['-I'+str(p) for p in (x/'iokit',x/'osfmk',x/'bsd',root/'build/xnu/bsd',root/'build/kernel-headers',x/'EXTERNAL_HEADERS',out)]
flags+=['-isysroot',os.environ['SDK'],'-x','c++','-std=gnu++2b','-D__IIG=1','-DDRIVERKIT_PRIVATE=1','-DPRIVATE_WIFI_ONLY=1']
for relative in re.findall(r'(?<!\S)\./([^\s]+\.iig\.cpp)',match[1]):
    impl=out/relative
    impl.parent.mkdir(parents=True,exist_ok=True)
    definition=x/'iokit'/relative.removesuffix('.cpp')
    header=impl.with_name(impl.name.replace('.iig.cpp','.h'))
    subprocess.run([iig,'--def',str(definition),'--header',str(header),'--impl',str(impl),
                    '--framework-name','DriverKit','--',*flags],check=True)
