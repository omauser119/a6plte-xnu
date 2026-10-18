#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
if ! command -v xcrun >/dev/null || ! command -v xcodebuild >/dev/null; then
    echo 'Stock XNU build expects Darwin/Xcode tools. Full Linux kernel linking and dependencies are not complete. Use scripts/check-platform.sh for real platform object compilation.' >&2
    echo 'The A6PLTE platform port is incomplete; installing the SDK alone does not finish it.' >&2
    exit 2
fi
make -C "$ROOT/xnu" ARCH_CONFIGS=ARM64 MACHINE_CONFIGS=A6PLTE KERNEL_CONFIGS=DEVELOPMENT BTI_BUILD=0 "$@"
