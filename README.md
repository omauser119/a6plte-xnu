# XNU 12377 bring-up for Samsung Galaxy A6+ (SM-A605FN)

**Experimental, incomplete port. No bootable XNU kernel yet. UART is not used.**

The only hardware-confirmed result is a temporary ARM64 framebuffer payload loaded
through installed lk2nd 23.1: text and a continuously increasing display heartbeat.
This payload is not XNU. The modified lk2nd image has not been tested on hardware.

## Implemented

- RGB888/RGB565/XRGB8888 framebuffer console, scrolling and bounded geometry.
- ARM64 boot bridge: FDT parsing, reserved RAM handling, experimental Mach-O loader,
  XNU boot arguments and minimal Apple device tree.
- XNU early physical framebuffer marker, deferred logs across MMU setup, framebuffer
  remapping and replacement of UART console ABI with screen output.
- Initial Cortex-A53/A6PLTE profile, 4K pages, one CPU, GICv2 and virtual timer wiring.
- No-LSE commpage locks and exclusion of Apple-specific initialization.
- Pinned upstream patches, native config/MIG tools and component compilation probes.

SM-A605FN HW.Rev.4 display: 1080×2220 packed RGB888, stride 3240,
framebuffer physical address 0x90001000. GIC integration is not hardware-validated.

## GitHub Actions

`A6PLTE bring-up` runs on pushes, pull requests and manual dispatch:

- **Linux:** host tests, framebuffer boot image and UART-disabled lk2nd image.
- **macOS:** Apple Clang, native MIG, platform objects and broader XNU compilation.

Artifacts explicitly distinguish framebuffer/lk2nd images from XNU diagnostics.
The XNU job is expected to expose remaining errors; a green platform check is not
proof of a linked or bootable kernel. No workflow flashes a device.

## Reproduce

Use a fresh checkout (fetch refuses to overwrite existing upstream directories):

```sh
python3 scripts/fetch-sources.py
./scripts/test.sh
./scripts/build-smoke.sh
./scripts/build-lk2nd.sh
```

Linux dependencies: clang, llvm, lld, dtc, mkbootimg, GNU make, ARM bare-metal GCC,
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
XNU typed-allocation builtins. `check-platform.sh` generates 72 MIG interfaces and
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
There is no installation/flashing procedure for the unvalidated modified lk2nd.

`package-boot.sh /path/to/kernel` requires an actual linked ARM64_ALL Mach-O
MH_EXECUTE with LC_UNIXTHREAD. It rejects ARM64e, IMG4 and filesets. The bridge
uses a 128 MiB reserved-memory-aware allocation and no address slide. Before
loading a full kernel, RAM and lk2nd download-buffer overlap must be checked.
`serial=1` selects the substituted framebuffer ABI, not hardware UART.

## Remaining work

Compiler/SDK compatibility, CoreEntitlements/TrustCache/corecrypto and other
external dependencies, full linking, complete platform device tree, actual XNU
boot and exception/timer validation. SMP, storage, rootfs and power management
are not implemented. Compiled-file counts are not a measure of boot readiness.

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
