#!/usr/bin/env python3
"""Compile the new XNU platform TU against generated 12377 headers; no header stubs."""
from pathlib import Path
import subprocess,sys,shlex,os
r=Path(__file__).resolve().parents[1]; x=r/'xnu'; out=r/'build/xnu'
source=sys.argv[1] if len(sys.argv)>1 else 'osfmk/arm64/a6plte_interrupts.c'
generated=source.startswith('build/mig-generated/')
component='osfmk' if generated else source.split('/')[0]
source_path=(r if generated else x)/source
flags=['clang','--target=arm64-apple-darwin','-mcpu=cortex-a53','-ffreestanding','-fno-builtin','-fno-stack-protector','-mkernel','-fno-strict-aliasing','-fno-common','-fblocks','-D__API_AVAILABLE_PLATFORM_bridgeos(x)=bridgeos,introduced=x','-D__API_AVAILABLE_PLATFORM_xros(x)=visionos,introduced=x','-std=gnu17','-O2','-DCURRENT_MACHINE_CONFIG_LC=a6plte','-DXNU_TARGET_OS_OSX=1','-DXNU_TARGET_OS_IOS=0','-DARM64_BOARD_CONFIG_A6PLTE=1','-DA6PLTE=1','-DVM_KERNEL_LINK_ADDRESS=0xfffffff007004000','-Darm64','-DARM64','-D__ARM64__','-DLP64','-DPAGE_SIZE_FIXED','-DKERNEL=1','-DKERNEL_PRIVATE=1','-DXNU_KERNEL_PRIVATE=1','-D__APPLE_API_PRIVATE=1','-D__APPLE_API_UNSTABLE=1','-DPRIVATE=1','-isysroot',os.environ.get('SDK',str(Path.home()/'.local/share/theos/sdks/iPhoneOS16.5.sdk'))]
component_defines = {
    'osfmk': ['MACH_KERNEL_PRIVATE'],
    'pexpert': ['PEXPERT_KERNEL_PRIVATE'],
    'bsd': ['BSD_KERNEL_PRIVATE', 'DRIVER_PRIVATE', '_KERNEL_BUILD', 'KERNEL_BUILD', 'MACH_KERNEL', 'BSD_BUILD'],
    'iokit': ['IOKIT_KERNEL_PRIVATE', 'DRIVER_PRIVATE', 'DRIVERKIT_PRIVATE', 'IOMATCHDEBUG', 'IOALLOCDEBUG', 'PRIVATE_WIFI_ONLY', 'IOASSERT'],
    'libkern': ['LIBKERN_KERNEL_PRIVATE', 'OSALLOCDEBUG'],
    'libsa': ['LIBSA_KERNEL_PRIVATE'],
    'security': ['BSD_KERNEL_PRIVATE'],
    'san': [],
}
flags += ['-D'+name+'=1' for name in component_defines[component]]
if source.endswith(('.cpp', '.cc')):
    flags[0] = 'clang++'
    flags.remove('-std=gnu17')
    flags += ['-std=gnu++2b', '-fsized-deallocation', '-fapple-kext', '-fno-rtti', '-I'+str(x/'libkern/libcxx_support')]

for path in [out/component,out/'osfmk',out/'pexpert',out/'bsd',r/'build/kernel-headers',x/'osfmk',x/'bsd',x/'pexpert',x/'iokit',x/'libkern',x/'libsa',x/'EXTERNAL_HEADERS',x]: flags+=['-I'+str(path)]
for line in (out/'pexpert/config.DEVELOPMENT_ARM64').read_text().splitlines():
    p=shlex.split(line,comments=True)
    if p and p[0]=='options': flags+=['-D'+p[1]]
flags+=['-include',str(out/component/'meta_features.h')]
if component=='osfmk': flags+=['-DMACH_KERNEL=1']
if source.startswith('osfmk/vm/') and source.endswith('.c'): flags+=['-DVM_UNSAFE_TYPES=1']
if source.startswith('osfmk/corecrypto/'): flags+=['-I'+str(x/'EXTERNAL_HEADERS/corecrypto')]
if generated: flags+=['-I'+str(r/'build/kernel-headers/mach'),'-I'+str(r/'build/kernel-headers/device'),'-I'+str(r/'build/kernel-headers/UserNotification')]
assembly=source.endswith('/genassym.c')
if assembly: flags+=['-fno-integrated-as']
if source in ('pexpert/arm/a6plte/early.c','pexpert/arm/a6plte/fb.c'):
    flags+=['-mgeneral-regs-only'] # Called before CPACR_EL1 enables FP/SIMD.
if source.endswith('.s'):
    flags+=['-x','assembler-with-cpp','-DASSEMBLER']
output=Path(os.environ.get('A6_PROBE_OUTPUT',str(r/'artifacts'/('xnu-'+Path(source).stem))))
object_path=Path(str(output)+('.s' if assembly else '.macho.o'))
object_path.unlink(missing_ok=True) # A failed probe must not leave a stale successful object.
flags+=[('-S' if assembly else '-c'),str(source_path),'-o',str(object_path)]
p=subprocess.run(flags,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
log=Path(str(output)+'.log') if 'A6_PROBE_OUTPUT' in os.environ else r/'artifacts'/('compile-'+Path(source).stem+'.log')
log.write_text(p.stdout)
print(p.stdout);sys.exit(p.returncode)
