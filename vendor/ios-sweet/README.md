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
behavior. The original selector methods, result layout and rectangle-copy path
remain the copied implementation. Sweet HID is not imported.
