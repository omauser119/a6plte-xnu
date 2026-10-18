#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
THEOS_ROOT=${THEOS_ROOT:-$HOME/.local/share/theos}
SDK=${SDK:-$THEOS_ROOT/sdks/iPhoneOS16.5.sdk}
BIN="$THEOS_ROOT/toolchain/linux/iphone/bin"
for src in early fb; do
    "$BIN/clang" -target arm64-apple-ios16.5 -mcpu=cortex-a53 -isysroot "$SDK" -ffreestanding -fno-builtin -fno-stack-protector -mgeneral-regs-only -mstrict-align -O2 -DA6PLTE=1 -Wall -Wextra -Werror -c "$ROOT/xnu/pexpert/arm/a6plte/$src.c" -o "$ROOT/artifacts/theos-$src.o"
done
"$BIN/ld" -r -arch arm64 -o "$ROOT/artifacts/theos-console.o" "$ROOT/artifacts/theos-early.o" "$ROOT/artifacts/theos-fb.o"
if [[ -n $(llvm-nm -u "$ROOT/artifacts/theos-console.o") ]]; then
    echo 'Unexpected external dependencies in early console object' >&2; exit 1
fi
file "$ROOT/artifacts/theos-console.o"
