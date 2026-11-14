#!/usr/bin/env python3
"""Match lane-0 register bits to the two-valued enum toggles (pattern builds ep/eq, ez0/ez1, nl0)."""
import json
idx = json.load(open("enum_index.json")); tog = idx["toggles"]; NB = idx["NB"]
def ip(n):
    d = {}
    for l in open("%s.fasm" % n):
        if l.startswith("IP_UNKNOWN.0x0E42"):
            d[int(l[13:21], 16) - 0x0E420000] = int(l.split("8'h")[1][:2], 16)
    return d
obsn = [("ep%02d" % j, j, 0) for j in range(NB)] + [("eq%02d" % j, j, 1) for j in range(NB)] + [("ez0", "Z", 0), ("ez1", "Z", 1), ("nl0", "Z", 0)]
# the binary-attribute pattern builds have every enum at its baseline value
obsn += [("p%02d" % j, "Z", 0) for j in range(11)] + [("q%02d" % j, "Z", 0) for j in range(11)] + [("z0", "Z", 0), ("z1", "Z", 0)]
pat = json.load(open("pat_solution.json"))
wordbits = {(x[0], x[1]) for v in pat["mapping"].values() for x in v}
D = {n: ip(n) for n, _, _ in obsn}
offs = sorted(set().union(*D.values()))
codes = {i + 1: tog[i][0] for i in range(len(tog))}
def pred(c, j, inv):
    return inv if j == "Z" else ((c >> j) & 1) ^ inv
res, const, ambig, nomatch = {}, [], [], []
for o in offs:
    for b in range(8):
        if (o, b) in wordbits:
            continue
        allobs = [(j, inv, ((D[n][o] >> b) & 1) if o in D[n] else None) for n, j, inv in obsn]
        cands = []
        for d in (0, 1):                       # the byte's default value for this bit (unwritten byte)
            obs = [(j, inv, d if v is None else v) for j, inv, v in allobs]
            if len({v for _, _, v in obs}) == 1:
                cands.append(("CONST", d, obs[0][2])); continue
            for c in codes:
                for pol in (0, 1):
                    if all(pred(c, j, inv) ^ pol == v for j, inv, v in obs):
                        cands.append((c, pol, d))
        nonconst = [x for x in cands if x[0] != "CONST"]
        if not nonconst:
            const.append((o, b)); continue
        if len(nonconst) == 1:
            c, pol, d = nonconst[0]
            res.setdefault(codes[c], []).append((o, b, pol))
        else:
            ambig.append((o, b, len(nonconst)))
json.dump(dict(toggles={a: res.get(a, []) for a, _, _ in tog}, ambig=ambig, nomatch=nomatch), open("enum_solution.json", "w"), indent=0)
print("toggles with register bits:", sum(1 for a, _, _ in tog if res.get(a)), "of", len(tog),
      "| reg bits mapped:", sum(len(v) for v in res.values()), "ambig:", len(ambig), "nomatch:", len(nomatch))
print("toggles with no register effect:", [a for a, _, _ in tog if not res.get(a)][:60])
