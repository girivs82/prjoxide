#!/usr/bin/env python3
"""Bit-pattern variants of the base netlist: every binary PCSX1 attribute bit i gets code i+1
(11 bits); variant pj sets bit i to bit j of its code, variant qj to the inverse."""
import json, re
base = open("base_netlist.v").read()
DP = re.compile(r'(defparam \\PCSX1_inst\.u_PCSX1 \.([A-Z0-9_]+) = )"0b([01]+)";')
import os
EXCL = set(open("exclude.txt").read().split()) if os.path.exists("exclude.txt") else set()
attrs = [(m.group(2), len(m.group(3)), m.group(3)) for m in DP.finditer(base) if m.group(2) not in EXCL]
bits = []                     # global index -> (attr, bit position, LSB = 0)
for a, w, v in attrs:
    for b in range(w):
        bits.append((a, b))
json.dump(dict(attrs=attrs, bits=bits, excluded=sorted(EXCL)), open("pat_index.json", "w"))
NB = 11
assert len(bits) + 1 < (1 << NB)
code = {bits[i]: i + 1 for i in range(len(bits))}
def variant(j, inv):
    def rep(m):
        a, v = m.group(2), m.group(3)
        if a in EXCL:
            return m.group(0)
        w = len(v)
        val = "".join(str(((code[(a, w - 1 - k)] >> j) & 1) ^ inv) for k in range(w))  # MSB first
        return '%s"0b%s";' % (m.group(1), val)
    return DP.sub(rep, base)
import os
names = []
for j in range(NB):
    for inv, tag in ((0, "p"), (1, "q")):
        n = "%s%02d" % (tag, j)
        os.makedirs("%s/b" % n, exist_ok=True)
        open("%s/b/%s.v" % (n, n), "w").write(variant(j, inv))
        open("%s/b/%s.pdc" % (n, n), "w").write(open("nl0/b/nl0.pdc").read())
        names.append(n)
open("list_pat.txt", "w").write("\n".join(names) + "\n")
print(len(attrs), "binary attrs,", len(bits), "bits,", len(names), "variants")
