#!/bin/bash
# Build probe designs of timing/fuzzers/LFCPNX/12-dqsbuf-ivref/gen_dqsbuf_ivref.py in the Radiant
# container and decode them. Usage: build.sh <name> [VAR=value ...]
#   writes work/<name>.v / .pdc (generator run on the host with the given variables), builds
#   work/<name>.bit with radiant.sh (CLI flow: LSE, map, par, bitgen -ipeval), and decodes it to
#   work/<name>.fasm with the checked-out database.
# PRJOXIDE (the host prjoxide binary) and DOCKER_HOST must be set.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
name=$1; shift
mkdir -p "$HERE/work"
env "$@" python3 "$ROOT/timing/fuzzers/LFCPNX/12-dqsbuf-ivref/gen_dqsbuf_ivref.py" "$HERE/work/$name"
"$ROOT/tools/radiant-fuzz/docker/run-radiant.sh" exec bash -c \
  "ulimit -c 0; cd /work/prjoxide/fuzzers/LFCPNX/157-dqsbuf-ivref && RADIANTDIR=/opt/lscc/radiant/2026.1 bash /work/prjoxide/radiant.sh LFCPNX-100 work/$name.v" \
  > "$HERE/work/$name.log" 2>&1 || { echo "$name: BUILD FAILED"; exit 1; }
"$PRJOXIDE" unpack --db "$ROOT/database" "$HERE/work/$name.bit" "$HERE/work/$name.fasm" > /dev/null
echo "$name: done"
