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

All jobs in [Actions run 39564909222](https://github.com/omauser119/a6plte-xnu/actions/runs/39564909222)
passed for source `80a9d97`, including Apple Clang, linking with no undefined
symbols, ASan/UBSan host checks and both image profiles. This includes the HFS
catalog bounds fix, persistent hash conversion, bounded userdata cache policy
and polled QUP FIFO/application startup fixes.
Download just the kernel with
`python3 scripts/download-ci-kernel.py 39564909222`, then package it locally.
The downloader verifies the GitHub archive SHA256 before extraction.

Hardware confirmed native launchd image activation and successful 16-KiB code
signature verification on the 4-KiB kernel. Dyld then reported that its shared
cache was not loaded and `libSystem.B.dylib` was unavailable; split-cache and
mapping diagnostics are included. This is not yet a successful launchd boot.
The CPU0-only `80a9d97` image has been accepted by fastboot. Screen confirmation
of checkpoint creation/reuse and physical touch is still pending.

The `333bb5d` hardware run stopped in `__memmove_chk` (`16 < 32`) after HFS
journal setup. Apple's catalog writer copied the adjacent 16-byte `userInfo`
and `finderInfo` fields through a pointer to the first field. The HFS patch now
copies each field separately and zeros the two fork records separately, with
XNU's strict bounds checks kept enabled. A regression test runs the actual
catalog create/update/read functions against Apple's on-disk types and XNU's
guard: the old source reproduces the exact failure, and the corrected source
preserves all 32 Finder bytes, both forks and neighboring bytes. Hardware
confirmation of this fix is pending.

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

Hardware `2a53d3c` reached all reported signature/header checks successfully,
including `.42.dyldlinkedit` (318 MiB signed coverage), but map2 returned `EPERM`
for 44 files / 52 mappings. A board-limited root-cache policy handles the absence
of macOS SIP file flags on the user-prepared HFS volume; ownership, known cache
directory, same-root mount and code-signature checks remain. Hardware aa5824e
now confirms successful map2 for all 44 files / 52 mappings and real launchd
execution through the first `/sbin/mount` boot task.

At the user's request, this standalone board bypasses the Apple platform-binary
requirement for regular files on the selected userdata OS root, without an AMFI
provider. This includes pre-exec `F_GETSIGSINFO` (offset zero or wildcard -1,
without an attached signature), process/blob/file queries and the loaded task's
platform status. All files on that root receive this compatibility status;
this is not Apple CMS authentication. Other mounts and a real AMFI provider keep
their native behavior. CodeDirectory/page verification, validity flags, other
MAC failures and Mach-O load errors are not replaced with success. Prepared
userspace files remain unchanged. The earlier exec-only policies still failed
on hardware c0e8470. Hardware 7538fd7 passed the platform check and next reported
failure to retrieve a boot task's codesigning identity (`ENOENT`). Without AMFI,
the native CodeDirectory path never set the process-only `CS_SIGNED` flag, so
`cs_identity_get()` hid even an existing identifier. The board signature callback
now sets that bit only for a real, natively validated CodeDirectory on the selected
OS root. The native loader/exec path then preserves the original identity for
`CS_OPS_IDENTITY`; no identifier, team ID, entitlement or validity bit is invented.
Native-body regressions reproduce the old `ENOENT`, verify the original identifier
and syscall buffer/error behavior, and reject unsigned/invalid or foreign files.
Hardware confirmation of this identity fix is pending.

Hardware a05051c passed identity retrieval and next reported a missing boot
manifest hash. The board platform expert now supplies `/chosen/boot-manifest-hash`
before BSD startup, so both the native registry reader and `kern.bootobjectspath`
can read it. Because this lk2nd boot has no Apple Image4 manifest, this value is
an explicit standalone compatibility identity: SHA-384 of the ASCII domain
`A6PLTE standalone boot identity v1` followed by the linked kernel's 16-byte UUID.
It is stable across reboots of that image and changes with the image UUID;
it authenticates neither an Apple manifest nor any userspace/preboot files.
Existing valid firmware hashes are preserved. No files or directories are
created in the prepared OS root. Hardware confirmation is pending.

## Persistent code-signature conversion

The 16-KiB-to-4-KiB hash conversion now checkpoints to hidden
`/.a6cs4k-v2-<SHA256>` files on the userdata root. The first run still verifies
the source against its original CodeDirectory. Every 4 MiB it appends a bounded,
SHA256-checked record and uses HFS `F_FULLFSYNC` to commit it. A later boot reuses
complete records and resumes after the last valid record, including after an
interrupted first run. A torn or corrupt tail is recomputed. The key includes
the full CodeDirectory, source file ID, size, modification/change times, base
offset and hash geometry; source changes during conversion reject publication.

Cache files must be regular, root-owned, mode 0600, have one link and belong to
the userdata root mount. Symlinks and other mounts are rejected. This experimental
port trusts root-owned derived hash metadata; record checksums detect corruption,
not malicious replacement by root. Native VM faults still hash the actual 4-KiB
page against the table. Cache I/O failure falls back to source verification.
The explicitly writable userdata HFS root is mounted writable before launchd,
because dyld needs checkpoints before launchd can perform a remount. The driver's
read-only GPT attribute and `a6_userdata_rw=0` remain effective.

An empty `shared_region_check_np` probe still returns its native `ENOMEM`, which
dyld uses to proceed with mapping. On this board it is no longer printed as an
unexpected `vm_shared_region_start_address() failed`; no address or successful
mapping is fabricated. Actual signature and map2 failures remain in the PID1
panic summary. Hardware aa5824e has now passed the complete split-cache mapping;
the current boot-helper failure and its platform-status fix are described above.

Historical hardware reports elsewhere describe XNU 12377.
