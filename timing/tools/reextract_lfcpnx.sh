#!/bin/bash
# Re-run extract_route_cram.py on archived LFCPNX timing fuzzer designs (work/design_N.fasm,
# .twr, .tmp/par.pad and output/LFCPNX/<NAME>_N_9.vo/.sdf), e.g. after a database or extractor
# change. Usage (from timing/, in the container): tools/reextract_lfcpnx.sh <fuzzer dir>...
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH=../util/common:../util/fuzz:util:${PYTHONPATH}
for d in "$@"; do
    name=$(sed -n 's/^NAME=//p' "$d/Makefile")
    for f in "$d"/work/design_*.fasm; do
        n=$(basename "$f" .fasm); n=${n#design_}
        o=output/LFCPNX/${name}_${n}
        [ -e "${o}_9.vo" ] || continue
        python3 util/extract_route_cram.py "$f" "${o}_9.vo" "${o}_9.sdf" "$d/work/design_${n}.tmp/par.pad" \
            "${o}_route.pickle" "$d/work/design_${n}.twr" > "$d/work/route_${n}.log" 2>&1 \
            && echo "$name $n: $(tail -2 "$d/work/route_${n}.log" | head -1)" || echo "$name $n: FAILED"
    done
done
