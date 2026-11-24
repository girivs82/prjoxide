#!/bin/bash
# collect.sh: per build, the PLL's REFMUX selection (JREFCK <- JREFCLKn) and whether par put the pad
# on a primary clock. Needs the builds' par.bit decoded with prjoxide (PRJOXIDE, DB).
for v in *_*.v; do n=${v%.v}; pll=${n%%_*}; pin=${n#*_}
  [ -e $n.tmp/par.bit ] || { echo "$pll $pin FAILED"; continue; }
  [ -e $n.fasm ] || $PRJOXIDE unpack --db $DB $n.tmp/par.bit $n.fasm >/dev/null 2>&1
  sel=$(grep -o "GPLL_$pll\.PIP\.[A-Z0-9]*__JREFCK_REFMUX_CORE_REFMUX\.[A-Z0-9]*__J[A-Z0-9]*" $n.fasm | sed 's/.*__J//')
  echo "$pll $pin $sel primary=$(grep -c "PRIMARY \"refin" $n.tmp/par.par)"
done
