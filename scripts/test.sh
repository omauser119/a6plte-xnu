#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$ROOT/artifacts"
sed 's/reg = <0x00 0x10000000 0x00 0x00>;/reg = <0x00 0x80000000 0x00 0xc0000000>;/' "$ROOT/reference/a6plte-r4.dts" > "$ROOT/artifacts/test.dts"
python3 - "$ROOT/artifacts/test.dts" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
seed=' '.join(f'{i:02x}' for i in range(256))
p.write_text(p.read_text().replace('chosen {', 'chosen {\n rng-seed = ['+seed+'];', 1))
PY
dtc -q -I dts -O dtb -o "$ROOT/artifacts/test.dtb" "$ROOT/artifacts/test.dts" 2>/dev/null
clang -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_console.c" "$ROOT/console/fb.c" "$ROOT/shim/fdt.c" -o "$ROOT/artifacts/test-console"
"$ROOT/artifacts/test-console" "$ROOT/artifacts/test.dtb"
clang -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_apple_dt.c" "$ROOT/shim/apple_dt.c" -o "$ROOT/artifacts/test-apple-dt"
"$ROOT/artifacts/test-apple-dt"
clang -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_package.c" "$ROOT/shim/package.c" -o "$ROOT/artifacts/test-package"
"$ROOT/artifacts/test-package"
python3 "$ROOT/tests/test_pack.py"
python3 "$ROOT/tests/test_hfs_image.py"
python3 "$ROOT/tests/test_hfs_finderinfo.py"
python3 "$ROOT/tests/test_dyld_root_policy.py"
python3 "$ROOT/tests/test_iokit_catalogue.py"
python3 "$ROOT/tests/test_amfi_queries.py"
python3 "$ROOT/tests/test_amfi_signature.py"
python3 "$ROOT/tests/test_platform_signature.py"
python3 "$ROOT/tests/test_codesign_identity.py"
python3 "$ROOT/tests/test_codesign_16k.py"
clang -std=gnu17 -Wall -Wextra -Werror -Wno-deprecated-declarations -fsanitize=address,undefined -g -I"$ROOT/xnu/bsd/dev/a6plte" "$ROOT/tests/test_cs_cache.c" "$ROOT/xnu/bsd/dev/a6plte/cs_cache.c" -lcrypto -o "$ROOT/artifacts/test-cs-cache"
"$ROOT/artifacts/test-cs-cache"
python3 "$ROOT/tests/test_cs_cache_vfs.py"
python3 "$ROOT/tests/test_aks_state.py"
clang -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_usb.c" "$ROOT/xnu/bsd/dev/a6plte/usb_ecm.c" "$ROOT/xnu/bsd/dev/a6plte/usb_dwc3.c" -o "$ROOT/artifacts/test-usb"
"$ROOT/artifacts/test-usb"
for unit in storage sdhci; do
    sources=("$ROOT/xnu/bsd/dev/a6plte/sdhci.c")
    if [[ $unit == storage ]]; then sources=("$ROOT/xnu/bsd/dev/a6plte/gpt.c"); fi
    clang -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_$unit.c" "${sources[@]}" -o "$ROOT/artifacts/test-$unit"
    "$ROOT/artifacts/test-$unit"
done
python3 "$ROOT/tests/test_userdata_strategy.py"
clang -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_hfs_volume.c" "$ROOT/xnu/bsd/dev/a6plte/gpt.c" "$ROOT/xnu/bsd/dev/a6plte/hfs_volume.c" -o "$ROOT/artifacts/test-hfs-volume"
"$ROOT/artifacts/test-hfs-volume"
python3 "$ROOT/tests/test_bootimg.py"
python3 "$ROOT/tests/test_crc32.py"
clang -pthread -I"$ROOT/xnu" -DA6PLTE=1 -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_xnu_early.c" "$ROOT/xnu/pexpert/arm/a6plte/early.c" "$ROOT/xnu/pexpert/arm/a6plte/fb.c" -o "$ROOT/artifacts/test-xnu-early"
"$ROOT/artifacts/test-xnu-early"
clang -DA6PLTE=1 -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_xnu_fb_scroll.c" "$ROOT/xnu/pexpert/arm/a6plte/fb.c" -o "$ROOT/artifacts/test-xnu-fb-scroll"
"$ROOT/artifacts/test-xnu-fb-scroll"
for source in early fb; do
    clang -I"$ROOT/xnu" --target=arm64-apple-darwin -mcpu=cortex-a53 -ffreestanding -fno-builtin -fno-stack-protector -mgeneral-regs-only -mstrict-align -fno-jump-tables -O2 -DA6PLTE=1 -Wall -Wextra -Werror -c "$ROOT/xnu/pexpert/arm/a6plte/$source.c" -o "$ROOT/artifacts/xnu-$source.macho.o"
done
clang -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_graphics_layout.c" "$ROOT/xnu/iokit/Kernel/arm/A6GraphicsLayout.c" -o "$ROOT/artifacts/test-graphics-layout"
"$ROOT/artifacts/test-graphics-layout"
clang -DA6PLTE=1 -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_gic.c" "$ROOT/xnu/pexpert/arm/a6plte/gic.c" -o "$ROOT/artifacts/test-gic"
"$ROOT/artifacts/test-gic"
clang -DA6PLTE=1 -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_kmem_rng.c" "$ROOT/xnu/libkern/crypto/a6plte_kmem_rng.c" -o "$ROOT/artifacts/test-kmem-rng"
"$ROOT/artifacts/test-kmem-rng"
clang -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_aes.c" "$ROOT"/xnu/libkern/crypto/a6plte_aes/gen/*.c -o "$ROOT/artifacts/test-aes"
"$ROOT/artifacts/test-aes"
clang -DKERNEL=1 -DA6PLTE=1 -I"$ROOT/xnu/libkern" -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_md5.c" "$ROOT/xnu/libkern/crypto/a6plte_md5.c" -o "$ROOT/artifacts/test-md5"
"$ROOT/artifacts/test-md5"
clang --target=arm64-apple-darwin -mcpu=cortex-a53 -ffreestanding -fno-builtin -mgeneral-regs-only -mstrict-align -fno-jump-tables -O2 -DA6PLTE=1 -Wall -Wextra -Werror -c "$ROOT/xnu/libkern/crypto/a6plte_kmem_rng.c" -o "$ROOT/artifacts/xnu-kmem-rng.macho.o"

python3 "$ROOT/tests/test_sha1.py"
python3 "$ROOT/tests/test_sha512.py"

clang -std=c17 -fsanitize=address,undefined -g -Wall -Wextra -Werror "$ROOT/tests/test_input.c" "$ROOT/xnu/iokit/Kernel/arm/A6Input.c" "$ROOT/xnu/iokit/Kernel/arm/A6HIDWire.c" -o "$ROOT/artifacts/test-input"
"$ROOT/artifacts/test-input"

python3 "$ROOT/tests/test_early_relocations.py" "$ROOT/artifacts/xnu-early.macho.o" "$ROOT/artifacts/xnu-fb.macho.o"
