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
