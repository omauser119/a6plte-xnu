#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/artifacts"
LLD=${LLD:-$(command -v ld.lld || true)}
LLD=${LLD:-$HOME/a6plte-uefi/toolchain/ld.lld}
mkdir -p "$OUT"
flags=(--target=aarch64-none-elf -mcpu=cortex-a53 -mgeneral-regs-only -ffreestanding -fno-builtin -fno-stack-protector -fno-pic -O2 -g -Wall -Wextra -Werror)
for src in console/fb.c shim/fdt.c shim/loader.c shim/main.c shim/start.S; do
    clang "${flags[@]}" -c "$ROOT/$src" -o "$OUT/$(basename "${src%.*}").o"
done
"$LLD" -T "$ROOT/shim/link.ld" -o "$OUT/fb-smoke.elf" "$OUT/start.o" "$OUT/main.o" "$OUT/fdt.o" "$OUT/fb.o" "$OUT/loader.o"
llvm-objcopy -O binary "$OUT/fb-smoke.elf" "$OUT/fb-smoke.Image"
# The older installed lk2nd requires the exact /memory node name.
sed 's/memory@10000000 {/memory {/' "$ROOT/reference/a6plte-r4.dts" > "$OUT/boot.dts"
dtc -q -I dts -O dtb -o "$OUT/boot.dtb" "$OUT/boot.dts" 2>"$OUT/dtc.log"
python3 "$ROOT/scripts/append-dtb.py" --fd "$OUT/fb-smoke.Image" --dtb "$OUT/boot.dtb" --output "$OUT/fb-smoke.kernel"
bootimg=(mkbootimg)
if [[ -n ${MKBOOTIMG_PYTHON:-} ]]; then
    bootimg=("$MKBOOTIMG_PYTHON" "$(command -v mkbootimg)")
fi
"${bootimg[@]}" --kernel "$OUT/fb-smoke.kernel" --output "$OUT/fb-smoke-boot.img" --pagesize 2048 --base 0x80000000 --kernel_offset 0x00080000 --tags_offset 0x01e00000 --board a6plte --cmdline 'a6plte-xnu lk2nd.pass-simplefb=autorefresh' --header_version 0
