#!/bin/bash
# build one generated variant with the CLI flow (decode-only); keep only the bitstream and log
n=$1; cd /work/serdes/fuzz || exit 1
ulimit -c 0
python3 /work/serdes/fuzz/gen_top.py $n 2>$n/gen.err || { echo "$n GENTOP_FAIL"; exit 0; }
cd /work/serdes/fuzz/$n && mkdir -p b && cp ${n}_top.v b/$n.v && cp /work/serdes/serdes_t.pdc b/$n.pdc && cd b
FORCE_REBUILD=1 bash /work/prjoxide/radiant.sh LFCPNX-100 $n > build.log 2>&1
if [ -f $n.bit ]; then cp $n.tmp/synth.vm ../synth.vm 2>/dev/null; rm -rf $n.tmp; echo "$n OK"; else echo "$n FAIL $(grep -m1 '^ERROR' build.log | cut -c1-200)"; rm -rf $n.tmp/*.udb; fi
