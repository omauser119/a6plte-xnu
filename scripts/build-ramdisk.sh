#!/usr/bin/env bash
# Build the first HFS+ root and a freestanding native Darwin PID1 probe on macOS.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if ! command -v hdiutil >/dev/null; then echo 'HFS+ image creation requires the macOS Actions job.' >&2; exit 2; fi
SDK=${SDK:-$(xcrun --sdk macosx --show-sdk-path)}
A6_SDK_VERSION=$(xcrun --sdk macosx --show-sdk-version)
STAGE="$ROOT/build/ramdisk-root"
mkdir -p "$STAGE"/{sbin,etc,dev,tmp,usr/share/licenses} artifacts
sudo chown -R "$(id -u):$(id -g)" "$STAGE"
clang --target=arm64-apple-macos11 -mcpu=cortex-a53 -ffreestanding -fno-builtin -fno-stack-protector -mgeneral-regs-only -mstrict-align -O2 -D__APPLE_API_PRIVATE=1 -I"$ROOT/build/kernel-headers" -isysroot "$SDK" -Wall -Wextra -Werror -c ramdisk/init.c -o artifacts/a6-init.o
xcrun ld -arch arm64 -static -no_pie -e _start -platform_version macos 11.0 "$A6_SDK_VERSION" -adhoc_codesign artifacts/a6-init.o -o "$STAGE/sbin/a6-init"
python3 scripts/check-init.py "$STAGE/sbin/a6-init"
cat > "$STAGE/etc/a6plte-release" <<'EOF'
A6PLTE / SM-A605FN
Apple OSS XNU 12377.121.6 / Darwin 25.5.0
Root: native Apple HFS+ driver, RAMDisk /dev/md0
Initial PID1 probe; Bash and SSH are not installed yet.
EOF
cp reference/hfs/APPLE_LICENSE "$STAGE/usr/share/licenses/hfs-APSL.txt"
cp licenses/legacy-aes.txt "$STAGE/usr/share/licenses/legacy-aes.txt"
touch "$STAGE/.metadata_never_index"
chmod 755 "$STAGE" "$STAGE/sbin" "$STAGE/etc" "$STAGE/dev" "$STAGE/usr" "$STAGE/usr/share" "$STAGE/usr/share/licenses"
chmod 1777 "$STAGE/tmp"
chmod 755 "$STAGE/sbin/a6-init"
chmod 644 "$STAGE/etc/a6plte-release" "$STAGE/usr/share/licenses/"*.txt
sudo chown -R 0:0 "$STAGE"
hdiutil create -ov -size 32m -layout NONE -fs HFS+ -volname A6PLTE_ROOT -format UDRW -srcfolder "$STAGE" "$ROOT/artifacts/ramdisk.dmg"
python3 scripts/extract-hfs.py artifacts/ramdisk.dmg artifacts/ramdisk.hfs
cp "$STAGE/sbin/a6-init" artifacts/a6-init
