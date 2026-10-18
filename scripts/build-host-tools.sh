#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC="$ROOT/xnu/SETUP/config"
OUT="$ROOT/build/host-config"
mkdir -p "$OUT"
cd "$OUT"
bison -d -o parser.c "$SRC/parser.y"
flex --header-file=lexer.yy.h -o lexer.yy.c "$SRC/lexer.l"
cc -std=gnu11 -DYY_NO_INPUT -I"$SRC" -I. "$SRC/externs.c" "$SRC/main.c" "$SRC/mkheaders.c" "$SRC/mkioconf.c" "$SRC/mkmakefile.c" "$SRC/openp.c" "$SRC/searchp.c" parser.c lexer.yy.c -o config
file config

cc -std=gnu89 -O2 "$ROOT/reference/PureDarwin/tools/unifdef/unifdef.c" -o "$OUT/unifdef"
