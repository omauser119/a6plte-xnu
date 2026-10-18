#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
TCSH=${TCSH:-$(command -v tcsh || true)}
TCSH=${TCSH:-$ROOT/toolchain/tcsh/usr/bin/tcsh}
export SRCROOT="$ROOT/xnu"
export OBJROOT="$ROOT/build/xnu"
export PATH="$ROOT/build/host-config:$PATH"
mkdir -p "$OBJROOT/SETUP/config"
cp "$ROOT/build/host-config/config" "$OBJROOT/SETUP/config/config"
for component in pexpert osfmk bsd libkern iokit libsa security san; do
    export SOURCE="$SRCROOT/$component"
    mkdir -p "$OBJROOT/$component"
    "$TCSH" -f "$SRCROOT/SETUP/config/doconf" -cpu arm64 -soc a6plte -platform MacOSX -d "$OBJROOT/$component" -m "$SRCROOT/config" -s "$SOURCE/conf" -c DEVELOPMENT
    test -s "$OBJROOT/$component/Makefile"
done

python3 - "$OBJROOT/osfmk/Makefile" <<'PY_CHECK'
from pathlib import Path
import sys
text=Path(sys.argv[1]).read_text()
for source in ('osfmk/arm/arm_init.c', 'osfmk/arm64/arm_vm_init.c',
               'osfmk/arm64/start.s', 'osfmk/arm/pmap/pmap.c',
               'osfmk/arm64/a6plte_interrupts.c'):
    if '$(SOURCE_DIR)/'+source not in text:
        raise SystemExit('Missing required A6PLTE source: '+source)
for source in ('amcc_rorgn_common.c', 'amcc_rorgn_pv_ctrr.c'):
    if source in text:
        raise SystemExit('Unexpected Apple-only source: '+source)
PY_CHECK
