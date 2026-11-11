#!/usr/bin/env bash
# Build the empty LFCPNX-100 design through sv2udb -> bitgen and unpack it.
# Proves: tool paths, licence checkout (via MAC), RBK mode, prjoxide reading the output.
set -euo pipefail
cd "${PRJOXIDE:-/work/prjoxide}"
# prjoxide's environment.sh expands $PYTHONPATH unguarded, so it can't run under nounset.
set +u; source environment.sh; set -u
mkdir -p /work/smoke && cp fuzzers/LFCPNX/shared/empty_100.v /work/smoke/empty.v
cd /work/smoke
time STRUCT_VER=1 RBK_MODE=1 FORCE_REBUILD=1 bash /work/prjoxide/radiant.sh LFCPNX-100 empty.v
ls -la empty.bit
prjoxide unpack empty.bit empty.fasm && wc -l empty.fasm && echo "SMOKE TEST OK"
