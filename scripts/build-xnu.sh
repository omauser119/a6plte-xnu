#!/usr/bin/env bash
# Build the complete configured A6PLTE kernel with Apple's compiler and IIG.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
if ! command -v xcrun >/dev/null; then
    echo 'Full XNU compilation requires Apple clang and IIG; use the macOS Actions job.' >&2
    exit 2
fi
export SDK=${SDK:-$(xcrun --sdk macosx --show-sdk-path)}
./scripts/check-platform.sh
python3 scripts/generate-iokit.py
failed=0
for component in osfmk mig pexpert bsd libkern iokit libsa security san; do
    python3 scripts/check-component.py "$component" || failed=1
done
if [ "$failed" != 0 ]; then exit 1; fi
python3 scripts/link-xnu.py
