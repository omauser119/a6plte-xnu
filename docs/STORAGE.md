# A6PLTE eMMC userdata device

The current driver adopts the controller and card state retained by the modified
lk2nd XNU handoff. It uses SDHCI PIO, single 512-byte blocks, polling with bounded
timeouts and no DMA. It preserves clock, power, bus width and DLL/tuning settings.
The pinned lk2nd assigns eMMC RCA 2. The a6plte DT identifies the host at
`0x07824900` and core at `0x07824000`.

The driver reads EXT_CSD and requires a selected user area, sector addressing and
512-byte logical sectors. It checks both GPT header CRCs, both entry-array CRCs,
identical entries, usable disk ranges, non-overlapping partitions, unique GUIDs
and one exact UTF-16 `userdata` name. It then publishes only:

- `/dev/a6userdata`: native BSD block device.
- `/dev/ra6userdata`: native BSD raw device, using `physio`.

Both nodes are root-only (0600). Read/write is enabled as requested, subject to
the GPT read-only attribute. The native kernel argument `a6_userdata_rw=0` can
force read-only operation. The bridge's fixed kernel command line is defined in
`shim/loader.c`; an Android fastboot `-c` argument is not automatically forwarded
to XNU.

Every request is validated before physical sector translation. It must fit
completely inside `userdata`; overflow, invalid alignment and out-of-range writes
are rejected. There is no whole-eMMC node or erase, format, discard or RPMB
interface. Reads/writes use CMD17/CMD24. The driver waits for card readiness after
writes and issues the EXT_CSD cache-flush CMD6 when the card cache is enabled.
Timeouts or card/host errors take the backend offline; ambiguous writes are not
automatically retried.

## Layout observed on the connected SM-A605FN

`fastboot getvar all` reports a 512-byte logical block and a `userdata` size of
`0x623efb000` bytes. This loader does not publish the partition offset. Reading
its live GPT-derived partition entry over the USB debug interface supplied the
following matching geometry:

| Quantity | Value |
| --- | --- |
| First LBA | 9,562,112 (`0x91e800`) |
| Last LBA, inclusive | 61,071,319 (`0x3a3dfd7`) |
| Sector count | 51,509,208 |
| Byte start | 4,895,801,344 (`0x123d00000`) |
| Byte end, exclusive | 31,268,515,840 (`0x747bfb000`) |
| Byte size | 26,372,714,496 (`0x623efb000`) |

These values are evidence for this phone, not hardcoded driver limits. The
kernel independently validates the on-disk GPT before publishing the slice.
Full getvar/debug logs and device identifiers remain in ignored local artifacts.

## Validation

Host ASan/UBSan tests cover 128/256/512-byte GPT entries, corrupt headers/tables,
overlap, duplicate names/GUIDs, read-only attributes, overflow, boundary writes
and unchanged bytes outside the slice. The SDHCI emulator checks PIO transfers,
unaligned buffers, inherited state, R1/CRC errors, command/data timeouts, cache
flush and absence of automatic write retries. All three native BSD modules also
compile against XNU headers.

The first hardware check passed on the connected SM-A605FN with source
`f7c546c`: the user confirmed `PID1: eMMC userdata sector read OK`. PID1 opened
the native raw node and read a 512-byte sector through the SDHCI PIO backend.
The node is published only after EXT_CSD checks and both GPT copies validate,
so this result also exercises that initialization path on the real card.
The probe also attempts block-count and write-availability queries; their exact
displayed values have not been reported separately. Actual hardware write/readback
and HFS+ mounting on userdata remain separate acceptance checks on the user's
prepared volume. The ramdisk is not formatted or copied onto userdata by this probe.

## Root volume on userdata

The user has issued **«чеснок»** and selected `/sbin/launchd`. Build the image now;
do not run `fastboot boot` or reboot the phone until the user issues **«паста»**
as a command. Mentioning that word while defining this rule is not activation.
USB stays disabled and UART remains prohibited.

`scripts/package-boot.sh --root=userdata artifacts/kernel.a6plte` produces
`artifacts/xnu-userdata-boot.img`. It contains the kernel and bridge, no rootfs.
The bridge donates a checked 256 MiB RAM arena and supplies
`rd=a6userdata launchdsuffix=release`. The ramdisk image and `a6-init` remain
available separately as `artifacts/xnu-boot.img`.

The native BSD root path uses the dynamically assigned userdata device number;
it does not guess a major number or wait for an absent IOStorageFamily driver.
It checks both GPT copies, then the primary and alternate HFS+/HFSX headers,
block geometry and partition bounds. A bare filesystem must start at offset
zero in userdata, with its primary header at byte 1024. A copied volume may be
smaller than the partition; its alternate header is checked at its own end.
The preflight issues reads only and stops with a framebuffer panic if invalid.
Apple's HFS driver performs the subsequent actual root mount. An unsealed HFS+
root is exempted from the Apple APFS root-seal ioctl only for this validated
board root; executable validation is unchanged.

The user prepares the filesystem, `/sbin/launchd` and its runtime files.
Preparation does not format userdata, replace those files or write another
partition. A read-only fetch of the current first 4 KiB found no HFS+/HFSX
signature at byte 1024; mounting the prepared volume and running launchd are
still hardware checks. Raw partition contents stay in private artifacts.

The candidate from source `d65d1fb` is available in the `xnu-boot-image`
artifact of [Actions run 39278476097](https://github.com/omauser119/a6plte-xnu/actions/runs/39278476097).
The downloaded `xnu-userdata-boot.img` is 20,875,264 bytes, SHA-256
`cda18b60930bf040621b36d5e4a9bbe7376e22a336f2529b3f0cd54d8df4d9eb`.
`check-userdata-boot.py` passed on both the locally packaged image and the
downloaded CI image: complete CRC, expected kernel payload and native root
symbols, explicit launchd selection, no embedded rootfs or USB enable argument.
The CI image is saved locally as `build/userdata-d65d1fb/xnu-userdata-boot.img`.
This candidate has not been booted on the phone; the **«паста»** gate still applies.
