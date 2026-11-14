#!/usr/bin/env python3
"""Multi-valued enums against the full packed baseline (lane0_nl0_dec.fasm, which reproduces every
Radiant-written byte): for each value build, the bits where Radiant's written bytes differ from the
baseline model (unwritten bytes are at their default = baseline)."""
import json, re
from collections import defaultdict
var = json.load(open("multi_index.json"))
def ip(f):
    d = {}
    for l in open(f):
        if l.startswith("IP_UNKNOWN.0x0E42"): d[int(l[13:21], 16) & 0xFFFF] = int(l.split("8'h")[1][:2], 16)
    return d
B = ip("lane0_nl0_dec.fasm")
bv = {m.group(1): m.group(2) for m in re.finditer(r'defparam \\PCSX1_inst\.u_PCSX1 \.([A-Z0-9_]+) = "(.*?)";', open("base_netlist.v").read())}
byattr = defaultdict(dict)
for n, ch in var.items():
    if n.startswith("bond_b"): continue
    (a, v), = ch.items()
    R = ip("%s.fasm" % n)
    diff = {}
    for o, val in R.items():
        x = val ^ B.get(o, 0)
        for b in range(8):
            if (x >> b) & 1: diff[(o, b)] = (val >> b) & 1
    byattr[a][v] = diff
out = {}
for a, vals in byattr.items():
    bits = sorted(set().union(*[set(d) for d in vals.values()]))
    if not bits: continue
    opts = {bv[a]: [(o, b, (B.get(o, 0) >> b) & 1) for o, b in bits]}
    for v, d in vals.items():
        opts[v] = [(o, b, d.get((o, b), (B.get(o, 0) >> b) & 1)) for o, b in bits]
    out[a] = opts
json.dump(out, open("multi_solution.json", "w"), indent=0)
print(len(out), "multi enums:", {a: len(next(iter(o.values()))) for a, o in out.items()})
