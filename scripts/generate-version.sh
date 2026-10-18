#!/usr/bin/env bash
# Stamp a local development version using XNU's own generator.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export SRCROOT="$ROOT/xnu"
export OBJROOT="$ROOT/build/xnu"
export CURRENT_KERNEL_CONFIG_LC=development
# No matching KDK is installed. Do not impersonate an Apple release version.
A6_DARWIN_VERSION=${RC_DARWIN_KERNEL_VERSION:-1.0.0d1}
mkdir -p "$ROOT/build/kernel-headers/libkern" "$OBJROOT"
printf '%s\n' "$A6_DARWIN_VERSION" > "$OBJROOT/xnuVersion"
cp "$SRCROOT/libkern/libkern/version.h.template" "$ROOT/build/kernel-headers/libkern/version.h.pending"
perl "$SRCROOT/config/newvers.pl" "$ROOT/build/kernel-headers/libkern/version.h.pending"
mv "$ROOT/build/kernel-headers/libkern/version.h.pending" "$ROOT/build/kernel-headers/libkern/version.h"
