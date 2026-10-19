#!/usr/bin/env bash
# Stamp the pinned source's Darwin version using XNU's own generator.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export SRCROOT="$ROOT/xnu"
export OBJROOT="$ROOT/build/xnu"
export CURRENT_KERNEL_CONFIG_LC=development
# xnu-8796.141.3 belongs to Darwin 22.6.0. Keep the custom target explicit.
A6_DARWIN_VERSION=${RC_DARWIN_KERNEL_VERSION:-22.6.0}
export KERNEL_BUILD_OBJROOT=${KERNEL_BUILD_OBJROOT:-xnu-8796.141.3/DEVELOPMENT_ARM64_A6PLTE}
mkdir -p "$ROOT/build/kernel-headers/libkern" "$OBJROOT"
printf '%s\n' "$A6_DARWIN_VERSION" > "$OBJROOT/xnuVersion"
cp "$SRCROOT/libkern/libkern/version.h.template" "$ROOT/build/kernel-headers/libkern/version.h.pending"
perl "$SRCROOT/config/newvers.pl" "$ROOT/build/kernel-headers/libkern/version.h.pending"
mv "$ROOT/build/kernel-headers/libkern/version.h.pending" "$ROOT/build/kernel-headers/libkern/version.h"

cp "$SRCROOT/config/version.c" "$OBJROOT/osfmk/version.c"
perl "$SRCROOT/config/newvers.pl" "$OBJROOT/osfmk/version.c"
