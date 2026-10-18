#!/usr/bin/env bash
# Build real XNU platform translation units on Linux, without linking a kernel.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export SDK=${SDK:-$HOME/.local/share/theos/sdks/iPhoneOS16.5.sdk}
cd "$ROOT"
./scripts/build-host-tools.sh
./scripts/build-mig.sh
./scripts/configure-xnu-linux.sh
mkdir -p build/kernel-headers/{san,mach,CoreEntitlements} artifacts
cp -R reference/platform-headers/EXTERNAL_HEADERS/CoreEntitlements/V2 build/kernel-headers/CoreEntitlements/
cp -R reference/platform-headers/EXTERNAL_HEADERS/TrustCache build/kernel-headers/
ln -sfn "$ROOT/xnu/osfmk/libsa/string.h" build/kernel-headers/string.h
ln -sfn "$ROOT/xnu/osfmk/libsa/types.h" build/kernel-headers/types.h
ln -sfn "$ROOT/xnu/osfmk/libsa/stdlib.h" build/kernel-headers/stdlib.h
for header in xnu/san/memory/*.h xnu/san/coverage/*.h; do
    ln -sfn "$ROOT/$header" "build/kernel-headers/san/$(basename "$header")"
done
for header in Availability.h AvailabilityInternal.h AvailabilityMacros.h AvailabilityVersions.h; do
    ln -sfn "$SDK/usr/include/$header" "build/kernel-headers/$header"
done
mkdir -p build/cxx-support
for header in errno.h stdio.h stdlib.h; do
    ln -sfn "$ROOT/xnu/libkern/libcxx_support/$header" "build/cxx-support/$header"
done
mkdir -p build/kernel-headers/skywalk
for header in xnu/bsd/skywalk/*/os_*.h; do
    ln -sfn "$ROOT/$header" "build/kernel-headers/skywalk/$(basename "$header")"
done
./scripts/generate-version.sh
python3 scripts/generate-mach-interfaces.py
python3 scripts/generate-bsd.py
python3 scripts/probe-platform.py osfmk/arm64/genassym.c
python3 - <<'PY'
from pathlib import Path
import re
s=Path('artifacts/xnu-genassym.s').read_text()
values=re.findall(r'DEFINITION__define__(\w+):\s*\.ascii\s+"[#\$]?(-?\d+)"',s)
if not values:
    raise SystemExit('No assembly offsets generated')
Path('build/xnu/osfmk/assym.s').write_text(''.join(f'#define {k} {v}\n#define {k}_NUM {v}\n' for k,v in values))
print(f'Generated {len(values)} assembly offsets')
PY
for source in \
    osfmk/arm64/start.s osfmk/arm64/locore.s osfmk/arm/rtclock.c osfmk/arm/arm_init.c osfmk/arm64/arm_vm_init.c \
    osfmk/arm64/cpu.c osfmk/arm64/machine_routines.c osfmk/arm64/sleh.c \
    osfmk/arm64/a6plte_interrupts.c osfmk/arm64/pcb.c \
    osfmk/arm/machine_routines_common.c osfmk/arm/commpage/commpage_asm.s pexpert/arm/pe_serial.c \
    pexpert/arm/pe_identify_machine.c pexpert/arm/pe_kprintf.c \
    pexpert/arm/a6plte/early.c pexpert/arm/a6plte/fb.c pexpert/arm/a6plte/gic.c; do
    echo "Compiling $source"
    python3 scripts/probe-platform.py "$source" > "artifacts/check-$(basename "$source").log" 2>&1 || {
        cat "artifacts/check-$(basename "$source").log"
        exit 1
    }
done
echo 'Platform compilation passed. These objects are NOT a linked or bootable XNU kernel.'
