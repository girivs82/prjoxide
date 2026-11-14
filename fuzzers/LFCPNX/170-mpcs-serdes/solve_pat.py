#!/usr/bin/env python3
"""Like solve_pat.py, but a byte missing from a build (not written: equal to its default) is an
unknown observation. Each register bit is matched to the unique attribute-bit code consistent with
its observed values; the implied value of the missing observations gives the byte's default, which
must be the same in every build where the byte is missing."""
import json, re
from collections import defaultdict
idx = json.load(open("pat_index.json")); bits = [tuple(b) for b in idx["bits"]]; NB = 11
def ip(n):
    d = {}
    for l in open("%s.fasm" % n):
        if l.startswith("IP_UNKNOWN.0x0E42"):
            d[int(l[13:21], 16) - 0x0E420000] = int(l.split("8'h")[1][:2], 16)
    return d
codes = {i + 1: bits[i] for i in range(len(bits))}
obsn = [("p%02d" % j, j, 0) for j in range(NB)] + [("q%02d" % j, j, 1) for j in range(NB)] + [("z0", "Z", 0), ("z1", "Z", 1), ("nl0", "B", 0)]
base_txt = open("base_netlist.v").read()
base_attr = {m.group(1): m.group(2) for m in re.finditer(r'defparam \\PCSX1_inst\.u_PCSX1 \.([A-Z0-9_]+) = "0b([01]+)";', base_txt)}
def pred(c, j, inv):
    if j == "Z": return inv
    if j == "B":
        a, b = codes[c]; v = base_attr[a]; return int(v[len(v) - 1 - b])
    return ((c >> j) & 1) ^ inv
D = {n: ip(n) for n, _, _ in obsn}
offs = sorted(set().union(*D.values()))
mapping, const, ambig, nomatch = {}, {}, [], []
default_bits = defaultdict(dict)
for o in offs:
    for b in range(8):
        obs = [(j, inv, (D[n][o] >> b) & 1) for n, j, inv in obsn if o in D[n]]
        vals = {v for _, _, v in obs}
        cands = []
        for c in codes:
            for pol in (0, 1):
                if all(pred(c, j, inv) ^ pol == v for j, inv, v in obs):
                    cands.append((c, pol))
        if len(vals) == 1 and not cands:
            const[(o, b)] = vals.pop(); continue
        if len(cands) == 1:
            c, pol = cands[0]
            mapping.setdefault(codes[c], []).append((o, b, bool(pol)))
            for n, j, inv in obsn:
                if o not in D[n]:
                    default_bits[(o, b)].setdefault(pred(c, j, inv) ^ pol, []).append(n)
        elif not cands:
            nomatch.append((o, b, obs))
        else:
            ambig.append((o, b, len(cands)))
# a byte's default must be one value: each of its mapped bits implies one value in every missing build
bad_default = [k for k, v in default_bits.items() if len(v) > 1]
unmapped = [bt for bt in bits if bt not in mapping]
json.dump(dict(mapping={"%s[%d]" % k: v for k, v in mapping.items()},
               const={"%d.%d" % k: v for k, v in const.items()},
               defaults={"%d.%d" % k: list(v.keys())[0] for k, v in default_bits.items() if len(v) == 1},
               unmapped=["%s[%d]" % u for u in unmapped], ambig=ambig, nomatch=[(o, b) for o, b, _ in nomatch]),
          open("pat_solution.json", "w"), indent=0)
print("attr bits mapped:", len(mapping), "of", len(bits), "| reg bits const:", len(const),
      "ambiguous:", len(ambig), "nomatch:", len(nomatch), "| inconsistent defaults:", len(bad_default))
print("attr bits -> >1 reg bit:", sum(len(v) > 1 for v in mapping.values()))
from collections import Counter
print("unmapped attrs:", Counter(u[0] for u in unmapped).most_common(30))
