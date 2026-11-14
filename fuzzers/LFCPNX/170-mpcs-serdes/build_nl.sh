#!/bin/bash
# build one netlist variant (decode-only); keep only the bitstream
n=$1; cd /work/serdes/attr/$n/b || exit 1
ulimit -c 0
FORCE_REBUILD=1 bash /work/prjoxide/radiant.sh LFCPNX-100 $n > build.log 2>&1
if [ -f $n.bit ]; then rm -rf $n.tmp; echo "$n OK"; else echo "$n FAIL $(grep -m1 '^ERROR' build.log | cut -c1-250)"; rm -rf $n.tmp/*.udb; fi
