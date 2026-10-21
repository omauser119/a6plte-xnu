#!/usr/bin/env python3
"""Compile the new XNU platform TU against generated 8796 headers; no header stubs."""
from pathlib import Path
import subprocess,sys,shlex,os
r=Path(__file__).resolve().parents[1]; x=r/'xnu'; out=r/'build/xnu'
source=sys.argv[1] if len(sys.argv)>1 else 'osfmk/arm64/a6plte_interrupts.c'
generated=source.startswith('build/')
mig_generated=source.startswith('build/mig-generated/')
component='osfmk' if mig_generated else (source.split('/')[2] if generated else source.split('/')[0])
component=os.environ.get('A6_COMPONENT', component)
source_path=(r if generated or source.startswith(('reference/','tests/')) else x)/source
flags=['clang','--target=arm64-apple-darwin','-mcpu=cortex-a53','-ffreestanding','-fno-builtin','-fno-stack-protector','-mkernel','-fno-strict-aliasing','-fno-common','-fblocks','-D__API_AVAILABLE_PLATFORM_bridgeos(x)=bridgeos,introduced=x','-D__API_AVAILABLE_PLATFORM_xros(x)=visionos,introduced=x','-std=gnu17','-O2','-DCURRENT_MACHINE_CONFIG_LC=a6plte','-DXNU_TARGET_OS_OSX=1','-DXNU_TARGET_OS_IOS=0','-DARM64_BOARD_CONFIG_A6PLTE=1','-DA6PLTE=1','-DVM_KERNEL_LINK_ADDRESS=0xfffffff007004000','-Darm64','-DARM64','-D__ARM64__','-DLP64','-DPAGE_SIZE_FIXED','-DKERNEL=1','-DKERNEL_PRIVATE=1','-DXNU_KERNEL_PRIVATE=1','-D__APPLE_API_PRIVATE=1','-D__APPLE_API_UNSTABLE=1','-DPRIVATE=1','-DOS_FIREHOSE_SPI=1','-isysroot',os.environ.get('SDK',str(Path.home()/'.local/share/theos/sdks/iPhoneOS16.5.sdk'))]
component_defines = {
    'osfmk': ['MACH_KERNEL_PRIVATE'],
    'pexpert': ['PEXPERT_KERNEL_PRIVATE'],
    'bsd': ['BSD_KERNEL_PRIVATE', 'DRIVER_PRIVATE', '_KERNEL_BUILD', 'KERNEL_BUILD', 'MACH_KERNEL', 'BSD_BUILD'],
    'iokit': ['IOKIT_KERNEL_PRIVATE', 'DRIVER_PRIVATE', 'DRIVERKIT_PRIVATE', 'IOMATCHDEBUG', 'IOALLOCDEBUG', 'PRIVATE_WIFI_ONLY', 'IOASSERT'],
    'libkern': ['LIBKERN_KERNEL_PRIVATE', 'OSALLOCDEBUG'],
    'libsa': ['LIBSA_KERNEL_PRIVATE'],
    'security': ['BSD_KERNEL_PRIVATE'],
    'san': [],
    'pthread': ['BSD_KERNEL_PRIVATE', 'DRIVER_PRIVATE', '_KERNEL_BUILD', 'KERNEL_BUILD', 'MACH_KERNEL', 'BSD_BUILD', 'ABSOLUTETIME_SCALAR_TYPE', 'NEEDS_SCHED_CALL_T', '__PTHREAD_EXPOSE_INTERNALS__'],
    'hfs': ['BSD_KERNEL_PRIVATE', 'DRIVER_PRIVATE', '_KERNEL_BUILD', 'KERNEL_BUILD', 'MACH_KERNEL', 'BSD_BUILD', 'ABSOLUTETIME_SCALAR_TYPE', 'NEEDS_SCHED_CALL_T'],
}
if component=='hfs' and source.endswith('.cpp'):
    component_defines['hfs'] = component_defines['iokit']
config_component = 'iokit' if component=='hfs' and source.endswith('.cpp') else ('bsd' if component in ('pthread','hfs') else component)
flags += ['-D'+name+'=1' for name in component_defines[component]]
if component=='hfs':
    flags += ['-I'+str(r/'reference/hfs/core'), '-I'+str(r/'reference/hfs/hfs_encodings')]
    flags += ['-include',str(r/'reference/hfs/core/kext-config.h'),'-ferror-limit=0']
    if not source.endswith('.cpp'):
        flags += ['-include','sys/param.h','-include','sys/proc_internal.h','-include','sys/vnode_internal.h']
if component=='pthread':
    # Separate kext globals need private names when linked into the kernel image.
    flags += ['-Dpthread_kern=a6_pthread_kern', '-Dcurrent_uthread=a6_pthread_current_uthread']
    flags += ['-I'+str(r/'reference/libpthread'/part) for part in ('private','include','')]
    flags += ['-ferror-limit=0']
    flags += ['-include','sys/param.h','-include','sys/proc_internal.h']
if source.endswith(('.cpp', '.cc')):
    flags[0] = 'clang++'
    flags.remove('-std=gnu17')
    flags += ['-std=gnu++17', '-nostdinc++', '-fsized-deallocation', '-fapple-kext', '-fno-rtti', '-ferror-limit=0', '-I'+str(r/'build/cxx-support')]

if component != 'osfmk': flags += ['-I'+str(r/'build/export-headers')]
for path in [out/config_component,out/'osfmk',out/'pexpert',out/'bsd',out/'iokit',r/'build/kernel-headers',x/'osfmk',x/'bsd',x/'pexpert',x/'iokit',x/'libkern',x/'libsa',x/'EXTERNAL_HEADERS',x,r/'reference/libdispatch']: flags+=['-I'+str(path)]
for line in (out/'pexpert/config.DEVELOPMENT_ARM64').read_text().splitlines():
    p=shlex.split(line,comments=True)
    if p and p[0]=='options': flags+=['-D'+p[1]]
flags+=['-include',str(out/config_component/'meta_features.h')]
if component=='hfs':
    # Public macOS HFS profile: unencrypted HFS+, without Apple's private key-roll sources.
    flags += ['-UCONFIG_PROTECT','-DCONFIG_PROTECT=0']
    if source.startswith('reference/hfs/hfs_encodings/'):
        flags += ['-Dhfs_allocated=a6_hfs_encoding_allocated']
if component=='osfmk': flags+=['-DMACH_KERNEL=1']
if (source.startswith(('osfmk/vm/', 'bsd/vm/')) and source.endswith('.c')) or source == 'bsd/kern/kern_mman.c': flags+=['-DVM_UNSAFE_TYPES=1']
if source.startswith('reference/libdispatch/'):
    flags += ['-I'+str(x/'libkern/firehose'), '-DDISPATCH_USE_DTRACE=0', '-DOS_ATOMIC_CONFIG_MEMORY_ORDER_DEPENDENCY=1', '-DOS_ATOMIC_CONFIG_STARVATION_FREE_ONLY=0']
if source.startswith('osfmk/corecrypto/'): flags+=['-I'+str(x/'EXTERNAL_HEADERS/corecrypto')]
if mig_generated: flags += ['-I'+str(r/'build/kernel-headers'/directory) for directory in ('gssd', 'lockd', 'kextd')]
if mig_generated: flags+=['-I'+str(r/'build/kernel-headers/mach'),'-I'+str(r/'build/kernel-headers/device'),'-I'+str(r/'build/kernel-headers/UserNotification')]
if source.endswith(('.cpp', '.cc')):
    sdk=Path(os.environ.get('SDK',str(Path.home()/'.local/share/theos/sdks/iPhoneOS16.5.sdk')))
    flags += ['-idirafter',str(sdk/'usr/include/c++/v1')]
if source in ('pexpert/arm/a6plte/early.c', 'pexpert/arm/a6plte/fb.c'):
    flags += ['-fno-jump-tables'] # No absolute string/dispatch tables before MMU.
assembly=source.endswith('/genassym.c')
if assembly: flags+=['-fno-integrated-as']
if source.startswith(('iokit/Kernel/arm/A6HID', 'iokit/Kernel/arm/A6Input')) or source in ('pexpert/arm/a6plte/early.c','pexpert/arm/a6plte/fb.c','osfmk/prng/a6plte_prng.c','libkern/crypto/a6plte_kmem_rng.c','libkern/crypto/a6plte_sha1_digest.c','libkern/crypto/a6plte_sha512.c','libkern/crypto/a6plte_sha512_digest.c','iokit/Kernel/arm/A6PlatformServices.cpp','iokit/Kernel/arm/A6GraphicsLayout.c') or source.startswith(('libkern/crypto/a6plte_aes/','bsd/dev/a6plte/')):
    flags+=['-mgeneral-regs-only','-mstrict-align'] # Early console and bootstrap crypto: scalar, alignment-safe accesses.
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
