#!/usr/bin/env python3
"""Fetch pinned upstreams and apply this port's patches; never overwrite a checkout."""
from pathlib import Path
import subprocess
r=Path(__file__).resolve().parents[1]
sources=[('reference/platform-headers','theo-os/xnu','54ea37c23af20f9d0354c0d758eb51dc68dbcd81',None),('lk2nd','msm8916-mainline/lk2nd','dd6c1db1c085b419ac5dfffbd429aadb994ac094','lk2nd-a6plte-xnu.patch'),
 ('xnu','apple-oss-distributions/xnu','ac9718fb1af618d5ce8678d0dc6e8a58f252216f','xnu-a6plte-framebuffer.patch'),
 ('reference/bootstrap_cmds','apple-oss-distributions/bootstrap_cmds','c71d2d72f48995baaea76148f61002e5299841de',None),
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
        git('sparse-checkout','set','EXTERNAL_HEADERS/CoreEntitlements/V2','EXTERNAL_HEADERS/TrustCache')
    git('checkout','--detach','FETCH_HEAD')
    if patch: git('apply',str(r/'patches'/patch))
