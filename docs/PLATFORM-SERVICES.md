# A6PLTE platform services

These are built-in board implementations, published as children of
`A6PLTEPlatformExpert`. They use XNU's actual IOService, IOUserClient, IOTimerEventSource,
IOBufferMemoryDescriptor and IODeviceMemory classes. They do not load Apple's
closed platform kexts. The kernel build and actual phone execution are separate
checks. On SM-A605FN the user confirmed `IO services 31 / watchdog timeout: no reset`
with a continuing sleep/wakeup counter from source `0cf5061`. All four startup
paths, the native surface allocation smoke check, and diagnostic timer expiry
therefore completed on the phone. User-client mappings/blits and private iOS
framework compatibility have not been hardware-tested.

| Service | Implemented behavior | Limit |
| --- | --- | --- |
| `IOWatchDogTimer` (`A6PLTEWatchdog`) | Native IOKit diagnostic timer; records requests and expiry count, prints an expiry message | No hardware watchdog, reset register, panic or reboot on expiry |
| `AppleKeyStore` | Stub state queries 17/35 return bounded DER; selector 7 reports unlocked state, 14 returns system handle, 101 consumes an assertion | No SEP, hardware keys, keybag encryption or cryptographic operations |
| `AppleSmartBattery` | Explicit IOPMPowerSource stub reporting 100%, installed, not charging | No fuel-gauge measurement; marked `A6Stub` and `A6ActualChargeMeasured=false` |
| `IOSurfaceRoot` | Zeroed, page-aligned CPU buffers, shared through native IOKit memory mappings | A6 ABI, one surface per connection, 8 MiB per surface and 32 MiB total; no GPU or global IOSurface-ID lookup |
| `IOMobileFramebuffer` | Actual inherited screen geometry, read-only scanout mapping and bounded CPU rectangle writes | A6 ABI, RGB888/XRGB8888, no mode switching, GPU, page flip or VBL callback |

The graphics services are an initial CPU implementation. Their presence does
not establish compatibility with the private user-client protocol used by
Apple's IOSurface.framework or IOMobileFramebuffer.framework. They advertise
`A6PrivateAppleABICompatible = false`. Those clients must not be treated as
working until their exact ABI and dependencies have been implemented and tested.

The framebuffer console remains active. Kernel log output can overwrite rendered
pixels. The driver does not replace lk2nd's MDP/DSI setup or reinitialize the panel.

The reported S6SY761 probe `command 21 / reg 02000018 / value 00000040`
identifies a QUP operational timeout with the output FIFO full. The transport
now waits for physical I2C STOP/bus idle before resetting QUP, accepts the FIFO
OUTPUT_SERVICE completion when MAX_OUTPUT_DONE lags, and waits for mini-core
selection readiness. Delayed-STOP regression reproduces that exact timeout with
the old driver and passes with the fix; physical touch remains unconfirmed.
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

## A6 graphics ABI v1

The source of truth is `iokit/Kernel/arm/A6PlatformServicesABI.h` in the patched
XNU tree. `IOServiceOpen` uses connection type `0x41365031` (`A6P1`) and requires
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
