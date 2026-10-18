#!/usr/bin/env python3
"""Generate XNU Mach interfaces using the kernel modes in osfmk/mach/Makefile."""
from pathlib import Path
import subprocess, re, json, os, shlex
r=Path(__file__).resolve().parents[1]
x=r/'xnu'
out=r/'build/kernel-headers/mach'
out.mkdir(parents=True,exist_ok=True)
source_out=r/'build/mig-generated'; source_out.mkdir(exist_ok=True)
m=(x/'osfmk/mach/Makefile').read_text().replace('\\\n',' ')
def items(name):
    return re.search(r'^'+name+r'\s*=([^\n]*)',m,re.M)[1].split()
jobs={}
for name in ('MIG_UUHDRS','MIG_USHDRS','MIG_KUHDRS','MIG_KSHDRS','MIG_KUSRC','MIG_KSSRC'):
    server=name in ('MIG_USHDRS','MIG_KSHDRS','MIG_KSSRC')
    kernel=name.startswith('MIG_K')
    for file in items(name):
        stem=re.sub(r'(_server|_user)?\.[ch]$','',file)
        jobs[stem,server]=(kernel or jobs.get((stem,server),False))
jobs={("mach",stem,server):kernel for (stem,server),kernel in jobs.items()}
jobs["device","device",True]=True
jobs["UserNotification","UNDRequest",False]=True
jobs["UserNotification","UNDReply",True]=True
for directory in ('gssd', 'lockd', 'kextd'):
    jobs[directory, directory+'_mach', False]=True
config_flags=[]
for line in (r/'build/xnu/osfmk/config.DEVELOPMENT_ARM64').read_text().splitlines():
    fields=shlex.split(line,comments=True)
    if fields and fields[0]=='options': config_flags.append('-D'+fields[1])
results=[]
variants=[(key, kernel, False) for key,kernel in sorted(jobs.items())]
variants += [(key, False, True) for key,kernel in sorted(jobs.items()) if key[0]=='mach']
for (directory,stem,server),kernel,exported in variants:
    out=r/('build/export-headers' if exported else 'build/kernel-headers')/directory
    out.mkdir(parents=True,exist_ok=True)
    defs=x/'osfmk'/directory/f'{stem}.defs'
    server_stem=stem+('Server' if directory=='UserNotification' else '_server')
    flags=['clang','--target=arm64-apple-darwin','-E','-x','c','-D__MIG__','-DPRIVATE=1','-DKERNEL=1','-DKERNEL_PRIVATE=1','-DXNU_KERNEL_PRIVATE=1',
           '-I'+str(x/'osfmk'),'-I'+str(x/'bsd'),'-I'+str(x/'EXTERNAL_HEADERS')]
    flags+=config_flags+['-I'+str(r/'build/xnu/osfmk'),'-include',str(r/'build/xnu/osfmk/meta_features.h')]
    if kernel:
        flags+=['-DMACH_KERNEL_PRIVATE=1', '-DKERNEL_SERVER=1' if server else '-DKERNEL_USER=1']
        if not server: flags+=['-DEXC_SERVER_AUDITTOKEN=1','-DMACH_EXC_SERVER_AUDITTOKEN=1']
    pre=subprocess.run(flags+[str(defs)],capture_output=True,text=True)
    label=('export_' if exported else '')+stem+('_server' if server else '_user')
    log=pre.stderr
    status=pre.returncode
    if not status:
        cmd=[str(r/'build/host-mig/migcom'),'-novouchers']
        if kernel: cmd+=['-mach_msg2'] if server else ['-maxonstack','1024']
        cmd+=['-header','/dev/null' if server else str(out/f'{stem}.h'),
              '-sheader',str(out/f'{server_stem}.h') if server else '/dev/null',
              '-user','/dev/null' if server or exported else str(source_out/f'{stem}_user.c'),
              '-server',str(source_out/f'{server_stem}.c') if server and not exported else '/dev/null']
        proc=subprocess.run(cmd,input=pre.stdout,capture_output=True,text=True)
        status=proc.returncode;log+=proc.stdout+proc.stderr
    (source_out/f'{label}.log').write_text(log)
    results.append(dict(interface=label,success=status==0,log=log if status else ''))
(source_out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(f"MIG: {sum(a['success'] for a in results)}/{len(results)} interfaces generated")
for a in results:
    if not a['success']: print(a['interface']+': '+a['log'][:400])
raise SystemExit(any(not a['success'] for a in results))
