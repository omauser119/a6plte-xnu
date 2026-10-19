# A6PLTE platform services

These are built-in board implementations, published as children of
`A6PLTEPlatformExpert`. They use XNU's actual IOService, IOUserClient, IOTimerEventSource,
IOBufferMemoryDescriptor and IODeviceMemory classes. They do not load Apple's
closed platform kexts. The kernel build and actual phone execution are separate
checks; this revision has not yet been verified on the phone.

| Service | Implemented behavior | Limit |
| --- | --- | --- |
| `IOWatchDogTimer` (`A6PLTEWatchdog`) | Native IOKit diagnostic timer; records requests and expiry count, prints an expiry message | No hardware watchdog, reset register, panic or reboot on expiry |
| `AppleKeyStore` | Discoverable, explicitly marked stub, administrator connection allowed | Every external selector returns unsupported; no keybag, SEP, hardware keys, encryption or fabricated success |
| `IOSurfaceRoot` | Zeroed, page-aligned CPU buffers, shared through native IOKit memory mappings | A6 ABI, one surface per connection, 8 MiB per surface and 32 MiB total; no GPU or global IOSurface-ID lookup |
| `IOMobileFramebuffer` | Actual inherited screen geometry, read-only scanout mapping and bounded CPU rectangle writes | A6 ABI, RGB888/XRGB8888, no mode switching, GPU, page flip or VBL callback |

The graphics services are an initial CPU implementation. Their presence does
not establish compatibility with the private user-client protocol used by
Apple's IOSurface.framework or IOMobileFramebuffer.framework. They advertise
`A6PrivateAppleABICompatible = false`. Those clients must not be treated as
working until their exact ABI and dependencies have been implemented and tested.

The framebuffer console remains active. Kernel log output can overwrite rendered
pixels. The driver does not replace lk2nd's MDP/DSI setup or reinitialize the panel.

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
ASan/UBSan. Actual IORegistry matching, user mappings, blits and timer expiry need
hardware verification.

`kern.a6plte_services` is a read-only native sysctl. Bits 1/2/4/8 record successful
watchdog/keystore-stub/surface/framebuffer startup; bit 16 is set only when the
real watchdog timer callback observes its deadline. PID1 reads it through
`SYS_sysctlbyname` after each sleep/wakeup and prints the numeric mask. `31`
means all four startup paths completed and the timer expired without requesting
reset. It does not certify untested user-client operations or iOS private ABI.
