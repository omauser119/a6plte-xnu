# XNU 8796 for Samsung SM-A605FN / a6plte

This branch ports the existing board support to **Apple XNU 8796.141.3,
Darwin 22.6.0**. The XNU 12377 image remains on `main`.

The requested image mounts a user-prepared bare HFS+/HFSX volume on GPT
`userdata` and selects `/sbin/launchd` as PID1. It contains no embedded rootfs.
USB code is retained but disabled by default. UART is prohibited; console and
panic output use the inherited framebuffer. Do not format userdata or replace
the user's files. The user issued **«паста»** and hardware testing has started.

## Build

The `A6PLTE XNU 8796` Actions workflow builds the native ARM64 kernel with Apple
Clang, checks every component, links without undefined symbols and packages
`xnu-8796-userdata-boot.img`. A separate ramdisk/a6-init image is also built.

```sh
python3 scripts/fetch-sources.py
./scripts/test.sh
# The complete kernel build uses the macOS Actions workflow.
./scripts/package-boot.sh --root=userdata artifacts/kernel.a6plte
python3 scripts/check-userdata-boot.py artifacts/kernel.a6plte artifacts/xnu-8796-userdata-boot.img
```

The boot bridge uses the native 8796 BootArgs layout (608-byte command line,
736-byte structure), checked against Apple's header during compilation.
The port keeps GICv2, the architectural timer, bounded userdata eMMC I/O,
HFS+ preflight, framebuffer locking and the board platform services.
The Apple performance-counter/profiling drivers are disabled for this board.
Provider-free SHA-384/SHA-512 uses an original scalar implementation of
FIPS 180-4, checked against hashlib across 666 streaming and alignment cases;
the adapter checks the native 8796 digest-context layout at compile time.

## Pinned sources

These kernel dependencies match Apple's `distribution-macOS` `macos-135` tree:

- XNU `8796.141.3`: `1b191cb58250d0705d8a51287127505aa4bc0789`.
- HFS `627.100.6`: `31d5ec238dfab485e78a9a30b8b92d13e8914f03`.
- libpthread `514.100.2`: `a6c70ca0e544347a0377babf748f831577ec24f9`.
- libdispatch `1415.140.2`: `cdb61e93e803d0093635f356753a9a30c09836db`.
- bootstrap_cmds `129`: `fc3180f320239c85da79fc30a281a8830f1301f1`.

Source fetches apply this branch's patches, not the 12377 patches.
Xcode 16 IIG output is adapted to the original contiguous Mach RPC messages:
8796 keeps its four-field IORPC, with content resolved by its native
`IORPCMessageFromMach()` helper. Kernel C++ uses the upstream C++17 dialect.
The native Apple allocator builtins remain enabled; no fake allocator types or
undefined-symbol link bypass is used. The installed lk2nd does not need a new
package format or a flash operation for this profile.

## Verification status

All jobs in [Actions run 39445871601](https://github.com/omauser119/a6plte-xnu/actions/runs/39445871601)
passed for native source `665a2d5`, including Apple Clang, linking with no undefined
symbols, ASan/UBSan host checks and both image profiles. Download just the kernel
with `python3 scripts/download-ci-kernel.py 39445871601`, then package it locally.
The downloader verifies the GitHub archive SHA256 before extraction.

Hardware confirmed native launchd image activation and successful 16-KiB code
signature verification on the 4-KiB kernel. Dyld then reported that its shared
cache was not loaded and `libSystem.B.dylib` was unavailable; split-cache and
mapping diagnostics are included. This is not yet a successful launchd boot.

All boot profiles currently use `cpus=1`: SMP is temporarily disabled at the
user's request. The CPU0-only image reaches dyld. The retained SMP code describes
eight Cortex-A53 CPUs in two clusters, with PSCI startup, per-CPU GICv2/timers,
SGI IPIs and a cross-CPU framebuffer lock. The first SMP
attempt found a pre-MMU string lookup table, fixed with PC-relative code and a
relocation regression check. The next attempt reached CPU registration and
reported a missing kernel PRNG. Source `f260bf3` installs native HMAC-SHA256 DRBG
instances through XNU's kernel PRNG API before registering/starting APs. This
code is built and verified; eight online CPUs have not been demonstrated.

Hardware reported `S6SY761 probe failed` and another dyld cache load refusal.
The latest build explicitly clears I2C error flags, preserves the original
failure across cleanup and reports the sensor command/register/value. Before
a PID1 panic it repeats the saved split-cache, signature errno/coverage, mmap
and shared-region results in a compact framebuffer summary. These are
diagnostics, not confirmation that the touchscreen or launchd now works.
The userdata block strategy now accepts large filesystem buffers while retaining
whole-request partition bounds; native-strategy tests cover 1-MiB reads/writes,
cross-boundary rejection and the unchanged raw I/O cap. The next hardware boot
must confirm whether this fixes the reported cache signature `EINVAL`.
See [platform services](docs/PLATFORM-SERVICES.md) for input compatibility limits.

Historical hardware reports elsewhere describe XNU 12377.
