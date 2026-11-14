#!/usr/bin/env python3
"""Pattern variants for the two-valued string attributes of PCSX1: toggle t (baseline value vs the
other known value) gets code t+1 (NB bits, top bit 0); ep<j> sets toggle t to bit j of its code,
eq<j> to the inverse; ez0/ez1 set every toggle to baseline/alternative."""
import json, os, re
base = open("base_netlist.v").read()
legal = json.load(open("enum_legal.json"))
EXCL = set(open("exclude_enum.txt").read().split()) if os.path.exists("exclude_enum.txt") else set()
SKIP = {"PROTOCOL", "DATARATE", "LANE_ID", "GRP_NAME"}
DP = re.compile(r'(defparam \\PCSX1_inst\.u_PCSX1 \.([A-Z0-9_]+) = )"(.*?)";')
tog = []
for m in DP.finditer(base):
    a, v = m.group(2), m.group(3)
    if v.startswith("0b") or a in SKIP or a in EXCL:
        continue
    vals = legal.get(a)
    if not vals or len(vals) != 2 or v not in vals:
        continue
    alt = [x for x in vals if x != v][0]
    tog.append((a, v, alt))
NB = 9
assert len(tog) + 1 < (1 << (NB - 1))
code = {t[0]: i + 1 for i, t in enumerate(tog)}
alt = {a: (v, al) for a, v, al in tog}
def variant(sel):
    def rep(m):
        a = m.group(2)
        if a not in alt: return m.group(0)
        return '%s"%s";' % (m.group(1), alt[a][sel(a)])
    return DP.sub(rep, base)
names = []
for j in range(NB):
    for inv, tag in ((0, "ep"), (1, "eq")):
        n = "%s%02d" % (tag, j)
        os.makedirs("%s/b" % n, exist_ok=True)
        open("%s/b/%s.v" % (n, n), "w").write(variant(lambda a, j=j, inv=inv: ((code[a] >> j) & 1) ^ inv))
        names.append(n)
for n, val in (("ez0", 0), ("ez1", 1)):
    os.makedirs("%s/b" % n, exist_ok=True)
    open("%s/b/%s.v" % (n, n), "w").write(variant(lambda a, val=val: val))
    names.append(n)
for n in names:
    open("%s/b/%s.pdc" % (n, n), "w").write(open("nl0/b/nl0.pdc").read())
json.dump(dict(toggles=tog, NB=NB, excluded=sorted(EXCL)), open("enum_index.json", "w"), indent=0)
open("list_enum.txt", "w").write("\n".join(names) + "\n")
print(len(tog), "toggles,", len(names), "variants")
