#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$ROOT/artifacts"
sed 's/reg = <0x00 0x10000000 0x00 0x00>;/reg = <0x00 0x80000000 0x00 0xc0000000>;/' "$ROOT/reference/a6plte-r4.dts" > "$ROOT/artifacts/test.dts"
dtc -q -I dts -O dtb -o "$ROOT/artifacts/test.dtb" "$ROOT/artifacts/test.dts" 2>/dev/null
clang -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_console.c" "$ROOT/console/fb.c" "$ROOT/shim/fdt.c" -o "$ROOT/artifacts/test-console"
"$ROOT/artifacts/test-console" "$ROOT/artifacts/test.dtb"
python3 "$ROOT/tests/test_pack.py"
clang -DA6PLTE=1 -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_xnu_early.c" "$ROOT/xnu/pexpert/arm/a6plte/early.c" "$ROOT/xnu/pexpert/arm/a6plte/fb.c" -o "$ROOT/artifacts/test-xnu-early"
"$ROOT/artifacts/test-xnu-early"
for source in early fb; do
    clang --target=arm64-apple-darwin -mcpu=cortex-a53 -ffreestanding -fno-builtin -fno-stack-protector -mgeneral-regs-only -O2 -DA6PLTE=1 -Wall -Wextra -Werror -c "$ROOT/xnu/pexpert/arm/a6plte/$source.c" -o "$ROOT/artifacts/xnu-$source.macho.o"
done
clang -DA6PLTE=1 -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_gic.c" "$ROOT/xnu/pexpert/arm/a6plte/gic.c" -o "$ROOT/artifacts/test-gic"
"$ROOT/artifacts/test-gic"
