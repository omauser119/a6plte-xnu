#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC="$ROOT/reference/bootstrap_cmds/migcom.tproj"
OUT="$ROOT/build/host-mig"
SDK=${SDK:-$HOME/.local/share/theos/sdks/iPhoneOS16.5.sdk}
mkdir -p "$OUT/mach_shim/sys"
cd "$OUT"
if [[ $(uname -s) != Darwin ]]; then
for dir in mach arm machine architecture _types libkern; do
    cp -R "$SDK/usr/include/$dir" mach_shim/
done
for dir in _types _pthread; do cp -R "$SDK/usr/include/sys/$dir" mach_shim/sys/; done
for file in _types.h _endian.h appleapiopts.h; do cp "$SDK/usr/include/sys/$file" mach_shim/sys/; done
for file in Availability.h AvailabilityInternal.h AvailabilityVersions.h AvailabilityMacros.h; do cp "$SDK/usr/include/$file" mach_shim/; done
sed -i -e '/typedef long long *__int64_t;/d' -e '/typedef unsigned long long *__uint64_t;/d' -e '/^typedef union {/,/} __mbstate_t;/d' mach_shim/arm/_types.h
fi
bison -d -b y "$SRC/parser.y"
flex -o lexxer.yy.c "$SRC/lexxer.l"
host_flags=()
if [[ $(uname -s) != Darwin ]]; then
    host_flags=(-D__kernel_ptr_semantics= -D__private_extern__= -D__LITTLE_ENDIAN__ -D__arm64__=1 -Imach_shim -include sys/types.h -include bits/types/__mbstate_t.h)
fi
cc -std=gnu11 "${host_flags[@]}" -DMIG_VERSION='"a6plte-linux"' -I"$SRC" -I. "$SRC/error.c" "$SRC/global.c" "$SRC/header.c" "$SRC/mig.c" "$SRC/routine.c" "$SRC/server.c" "$SRC/statement.c" "$SRC/string.c" "$SRC/type.c" "$SRC/user.c" "$SRC/utils.c" y.tab.c lexxer.yy.c -o migcom
file migcom
