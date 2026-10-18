#!/usr/bin/env python3
"""Link the configured objects using XNU's ARM64 segment layout, no undefined-symbol bypass."""
from pathlib import Path
import json, os, re, shlex, subprocess
root=Path(__file__).resolve().parents[1]
components=('osfmk','mig','pexpert','bsd','libkern','iokit','libsa','security','san')
objects=[]
for component in components:
    out=root/'artifacts/components'/component
    results=json.loads((out/'results.json').read_text())
    if any(not item['success'] for item in results):
        raise SystemExit('Cannot link: compilation failed in '+component)
    for item in results:
        obj=out/(item['source'].replace('/','__')+'.macho.o')
        if not obj.is_file(): raise SystemExit('Missing object: '+str(obj))
        objects.append(str(obj))
text=(root/'xnu/makedefs/MakeInc.def').read_text().replace('\\\n',' ')
variables={'ARM64_PLKSEG_ADDR':'0xfffffff004004000','ARM64_LINK_ADDR':'0xfffffff007004000'}
def resolve(name):
    if name in variables: return variables[name]
    match=re.search(r'^'+re.escape(name)+r'\s*=([^\n]*)',text,re.M)
    if not match: raise SystemExit('Missing linker setting '+name)
    return re.sub(r'\$\(([^)]+)\)',lambda m:resolve(m[1]),match[1].strip())
flags=[]
for name in ('LDFLAGS_KERNEL_GEN','LDFLAGS_KERNEL_GENARM64','LDFLAGS_KERNEL_SEGARM64'):
    flags += shlex.split(resolve(name))
# XNU appends the final data/constructor sentinels after component objects.
objects.sort(key=lambda path: ('lastkerneldataconst' in path or 'lastkernelconstructor' in path))
config=root/'xnu/config'
exports=[]
for component in ('BSDKernel','IOKit','Libkern','Mach','MACFramework','Unsupported','Private'):
    exports += [config/(component+'.exports'), config/(component+'.arm64.exports')]
    exports += sorted(config.glob(component+'.arm64.MacOSX.exports'))
exports += [config/name for name in ('Unused.exports','Kasan_disabled.exports','Kcov_disabled.exports')]
aliases=root/'artifacts/all-alias.exp'
subprocess.run(['sh',str(config/'generate_linker_aliases.sh'),str(aliases),*map(str,exports)],check=True)
flags += ['-Wl,-alias_list,'+str(aliases)]
filelist=root/'artifacts/xnu-objects.txt' 
filelist.write_text('\n'.join(objects)+'\n')
output=root/'artifacts/kernel.a6plte'
output.unlink(missing_ok=True)
cmd=['clang++','--target=arm64-apple-darwin','-mcpu=cortex-a53','-isysroot',os.environ['SDK'],*flags,
     '-Wl,-filelist,'+str(filelist),'-lcc_kext','-o',str(output)]
(root/'artifacts/link-command.txt').write_text(shlex.join(cmd)+'\n')
subprocess.run(cmd,check=True)
