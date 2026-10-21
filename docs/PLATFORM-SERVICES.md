# A6PLTE platform services

These are built-in board implementations, published as children of
`A6PLTEPlatformExpert`. They use XNU's actual IOService, IOUserClient, IOTimerEventSource,
IOBufferMemoryDescriptor and IODeviceMemory classes. They do not load Apple's
closed platform kexts. The kernel build and actual phone execution are separate
checks. On SM-A605FN the user confirmed `IO services 31 / watchdog timeout: no reset`
with a continuing sleep/wakeup counter from source `0cf5061`. All four startup
paths, the native surface allocation smoke check, and diagnostic timer expiry
therefore completed on the phone. The f72b97a kernel adds an iOS 16 graphics protocol subset and has been sent
to the phone. Actual GUI output and private-framework operation still require
phone evidence; a successful fastboot transfer does not establish either.

| Service | Implemented behavior | Limit |
| --- | --- | --- |
| `IOWatchDogTimer` (`A6PLTEWatchdog`) | Native IOKit diagnostic timer; records requests and expiry count, prints an expiry message | No hardware watchdog, reset register, panic or reboot on expiry |
| `AppleKeyStore` | Stub state queries 17/35 return bounded DER; selector 7 reports unlocked state, 14 returns system handle, 101 consumes an assertion | No SEP, hardware keys, keybag encryption or cryptographic operations |
| `AppleSmartBattery` | Explicit IOPMPowerSource stub reporting 100%, installed, not charging | No fuel-gauge measurement; marked `A6Stub` and `A6ActualChargeMeasured=false` |
| `IOCoreSurfaceRoot` / `IOSurfaceRootUserClient` | iOS 16 creation/limits, ID and Mach-port lookup, shared pixel/state mappings, cached-client result, lock/seed traps and lifetime management | 64 MiB per allocation/pool, 256 mappings per client; accelerator, shared-event and optional attachment operations unsupported |
| `AppleCLCD` / `IOMobileFramebufferUserClient` | Native type-zero client, display geometry, default BGRA surface, four-layer CPU composition/scaling, retained swaps, completion wait and software vsync notifications | Software subset, default 10 Hz present / 60 Hz notifications; no GPU, mode switching or hardware VBL interrupt |

The graphics protocol is adapted from the author's
[0046 implementation](https://github.com/dipa-studio/ios-sweet/blob/425b25102b6a9ee4b68fb2b9ca5d6a086b8a4116/xnu/patches/0046-sweet-iosurface-iomfb.patch),
with the cached-client convention from
[0068](https://github.com/dipa-studio/ios-sweet/blob/425b25102b6a9ee4b68fb2b9ca5d6a086b8a4116/xnu/patches/0068-sweet-surface-lookup-cached.patch).
The board publishes a real `disp0` device-tree nub, `display-subsystem` type,
and 1080x2220 canvas. `AppleCLCD` matches that nub. It never exposes the RGB888
panel memory as a falsely advertised 32-bit surface: clients share a real BGRA
software default surface, and the presenter converts it to the inherited panel's
actual pixel format. Pending swaps retain their surface objects until replaced;
port-held objects reserve their IDs, and client mappings/task references have
bounded lifetimes. Parent buffers retain their storage owner and quota.

After a non-black full-canvas frame from backboardd/SpringBoard has actually
been presented, ordinary console stores stop touching the screen. Logging
continues into memory. Panic or an early EL1 exception restores the console and
stops further graphics presentation. No path redirects the console to UART.
The display keeps lk2nd's MDP/DSI configuration. Touch remains unconfirmed.

The default IOSurface also has to act as scanout memory when a client draws
directly without submitting `SwapEnd`. The A6 BGRA shadow is now refreshed at
the presentation rate after an eligible backboardd/SpringBoard client obtains
it. Untouched/black initial storage preserves the boot console. The first real
colored full frame takes over, subsequent black frames remain valid, and layer
swaps take over from direct refresh. Waiting for a swap before one was queued
is a successful empty wait. These fixes do not establish that the frameworks
have reached this path on the phone.

The reported S6SY761 probe `command 21 / reg 02000018 / value 00000040`
identifies a QUP operational timeout with the output FIFO full. The transport
now waits for physical I2C STOP/bus idle before resetting QUP, accepts the FIFO
OUTPUT_SERVICE completion when MAX_OUTPUT_DONE lags, and waits for mini-core
selection readiness. Delayed-STOP regression reproduces that exact timeout with
the old driver and passes with the fix; physical touch remains unconfirmed.
The next photo, IMG_3460, supplies `command 60 / reg 02000018 / value 000004c0`:
MAX_OUTPUT_DONE is already set. Counted output completion now honors DONE
without waiting for a stale fullness bit to clear; tagged receive also drains
on INPUT_SERVICE/INPUT_DONE. Actual-code tests reproduce both flag sequences,
alongside the existing delayed-STOP and pending-output cases. This follows the
completion and FIFO servicing in the upstream QUP driver, but real sensor
operation is still unverified.
Register/handshake references are the pinned
[Linux QUP driver](https://github.com/msm8953-mainline/linux/blob/d9eabbae3edea6adb08e74c30059aa0933afaae7/drivers/i2c/busses/i2c-qup.c).

## Watchdog policy

The service derives from the real `IOWatchDogTimer` base, including its sleep
notification contract and administrator check. An OSNumber in `setProperties`
sets the diagnostic timeout in seconds; zero cancels. `IOWatchDogEnabled` stays
false, `A6HardwareResetEnabled` is false, and `A6WatchdogLogOnly` is true.
No operation in this driver writes hardware registers or calls reboot/panic.

An initial two-second diagnostic timer exercises the real workloop timer. Its
expected framebuffer message is:

```
A6PLTE watchdog: timeout observed; continuing without reset
```

The independent IOKit PM sleep/wake panic watchdog is disabled using
`kIOSleepWakeWdogOff` for A6PLTE, retained when the debug sysctl is changed.
This does not claim that unrelated faults, explicit reboot requests or external
firmware can never restart the device.

## Key-storage capability

Before BSD/userspace starts, the platform expert publishes the presence-only
`IODeviceTree:/defaults/no-effaceable-storage` property as empty OSData. The
A6+ has no Apple EffaceableStorage or SEP. This lets MobileKeyBag choose its
non-effaceable storage path; it does not supply keys or make the AppleKeyStore
stub support encrypted keybags. `/defaults/content-protect` remains absent.
Existing firmware flags are preserved, and failed publication fails platform
startup. No `/options` NVRAM service or keybag files are synthesized.

The same declaration is used by the
[iOS 16 qemu-t8030 board](https://github.com/TrungNguyen1909/qemu-t8030/blob/iOS16/hw/arm/xnu.c#L360).
The presence-only lookup and branch away from loading `systembag.kb` are
documented in the author's
[MobileKeyBag analysis](https://github.com/wh1te4ever/usbliter8-fun/blob/84c0a31806c53bfe36eee6c669c671c0b2ced5be/work-27.0b2/dt_patch3.py).
That branch analysis is from a different OS release; passing MKB on the user's
prepared system still requires hardware verification.

## Legacy A6 graphics ABI v1 (not published)

The former experimental A6-only graphics clients remain as unpublished legacy
classes; their old layout helpers still have regression coverage. The following
is their ABI documentation, not the interface now offered to iOS. The legacy
source of truth is `iokit/Kernel/arm/A6PlatformServicesABI.h`. `IOServiceOpen` uses connection type `0x41365031` (`A6P1`) and requires
administrator privilege. Standard private Apple graphics connection types are
rejected. The stub keystore also accepts type zero, with unsupported operations.

For `IOSurfaceRoot`, selector 0 takes three scalars (width, height, pixel format)
and returns a 32-byte `a6_surface_info`; selector 1 returns the same information;
selector 2 releases that connection's surface handle. Format 1 is RGB888 and
format 2 is XRGB8888. Row bytes are rounded to 64; the allocation to 4096.
Memory type 1 maps the surface read/write. Each allocation is zeroed, including
padding. The RAM quota follows the descriptor until its last reference dies,
including mappings that survive handle destruction.

For `IOMobileFramebuffer`, selector 0 returns a 32-byte `a6_display_info` with
no physical or kernel virtual address. Memory type 1 maps only the real
framebuffer aperture, read-only with the appropriate uncached mapping option.
Selector 1 takes five scalars (x, y, width, height, source row bytes) and an inline
pixel buffer up to 64 KiB, in the current display format. Rectangles and source
lengths are checked before copying. Larger updates can be split into rows/tiles.

Unsupported selectors, async requests and out-of-line structure arguments fail.
Generic physical mapping, arbitrary kernel access and changing scanout addresses
are not exposed. Unit tests exercise overflow, zero sizes, format rejection,
allocation caps, edge rectangles and 100,000 randomized layout/bounds cases with
ASan/UBSan. Actual userspace IORegistry matching, user mappings and blits still need
hardware verification. Diagnostic timer expiry and service startup have been
confirmed through the native PID1 sysctl output.

`kern.a6plte_services` is a read-only native sysctl. Bits 1/2/4/8 record successful
watchdog/keystore-stub/surface/framebuffer startup; bit 16 is set only when the
real watchdog timer callback observes its deadline. PID1 reads it through
`SYS_sysctlbyname` after each sleep/wakeup and prints the numeric mask. `31`
means all four startup paths completed and the timer expired without requesting
reset. It does not certify untested user-client operations or iOS private ABI.

## Original physical input

`A6Input.c`, `A6HIDWire.c` and `A6HID.cpp` implement board input independently of
Sweet HID. The controller is Samsung S6SY761 at I2C address 0x48 on BLSP1 QUP2
(0x078b6000), using TLMM pins 6/7, IRQ pin 59 and supply enable pin 139. Polling
uses short FIFO transfers with bounded waits and no DMA. The board DT overrides
the sensor range to 0..4095 on each axis; these units are normalized into HID
coordinates for the physical 1080x2220 display.

Volume-up uses GPIO85. Power and volume-down use read-only PM8953 PON RT_STS
commands through the SPMI observer channel. Button debounce requires three
samples. The driver never issues PMIC power/reset commands or firmware updates.

The event services expose the public Apple event-service queue representation:
ESUC connection type, open/close/copy selectors, native IOSharedDataQueue memory
and notifications, digitizer collections with ten contacts, and consumer keys
for volume/power. There are at most eight clients per service. Queue congestion
coalesces pending state; draining the queue retries the latest state, including
releases. Replay and live delivery are serialized. The client cannot inject
input or expose controller registers. Element output and matching-event copy
remain unsupported. This is a subset of IOHIDFamily; successful iOS/backboardd
integration has not yet been demonstrated.

ASan/UBSan tests cover QUP repeated START, tagged FIFO reads, sensor decoding,
contact bounds/releases, read-only PON commands, button debounce, timeouts and
HID packet bounds. Native compilation/linking passed. Hardware probing and
actual button/touch events still need confirmation. A failed probe is reported
as such rather than producing simulated contacts.
