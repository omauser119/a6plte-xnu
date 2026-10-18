#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CROSS=${TOOLCHAIN_PREFIX:-arm-none-eabi-}
mkdir -p "$ROOT/artifacts"
make -C "$ROOT/lk2nd" TOOLCHAIN_PREFIX="$CROSS" -j4 lk2nd-msm8953-a6plte-xnu
BUILD="$ROOT/lk2nd/build-lk2nd-msm8953-a6plte-xnu"
for macro in WITH_DEBUG_UART WITH_DEBUG_DCC WITH_DEBUG_JTAG; do
    rg -q "^#define $macro 0$" "$BUILD/config.h"
done
if "${CROSS}nm" "$BUILD/lk" | rg ' [Tt] (uart_dm_init|uart_putc|uart_getc)$'; then
    echo 'Unexpected UART implementation in linked image' >&2; exit 1
fi
cp "$BUILD/lk2nd.img" "$ROOT/artifacts/lk2nd-a6plte-xnu.img"
