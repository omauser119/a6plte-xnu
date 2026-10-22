The original patches in this directory are byte-for-byte copies from
[dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet/tree/425b25102b6a9ee4b68fb2b9ca5d6a086b8a4116/xnu/patches),
commit `425b25102b6a9ee4b68fb2b9ca5d6a086b8a4116`.

`0046-sweet-iosurface-iomfb.patch` is the implementation source, not a description
used to write another implementation. `scripts/apply-sweet-0046.py` extracts its
three complete new graphics files, changes the Sweet names to A6 names, applies
the author's `0068` cached-client correction, and applies the separately
reviewable `patches/0046-a6plte-adaptation.patch`. SHA-256 checks protect both
unchanged upstream patches. The script's `--verify` mode checks that the actual
compiled source files equal that result byte for byte.

The A6 adaptation supplies the inherited 1080x2220 panel geometry, a BGRA shadow
for its RGB888 scanout, scalar pixel conversion, framebuffer-only console handoff
and panic recovery, and the author's 0056-style latest-frame timer. Catalogue
integration follows 0046's IOResources/IOCoreSurfaceRoot and AppleCLCD matching.
Small allocation/lifetime and integer bounds corrections preserve valid wire
behavior. The base selector methods, surface result layout and rectangle-copy
path remain the copied implementation. Sweet HID is not imported.

The explicit adaptation also fixes display-mode publication, the current-mode
reply, the absolute-time query and vsync timestamp/port semantics using
[OOSEX GANG's MiniIOMobileFramebuffer.cpp](https://github.com/oosexgang/hackios-xnu-kernel/blob/8e61187098f2c26c5daee8f9f72b6416aa64b9ab/xnu/files/iokit/Kernel/MiniIOMobileFramebuffer.cpp)
as the primary compatibility reference (APSL 2.0, commit
`8e61187098f2c26c5daee8f9f72b6416aa64b9ab`, source SHA-256
`78141b3294b6c16b9173d5a7af64dc0b8a16f57d8027c93be608ef9dbbf764e9`).
Samsung geometry/identity, RGB888 conversion, CPU0-only operation and our own HID
are retained. No other device's GPU, injected userspace, logging/recording or
loader-return paths are imported.

`0040-sweet-iowatchdog.patch` and `0045-sweet-iowatchdog-pmu-primary.patch`
document the watchdogd-facing service/client class names, selectors and primary
PMU property. The A6 implementation in `A6PlatformServices.cpp` adapts that
interface around its existing diagnostic timer: supported check-ins return
bounded zeroed replies, boot-stage dictionary writes are accepted and hardware
reset remains disabled. No selector tracing is added. Their SHA-256 values are
`c58a94a2ce3acc03e5b60efc1a98a8c8fd723fe139908186396a119248879669` and
`5733977651e593d6a4179b7b16d3d8c14459dff1ae48dc16d1ff718cff0ca4d2`.
