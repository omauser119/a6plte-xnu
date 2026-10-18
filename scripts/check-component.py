#!/usr/bin/env python3
"""Compile configured C/assembly units and retain per-source results (not a link)."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json, os, re, subprocess, sys
root = Path(__file__).resolve().parents[1]
component = sys.argv[1] if len(sys.argv) > 1 else 'osfmk'
if component not in ('osfmk', 'pexpert', 'mig', 'bsd', 'libkern', 'iokit', 'libsa', 'security', 'san', 'pthread'):
    raise SystemExit('Unsupported XNU component')
sources = []
if component == 'pthread':
    sources = ['reference/libpthread/kern/'+name+'.c' for name in ('kern_init','kern_support','kern_synch')]
elif component == 'mig':
    makefile=(root/'build/xnu/osfmk/Makefile').read_text().replace('\\\n', ' ')
    match=re.search(r'^CFILES\s*=([^\n]*)',makefile,re.M)
    for path in re.findall(r'(?<!\S)\./([^\s]+)', match[1]):
        name=Path(path).name
        if name in ('gssd_mach.c','lockd_mach.c','kextd_mach.c','UNDRequest.c'):
            name=name.removesuffix('.c')+'_user.c'
        sources.append('build/mig-generated/'+name)

else:
    makefile = (root/'build/xnu'/component/'Makefile').read_text().replace('\\\n', ' ')
    for group in ('CFILES', 'CXXFILES', 'SFILES'):
        match = re.search(r'^' + group + r'\s*=([^\n]*)', makefile, re.M)
        if match:
            sources.extend(re.findall(r'\$\(SOURCE_DIR\)/([^\s]+)', match[1]))
            if component != 'osfmk': # OSFMK generated interfaces are built in the MIG component.
                sources.extend('build/xnu/'+component+'/'+name for name in re.findall(r'(?<!\S)\./([^\s]+)', match[1]))
if component == 'libsa': sources.extend('libsa/'+name+'.c' for name in ('nonlto','lastkerneldataconst','lastkernelconstructor'))
if component == 'libkern': sources.append('reference/libdispatch/src/firehose/firehose_buffer.c')
if component == 'osfmk': sources.append('build/xnu/osfmk/version.c')
sources = sorted(set(sources))
out = root/'artifacts/components'/component
out.mkdir(parents=True, exist_ok=True)
def compile_one(source):
    key = source.replace('/', '__')
    env = dict(os.environ, A6_PROBE_OUTPUT=str(out/key), A6_COMPONENT='osfmk' if component == 'mig' else component)
    result = subprocess.run([sys.executable, str(root/'scripts/probe-platform.py'), source],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    errors = [s for s in result.stdout.splitlines() if 'error:' in s]
    return dict(source=source, success=result.returncode == 0, errors=errors)
with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(compile_one, sources))
(out/'results.json').write_text(json.dumps(results, indent=2)+'\n')
passed = sum(r['success'] for r in results)
print(f'{component}: {passed}/{len(results)} compiled; results: {out}/results.json')
for result in results:
    if not result['success']:
        print(result['source'] + ': ' + (result['errors'][0] if result['errors'] else 'failed; see log'))
sys.exit(0 if passed == len(results) else 1)
