#!/usr/bin/env python3
"""Generate DriverKit RPC glue with the IIG shipped with Xcode."""
from pathlib import Path
import os, re, shlex, subprocess
from iig_compat import legacy_rpc
root=Path(__file__).resolve().parents[1]
x=root/'xnu'
out=root/'build/xnu/iokit'
makefile=(out/'Makefile').read_text().replace('\\\n',' ')
match=re.search(r'^CXXFILES\s*=([^\n]*)',makefile,re.M)
iig=subprocess.check_output(['xcrun','--find','iig'],text=True).strip()
flags=['-I'+str(p) for p in (x/'iokit',x/'osfmk',x/'bsd',root/'build/xnu/bsd',root/'build/kernel-headers',x/'EXTERNAL_HEADERS',out)]
flags+=['-isysroot',os.environ['SDK'],'-x','c++','-std=gnu++17','-D__IIG=1','-DDRIVERKIT_PRIVATE=1','-DPRIVATE_WIFI_ONLY=1']
for relative in re.findall(r'(?<!\S)\./([^\s]+\.iig\.cpp)',match[1]):
    impl=out/relative
    impl.parent.mkdir(parents=True,exist_ok=True)
    definition=x/'iokit'/relative.removesuffix('.cpp')
    header=impl.with_name(impl.name.replace('.iig.cpp','.h'))
    subprocess.run([iig,'--def',str(definition),'--header',str(header),'--impl',str(impl),
                    '--framework-name','DriverKit','--',*flags],check=True)
    # Adapt the newer generator to the old kernel's unchanged IORPC wire ABI.
    impl.write_text(legacy_rpc(impl.read_text()))
    # IIG references generated interfaces through the declared framework name,
    # including interfaces whose definitions live under Tests/.
    exported=out/'DriverKit'/header.name
    if exported != header:
        exported.write_bytes(header.read_bytes())
