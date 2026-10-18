# XNU 12377 bring-up for Samsung Galaxy A6+ (SM-A605FN)

**Experimental XNU 12377 port. ARM64 kernel and lk2nd boot image build successfully. UART is not used.**

The first complete milestone is a Darwin ramdisk built from Apple Open Source,
with an interactive Bash session over SSH through USB Ethernet. The
[project roadmap](ROADMAP.md) records the hardware evidence, dependencies and
acceptance checks for each step.

The modified lk2nd menu and the first framebuffer output from the actual linked
XNU kernel have been confirmed on SM-A605FN. After temporary loading with
`fastboot boot`, XNU prints `start_first_cpu: MMU OFF` and
`Framebuffer online. No UART.` The updated kernel has also reached
`arm_vm_init: final TTBR1 active`, confirming the MMU transition,
virtual execution in `arm_init` and activation of the final VM mappings.
Native XNU logs now confirm completion of VM bootstrap, initialization of
scheduler structures, Firehose, OSLog, IPC and IOKit on the physical display.
The RGB888 console update passed the previous graphics-console fault and reached
`ulock_initialize` in the kernel bootstrap thread. That run stopped in
`read_random` because no corecrypto kext had registered its PRNG callbacks.
The current source keeps XNU's boot-seeded HMAC-DRBG available to bootstrap
callers until corecrypto registration, with shared-state locking and reseeding.
Timer interrupts, sustained scheduling and userspace are not yet confirmed.

## Implemented

- RGB888/RGB565/XRGB8888 framebuffer console, scrolling and bounded geometry.
- ARM64 boot bridge: FDT parsing, reserved RAM handling, experimental Mach-O loader,
  XNU boot arguments and minimal Apple device tree, including boot entropy.
- XNU framebuffer identity mapping across MMU setup and final page-table
  construction, early `printf`/`kprintf` and panic output, bootstrap exception reports,
  and log replay when the framebuffer receives its final virtual mapping.
- Initial Cortex-A53/A6PLTE profile, 4K pages, one CPU, GICv2 and virtual timer wiring.
- No-LSE commpage locks and exclusion of Apple-specific initialization.
- Bootstrap random reads and writes through XNU's native HMAC-DRBG, without
  claiming a full corecrypto provider is registered.
- Pinned upstream patches, native config/MIG tools and component compilation probes.

SM-A605FN HW.Rev.4 display: 1080×2220 packed RGB888, stride 3240,
framebuffer physical address 0x90001000. GIC integration is not hardware-validated.

[Download the bootstrap random update](https://github.com/omauser119/a6plte-xnu/releases/tag/a6plte-xnu-12377-bringup4).

## GitHub Actions

`A6PLTE bring-up` runs on pushes, pull requests and manual dispatch:

- **Linux:** host tests, framebuffer boot image and UART-disabled lk2nd image.
- **macOS:** Apple Clang, MIG/IIG generation, all configured kernel components and ARM64 executable linking.
- **Packaging:** after a successful link, build `xnu-boot.img` for temporary loading through lk2nd.

Artifacts include the linked XNU kernel, packaged boot image, lk2nd image and
build diagnostics. All three jobs passed for the bootstrap random update
([run 39157836872](https://github.com/omauser119/a6plte-xnu/actions/runs/39157836872), source `0654e57`).
A successful build does not establish runtime progress on hardware. No workflow
flashes a device.

## Reproduce

Use a fresh checkout (fetch refuses to overwrite existing upstream directories):

```sh
python3 scripts/fetch-sources.py
./scripts/test.sh
./scripts/build-smoke.sh
./scripts/build-lk2nd.sh
```

Linux dependencies: clang, llvm, lld, dtc, GNU make, ARM bare-metal GCC,
newlib, ripgrep and Python 3. Build scripts accept `LLD` and `TOOLCHAIN_PREFIX`.

XNU component checks additionally need bison, flex, tcsh and Apple SDK headers.
On macOS use the Apple compiler and SDK:

```sh
export SDK="$(xcrun --sdk macosx --show-sdk-path)"
./scripts/check-platform.sh
python3 scripts/check-component.py osfmk
python3 scripts/check-component.py mig
```

On Linux `SDK` can point to a Theos iPhoneOS 16.5 SDK. Upstream Linux Clang lacks
XNU typed-allocation builtins. `check-platform.sh` generates private/exported MIG interfaces and
checks 18 platform objects. Per-file diagnostics and JSON results are stored in
`artifacts/`. These scripts do not link a kernel.

`generate-version.sh` uses XNU's original generator with a local development stamp
`1.0.0d1` unless `RC_DARWIN_KERNEL_VERSION` is set. This is not an Apple Darwin release.

## Device testing

From lk2nd/fastboot, the framebuffer payload can be loaded temporarily:

```sh
fastboot boot artifacts/fb-smoke-boot.img
```

No USB driver runs in this payload; return to lk2nd by hardware reboot.
The modified bootloader was written from the running lk2nd interface with:

```sh
fastboot flash lk2nd artifacts/lk2nd-a6plte-xnu.img
```

On this SM-A605FN, `fastboot reboot bootloader` entered Samsung Odin mode.
Use a hardware restart and press Volume Down after the screen/vibration to return
to lk2nd fastboot. The `lk2nd` target updates the bootloader's 512 KiB region;
`boot` is the separate boot-image area exposed by lk2nd.

`package-boot.sh /path/to/kernel` requires an actual linked ARM64_ALL Mach-O
MH_EXECUTE with LC_UNIXTHREAD. It rejects ARM64e, IMG4 and filesets. The bridge
uses a 128 MiB reserved-memory-aware allocation and no address slide. Before
loading a full kernel, RAM and lk2nd download-buffer overlap must be checked.
`serial=1` selects the substituted framebuffer ABI, not hardware UART.

## Remaining work

Full corecrypto integration, runtime compatibility of external dependencies,
a complete platform device tree, and exception/timer validation remain in progress. SMP,
storage, rootfs and power management are not implemented. Compiled-file counts
are not a measure of boot readiness.

## Sources and licensing

Upstream sources are fetched at fixed commits; this repository stores patches:

- [lk2nd](https://github.com/msm8916-mainline/lk2nd), `dd6c1db1c085b419ac5dfffbd429aadb994ac094`.
- [XNU rel/xnu-12377](https://github.com/apple-oss-distributions/xnu/tree/rel/xnu-12377),
  `ac9718fb1af618d5ce8678d0dc6e8a58f252216f` (12377.121.6).
- [bootstrap_cmds](https://github.com/apple-oss-distributions/bootstrap_cmds),
  `c71d2d72f48995baaea76148f61002e5299841de`, native MIG.
- [PureDarwin](https://github.com/PureDarwin/PureDarwin),
  `1bbaeb2ee6aa41e6f792a0b1e2943cc295b3b290`, unifdef source.
- `reference/a6plte-r4.dts` is decompiled from a pre-existing a6plte DTB. Related
  Linux source: [msm8953-mainline/linux](https://github.com/msm8953-mainline/linux).
  Exact DTB-to-source commit correspondence is not established.

Upstream licenses remain applicable to upstream code and patches. Copied font
retains its BSD license. Original bridge/console files carry SPDX identifiers.
No Apple SDK, device logs, credentials or prebuilt vendor toolchains are included.

The boot image v0 writer is local and tested; it does not depend on Ubuntu mkbootimg/GKI packaging. CI auto-cancellation is disabled.

## Supplemental declarations for the current OSFMK build

`fetch-sources.py` also pins [theo-os/xnu](https://github.com/theo-os/xnu) at
`54ea37c23af20f9d0354c0d758eb51dc68dbcd81` and stages only its CoreEntitlements/V2
TrustCache and CodeSignature headers in `build/kernel-headers`. These are community-maintained
supplemental declarations, not a matching Apple KDK. Their source commit describes
an import from OpenDarwin platform-support work. No replacement trust decision or
success-returning implementation is supplied. This addresses compilation for the
current non-PPL/non-SPTM profile; it does not establish runtime compatibility with
Apple private libraries, nor supply those libraries for final linking.


## Complete kernel build pipeline

On macOS with Xcode, run `scripts/build-xnu.sh` after fetching the pinned sources.
The pipeline generates BSD syscalls, private and exported MIG headers, DriverKit
interfaces with IIG, and version/assembly offsets. It compiles all configured
components, including C++, then links `artifacts/kernel.a6plte` using XNU's ARM64
segment layout. Compilation failures stop the link; unresolved symbols are not
ignored. The executable is still under development. A successful build does not establish
that the kernel reaches a working scheduler or userspace on the phone.

The kernel Firehose implementation is built from Apple's
[libdispatch](https://github.com/apple-oss-distributions/libdispatch) commit
`2361ffb78a76f7ee488cd052eb0bc5c767118bf9`, under its upstream license.
CI artifacts are named `a6plte-boot-images` and `xnu-build-output`; the latter
contains diagnostics and intermediate objects when the full build fails.


First complete build: [Actions 39140135502](https://github.com/omauser119/a6plte-xnu/actions/runs/39140135502),
commit `3a1d1ff`. The executable is ARM64 `MH_EXECUTE`, with `NOUNDEFS` and no
undefined symbols according to `llvm-nm`. The packaged image was independently
unpacked and compared with the freshly packed executable before temporary boot.


The display follow-up enables A6PLTE hardware auto-refresh during lk2nd display
initialization, keeps debug output in the USB-readable log buffer instead of
overwriting the menu, and cleans framebuffer cache lines before triggering DMA.
The corrected image was built locally with ARM bare-metal GCC, with UART/DCC/JTAG
still disabled, and `fastboot flash lk2nd` completed successfully. The user confirmed the physical fastboot menu is visible after this update.


The boot bridge now prints package-header/CRC/copy/entry milestones and installs
EL1 exception vectors before reading the kernel package. An early synchronous
fault prints ESR/ELR/FAR on the framebuffer. CRC integrity remains mandatory and
uses an incremental nibble-table implementation checked against zlib. The kernel
package CRC, kernel copy and the first XNU framebuffer marker have been
confirmed on the phone.


A photographed EL1 exception identified an unaligned `LDURH` in the bridge's
Apple-device-tree property-name copy: ESR `0x96000021`, bridge-relative ELR
`0x3c20`, FAR `0x4008425d`. MMU-off code now uses `-mstrict-align`, including
XNU's early framebuffer units. The loader also preserves the Mach-O virtual
base's low 21 bits in its physical placement, as required by XNU's initial L2
block mappings; this kernel needs a `0x4000` offset within the allocated block.
