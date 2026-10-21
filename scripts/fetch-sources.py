#!/usr/bin/env python3
"""Fetch pinned upstreams and apply this port's patches; never overwrite a checkout."""
from pathlib import Path
import subprocess
r=Path(__file__).resolve().parents[1]
sources=[('reference/hfs','apple-oss-distributions/hfs','31d5ec238dfab485e78a9a30b8b92d13e8914f03','hfs-a6plte.patch'),('reference/libpthread','apple-oss-distributions/libpthread','a6c70ca0e544347a0377babf748f831577ec24f9','libpthread-a6plte.patch'),('reference/libdispatch','apple-oss-distributions/libdispatch','cdb61e93e803d0093635f356753a9a30c09836db',None),('reference/platform-headers','theo-os/xnu','54ea37c23af20f9d0354c0d758eb51dc68dbcd81',None),('lk2nd','msm8916-mainline/lk2nd','dd6c1db1c085b419ac5dfffbd429aadb994ac094','lk2nd-a6plte-xnu.patch'),
 ('xnu','apple-oss-distributions/xnu','1b191cb58250d0705d8a51287127505aa4bc0789','xnu-a6plte-framebuffer.patch'),
 ('reference/bootstrap_cmds','apple-oss-distributions/bootstrap_cmds','fc3180f320239c85da79fc30a281a8830f1301f1',None),
 ('reference/PureDarwin','PureDarwin/PureDarwin','1bbaeb2ee6aa41e6f792a0b1e2943cc295b3b290',None)]
for directory,repo,commit,patch in sources:
    dest=r/directory
    if dest.exists():
        raise SystemExit(f'{dest} already exists; use a fresh checkout to fetch sources')
    dest.mkdir(parents=True)
    def git(*args): subprocess.run(['git','-C',str(dest),*args],check=True)
    git('init','-q');git('remote','add','origin','https://github.com/'+repo+'.git')
    git('fetch','--depth=1','origin',commit)
    if directory=='reference/platform-headers':
        git('sparse-checkout','init','--cone')
        git('sparse-checkout','set','EXTERNAL_HEADERS/CoreEntitlements/V2','EXTERNAL_HEADERS/TrustCache','EXTERNAL_HEADERS/CodeSignature')
    git('checkout','--detach','FETCH_HEAD')
    if patch: git('apply',str(r/'patches'/patch))
    if directory=='xnu':
        subprocess.run(['python3',str(r/'scripts/apply-sweet-0046.py'),str(dest)],check=True)
