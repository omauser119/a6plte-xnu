# A6PLTE USB Ethernet bring-up

USB is disabled by default at the user's request. The code stays compiled in,
but `a6_usb_init()` returns before MMIO mapping, interface allocation, DMA setup
or worker creation unless the boot argument `a6_usb=1` is explicitly supplied.
The normal boot image does not supply it. `a6-init` stays the only userspace
program and skips network configuration while USB is inactive. Userspace,
Bash and SSH work is deferred until the user requests it.

The first implementation adds a USB2 DWC3 peripheral driver and CDC-ECM control
protocol to the native BSD component. It adopts the already powered/trained USB2
PHY and clocks left by lk2nd. The device controller is reset before replacing
the loader's DMA buffers. UART is not used.

Board addresses and controller selection come from the pinned a6plte Linux DT
and lk2nd sources: DWC3 `0x07000000`, globals at offset `0xc100`, device registers
at `0xc700`. The implementation is original project code; register/command
sequence references are lk2nd's permissively licensed `usb30_dwc*.c` and the
public DWC3 register descriptions. No Linux driver code is linked into XNU.

## Current contract

- High-speed (512-byte bulk packets) and full-speed (64-byte) USB2 descriptors;
  one CDC communication interface and a data interface with alternate settings.
- EP0 setup/data/status transactions, bounded descriptor replies, address and
  configuration handling, interface selection, endpoint halt/clear, packet
  filter, and CDC network/speed notifications. Unsupported requests stall.
- Dedicated, cache-line-isolated kernel-image DMA buffers, one event ring and
  one TRB per physical endpoint. Physical DMA addresses refer only to these
  owned buffers. No user address is given to the controller.
- Cache maintenance, synchronous endpoint commands with timeouts, bounded event
  processing, packet length validation and bulk IN zero-packet termination.
- A native `en0` Ethernet ifnet uses XNU's Ethernet framing, DLIL, mbufs and IP
  stack. It has MTU 1500, no checksum offload, and a bounded 16-packet TX queue.
- One kernel thread polls the event ring, sleeping on the native deadline API
  between polls. This revision does not claim a DWC3 IRQ implementation.
- PID1 attempts to configure `en0` as `192.168.53.2/30`. The intended host address
  is `192.168.53.1/30`; host configuration and bidirectional ping remain tests.

Development USB identity is `1209:a605`; this is not a claimed VID/PID allocation.
The descriptor MAC for the host is `02:53:4d:41:36:01`, and XNU `en0` uses
`02:53:4d:41:36:02`. They are locally administered development addresses, not
derived from a device serial, CID or unique identifier. No USB serial string is
advertised.

`kern.a6plte_usb` and the PID1 heartbeat report `0` for offline, `1` for EP0
running, or `3` for the active Ethernet data alternate setting. `3` alone does
not establish packet delivery or working IP. Malformed events, command errors
and timeouts stop USB without rebooting the phone. DMA storage remains owned
by the kernel even if the controller cannot stop; it is never freed/reused by
an unrelated allocator after an uncertain hardware failure.

## Validation status

All three jobs passed in [Actions 39251328230](https://github.com/omauser119/a6plte-xnu/actions/runs/39251328230),
source `0a5b7de`. Physical USB enumeration and network delivery are pending.

The first hardware failure was a zero transfer-resource index for initial EP0
SETUP before RUN_STOP on DWC3 2.70a. Accepting that deferred allocation reached
the connection event and the first GET_DESCRIPTOR SETUP in the owned DMA ring.
The next boot stopped in a VM page-hash assertion while loading PID1; the host
reported descriptor/address timeouts and did not bind an Ethernet interface.
The diagnostic revision preserves full early-panic text and cleans the CPU
caches at the panic stop so lk2nd can inspect the fault state after a warm reset.
Inspection found repeated RGB888 glyph rows in the page-hash buckets directly
above the framebuffer's virtual allocation. The board console previously let
the cursor advance beyond its last row while scrolling with interrupts enabled;
the new USB thread could print during that interval. The fix serializes each
console character on the single boot CPU, keeps the cursor in range during
scrolling, and clips every pixel store. Tall displays scroll eight rows at a
time to reduce expensive framebuffer reads. Hardware validation is pending.

Host ASan/UBSan tests exercise HS/FS/other-speed descriptors, setup field bounds,
100,000 randomized requests, EP0 and bulk sequences, terminating zero packets,
endpoint halt/clear, reset, event-ring wrap, DMA/cache operation spans, and
command errors/timeouts against an injected MMIO model. Native source checks
compile against actual generated XNU headers. Those checks do not establish
physical enumeration, DMA correctness or networking on SM-A605FN.

Next hardware checks are Linux enumeration and `cdc_ether` binding, repeat
disconnect/reset, native `en0` configuration, ARP and bidirectional ping. SSH and
Bash still require the Apple OSS userspace/runtime work recorded in ROADMAP.md.
