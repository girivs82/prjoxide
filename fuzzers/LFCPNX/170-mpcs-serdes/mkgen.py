#!/usr/bin/env python3
"""variants file (name|json) -> per-variant .cfg files and one radiantc tcl running ipgen -cfg on each"""
import json, sys
vf, tcl = sys.argv[1], sys.argv[2]
L = ["set ip /opt/lscc/radiant/2026.1/ip/lifcl/mpcs"]
for line in open(vf):
    line = line.strip()
    if not line: continue
    n, cfg = line.split("|", 1)
    json.loads(cfg)
    open("%s.cfg" % n, "w").write(cfg)
    L.append('file mkdir /work/serdes/fuzz/%s' % n)
    L.append('if {[catch {exec ipgen -o /work/serdes/fuzz/%s -ip $ip -name %s -cfg /work/serdes/fuzz/%s.cfg -a LFCPNX -p LFCPNX-100 -t LFG672 -sp 7_High-Performance_1.0V -op COM} msg]} {puts "GENERR %s"}' % (n, n, n, n))
open(tcl, "w").write("\n".join(L) + "\n")
