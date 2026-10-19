# XNU 12377 bring-up for Samsung Galaxy A6+ (SM-A605FN)

**Experimental XNU 12377 port. ARM64 kernel and lk2nd boot image build successfully. UART is not used.**

The first complete milestone is a Darwin ramdisk built from Apple Open Source,
with an interactive Bash session over SSH through USB Ethernet. The
[project roadmap](ROADMAP.md) records the hardware evidence, dependencies and
acceptance checks for each step.

On SM-A605FN, the actual XNU kernel prints its own startup logs and panics on
framebuffer. Hardware confirms VM bootstrap, platform registration, the Apple
pthread kernel component, DLIL thread scheduling and the displayed Skywalk
self-tests. Hardware now also confirms the native `md0` memory disk and
`hfs: mounted A6PLTE_ROOT`: Apple's HFS+ driver mounted the supplied root image.
The user also confirmed that `/sbin/a6-init` started as PID1 in ARM64 userspace.

The image contains a 32 MiB HFS+ root image, the native
`RAMDisk` → `md0` path, and a static ARM64 `/sbin/a6-init` process. The first
userspace check prints its PID and Darwin release and attempts a root-file read
and timed sleep/wakeup through real system calls. PID1 startup is confirmed;
its individual file-read and sustained sleep/wakeup checks still need evidence.
Absent AMFI entitlement queries deny requests; raw XML/DER entitlements are
treated as absent when no provider exists. Native code-signature validation
continues. All three jobs passed for that kernel/rootfs build. Bash, a dynamic runtime and USB networking are not
implemented yet.

The current source adds an SDHCI PIO eMMC backend and native BSD block/raw
devices restricted to the GPT `userdata` partition. Read/write, cache flush,
GPT validation, bounds and error handling are implemented and host-tested;
PID1 successfully read a sector from the real phone's userdata device with
`PID1: eMMC userdata sector read OK`. Hardware write/readback remains to be
tested on a prepared volume. See [storage implementation and layout](docs/STORAGE.md).

Native `startup_debug=1` traces startup stages; `startup_debug=3` also logs each
callback for diagnosis. Framebuffer scrolling and clearing use aligned scalar
64-bit transfers with byte fallback. Sanitizer tests compare 648 configurations
against a byte-exact reference; the speed improvement has not been measured on
the phone. Initial scheduling is observed, while sustained scheduling and timer
IRQ delivery still need validation. Bootstrap crypto does not register a full
corecrypto provider.

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
- Private kmem random contexts within XNU's 256-byte limit, with no locks during
  generation; host tests include the RFC 8439 block vector and range rejection.
- Explicit unavailable trust-cache state for the standalone A6PLTE image when
  Apple Image4/AMFI providers are absent; no NULL provider callbacks are invoked.
- Built-in A6PLTE IOKit platform expert and matching personality, with native
  device-tree nub publication for the bridge's CPU and SoC nodes.
- Built-in Apple libpthread kernel sources for native thread and synchronization
  callbacks, with a shared wait-queue layout and early provider registration.
- Bootstrap AES CBC/ECB from Apple XNU's legacy C implementation, tested against
  NIST vectors for 128/192/256-bit keys, including unaligned and in-place buffers;
  SHA-256/SHA-512 legacy APIs use native primitives without a provider.
- Built-in Apple HFS+ sources, native VFS registration and MacRoman conversion;
  bootstrap MD5 derived from the RSA Data Security, Inc. MD5 Message-Digest Algorithm
  supplies the existing HFS volume-UUID path before a crypto provider is present.
- Versioned kernel/rootfs package with full payload CRC, reserved RAMDisk pages,
  native `rd=md0` boot selection, and a first static ARM64 PID1 probe.
- Native BSD RAMDisk root handling without IOStorageFamily meta classes;
  absent AMFI entitlement callbacks deny requests instead of dereferencing NULL.
- GPT-validated `/dev/a6userdata` and `/dev/ra6userdata`, bounded SDHCI PIO
  reads/writes and eMMC cache flush, with timeout/error fault isolation.
- Pinned upstream patches, native config/MIG tools and component compilation probes.

SM-A605FN HW.Rev.4 display: 1080×2220 packed RGB888, stride 3240,
framebuffer physical address 0x90001000. GIC integration is not hardware-validated.

[Download the kernel/rootfs and lk2nd](https://github.com/omauser119/a6plte-xnu/releases/tag/a6plte-xnu-12377-bringup13).
The larger image requires the `hfs-map-v2` lk2nd update and a hardware restart into it.
Bringup12's initial runtime-mapping fix was incomplete; its loader must be updated.

## GitHub Actions

The current platform-service extension adds a log-only `IOWatchDogTimer`, an
explicit `AppleKeyStore` stub, CPU shared-memory `IOSurfaceRoot`, and an inherited
scanout `IOMobileFramebuffer`. Graphics use a documented A6 ABI; private iOS
framework compatibility is not yet implemented. See [platform services](docs/PLATFORM-SERVICES.md).

`A6PLTE bring-up` runs on pushes, pull requests and manual dispatch:

- **Linux:** host tests, framebuffer boot image and UART-disabled lk2nd image.
- **macOS:** Apple Clang, MIG/IIG generation, all configured kernel components, ARM64 executable linking, and HFS+ root image creation.
- **Packaging:** after a successful link, build `xnu-boot.img` for temporary loading through lk2nd.

Artifacts include the linked XNU kernel, packaged boot image, lk2nd image, raw
HFS+ root image, native PID1 and build diagnostics. All three jobs passed with
the SDHCI PIO userdata driver and first read-only userspace probe
([run 39232688113](https://github.com/omauser119/a6plte-xnu/actions/runs/39232688113), source `f7c546c`).
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

`generate-version.sh` uses XNU's original generator with Darwin `25.5.0`, matching
the pinned XNU `12377.121.6`, and identifies this port as
`xnu-12377.121.6/DEVELOPMENT_ARM64_A6PLTE`. `RC_DARWIN_KERNEL_VERSION` and
`KERNEL_BUILD_OBJROOT` can override those defaults. Older images used the incorrect
placeholder `1.0.0d1`; this port is a custom development build.

## Device testing

After updating lk2nd and restarting into it, load the actual XNU kernel/rootfs
package temporarily:

```sh
fastboot boot xnu-boot.img
```

No USB driver runs in the current XNU image; return to lk2nd by hardware reboot.
The modified bootloader was written from the running lk2nd interface with:

```sh
fastboot flash lk2nd artifacts/lk2nd-a6plte-xnu.img
```

On this SM-A605FN, `fastboot reboot bootloader` entered Samsung Odin mode.
Use a hardware restart and press Volume Down after the screen/vibration to return
to lk2nd fastboot. The `lk2nd` target updates the bootloader's 512 KiB region;
`boot` is the separate boot-image area exposed by lk2nd.
The updated fastboot boot path maps the complete initrd destination before
copying: a kernel/rootfs package at DDR + 54 MiB exceeds the original 90 MiB
startup mapping. Wrapper offsets remain unchanged. Booting this larger image
through the old loader reset the phone before XNU entry.

`package-boot.sh /path/to/kernel [raw-ramdisk.hfs]` requires an actual linked
ARM64_ALL Mach-O MH_EXECUTE with LC_UNIXTHREAD. It rejects ARM64e, IMG4 and filesets.
The bridge reserves a verified contiguous 256 MiB window for a kernel/rootfs
package, or 128 MiB for a kernel-only package, with no address slide. Firmware,
framebuffer, device tree and downloaded source buffers are excluded.
`serial=1` selects the substituted framebuffer ABI, not hardware UART.

## Remaining work

Full corecrypto integration, runtime compatibility of external dependencies,
a complete platform device tree, and exception/timer validation remain in progress. SMP,
eMMC and power management are not implemented; HFS+ rootfs and the first EL0
process await hardware validation. Compiled-file counts
are not a measure of boot readiness.

## Sources and licensing

Upstream sources are fetched at fixed commits; this repository stores patches:

- [lk2nd](https://github.com/msm8916-mainline/lk2nd), `dd6c1db1c085b419ac5dfffbd429aadb994ac094`.
- [XNU rel/xnu-12377](https://github.com/apple-oss-distributions/xnu/tree/rel/xnu-12377),
  `ac9718fb1af618d5ce8678d0dc6e8a58f252216f` (12377.121.6).
- [libpthread-539.100.4](https://github.com/apple-oss-distributions/libpthread/tree/libpthread-539.100.4),
  `1f4f5265b319111142f1bf3a27d4484ef5a98314`, kernel component.
- [XNU xnu-1699.32.7 AES C implementation](https://github.com/apple-oss-distributions/xnu/tree/161efb48ee9912c6935f205e7ac9c370edb09318/bsd/crypto/aes),
  `161efb48ee9912c6935f205e7ac9c370edb09318`, with Brian Gladman's license retained
  in source and [licenses/legacy-aes.txt](licenses/legacy-aes.txt).
  This table-based bootstrap path does not provide constant-time AES or a full
  corecrypto provider; see `libkern/crypto/a6plte_aes/SOURCE.txt` in the patched XNU.
- [hfs-715.120.4](https://github.com/apple-oss-distributions/hfs/tree/hfs-715.120.4),
  `124b970fd5390f1c2cd6f985478616a04f6eeb1f`, native HFS+ driver and encoding sources.
- [XNU xnu-1699.32.7 MD5 implementation](https://github.com/apple-oss-distributions/xnu/blob/161efb48ee9912c6935f205e7ac9c370edb09318/libkern/crypto/md5.c),
  derived from the RSA Data Security, Inc. MD5 Message-Digest Algorithm;
  [license notices](licenses/legacy-md5.txt) are retained.
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
