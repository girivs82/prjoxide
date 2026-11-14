#!/usr/bin/env python3
"""Write the LFCPNX SERDES (MPCS PCS lane) database from the fuzz solutions:
  LFCPNX/iptypes/PCS_LANE.ron   words (binary PCSX attributes), enums (string attributes), and
                                always_on fixed bits (register bits no attribute drives, with value)
  LFCPNX/LFCPNX-100/baseaddr.json  PCS_LANE0..7 regions
  LFCPNX/tiletypes/PCS_0..7.ron    lane / quad enables and bonding
Register bit (frame = byte offset, bit = bit 0-7) as for the other IP types."""
import json, os, re, sys
DB = sys.argv[1]
S = os.path.dirname(os.path.abspath(__file__))
pat = json.load(open(os.path.join(S, "pat_solution.json")))
enm = json.load(open(os.path.join(S, "enum_solution.json")))
eidx = json.load(open(os.path.join(S, "enum_index.json")))
multi = json.load(open(os.path.join(S, "multi_solution.json"))) if os.path.exists(os.path.join(S, "multi_solution.json")) else {}
base = open(os.path.join(S, "base_netlist.v")).read()
bv = {m.group(1): m.group(2) for m in re.finditer(r'defparam \\PCSX1_inst\.u_PCSX1 \.([A-Z0-9_]+) = "(.*?)";', base)}

def cb(o, b, inv):
    return "(frame:%d,bit:%d,invert:%s,)" % (o, b, "true" if inv else "false")

# words: attr[i] -> register bit; LSB first
words = {}
for k, v in pat["mapping"].items():
    a, i = re.match(r"^(\w+)\[(\d+)\]$", k).groups()
    assert len(v) == 1
    words.setdefault(a, {})[int(i)] = tuple(v[0])
for a in list(words):
    w = len(bv[a]) - 2
    if len(words[a]) != w:       # partially mapped word (unmapped bits have no hardware effect)
        pass
# enums: two-valued toggles
enums = {}
for a, val, alt in eidx["toggles"]:
    rb = enm["toggles"].get(a, [])
    if not rb:
        continue
    enums[a] = {val: [cb(o, b, not pol) for o, b, pol in rb],      # baseline: bit = pol
                alt: [cb(o, b, bool(pol)) for o, b, pol in rb]}    # alternative: bit = !pol
for a, opts in multi.items():
    enums[a] = {v: [cb(o, b, not val) for o, b, val in bits] for v, bits in opts.items()}
# register bits claimed by more than one enum combine as OR in Radiant's output (e.g. 0x1E1 bits 3-4:
# BIST_BYPASS_TX_GATE / BIST_RX_DATA_SEL and BIST_PTN_SEL): for those, options only set bits, never clear
from collections import Counter
claims = Counter()
for a, opts in enums.items():
    for (o, b) in {tuple(map(int, re.findall(r"frame:(\d+),bit:(\d+)", x)[0])) for xs in opts.values() for x in xs}:
        claims[(o, b)] += 1
shared = {k for k, c in claims.items() if c > 1}
for a, opts in enums.items():
    for v in opts:
        opts[v] = [x for x in opts[v] if not (tuple(map(int, re.findall(r"frame:(\d+),bit:(\d+)", x)[0])) in shared and "invert:true" in x)]
print("bits shared between enums (OR):", sorted(shared))
# fixed bits: register bits that never changed in any build, with their value
fixed = {}
for k, v in pat["const"].items():
    o, b = map(int, k.split("."))
    fixed[(o, b)] = v
covered = {(o, b) for v in words.values() for (o, b, _) in v.values()}
covered |= {(o, b) for a in enm["toggles"].values() for (o, b, _) in a}
covered |= {(o, b) for opts in multi.values() for bits in opts.values() for (o, b, _) in bits}
fixed = {k: v for k, v in fixed.items() if k not in covered}
L = ["(", "  pips: {},", "  words: {"]
for a in sorted(words):
    L.append('    "%s": (' % a)
    L.append("      bits: [")
    for i in range(max(words[a]) + 1):
        if i in words[a]:
            o, b, inv = words[a][i]
            L.append("        [%s]," % cb(o, b, inv))
        else:
            L.append("        [],")
    L += ["      ],", "    ),"]
L += ["  },", "  enums: {"]
for a in sorted(enums):
    L.append('    "%s": (' % a)
    L.append("      options: {")
    for v in sorted(enums[a]):
        L.append('        "%s": [%s],' % (v, ",".join(enums[a][v])))
    L += ["      },", "    ),"]
L += ["  },", "  conns: {},", "  always_on: ["]
for (o, b), v in sorted(fixed.items()):
    L.append("    %s," % cb(o, b, not v))
L += ["  ],", ")"]
os.makedirs(os.path.join(DB, "LFCPNX", "iptypes"), exist_ok=True)
open(os.path.join(DB, "LFCPNX", "iptypes", "PCS_LANE.ron"), "w").write("\n".join(L) + "\n")
print("PCS_LANE: %d words (%d bits), %d enums, %d fixed bits" % (len(words), sum(len(v) for v in words.values()), len(enums), len(fixed)))

# base addresses
ba = os.path.join(DB, "LFCPNX", "LFCPNX-100", "baseaddr.json")
j = json.load(open(ba))
for k in range(8):
    j["regions"]["PCS_LANE%d" % k] = {"addr": 0x0E420000 + k * 0x20000, "abits": 9}
open(ba, "w").write(json.dumps(j, indent=4, sort_keys=True) + "\n")

# PCS tile types: lane n in PCS_n; quad enables/bonding in PCS_0 (lanes 0-3) and PCS_4 (lanes 4-7)
def tb(f, b, inv=False):
    return "(\n          frame: %d,\n          bit: %d,\n          invert: %s,\n        )" % (f, b, "true" if inv else "false")
for n in range(8):
    en = {}
    en["LANE_USED"] = {"ENABLED": [tb(22, 0)], "DISABLED": []}
    if n not in (1, 5):           # PCS_1/PCS_5 F0B0 is set in every design (left undecoded)
        en["LANE_EN"] = {"ENABLED": [tb(0, 0)], "DISABLED": []}
    if n in (2, 3, 6, 7):         # 10GE is only offered on these lanes (b_10ge: lane 2 sets F28B0)
        en["MODESEL"] = {"PCS10GE": [tb(28, 0)], "PCS": []}
    if n in (0, 4):
        en["QUAD_USED"] = {"ENABLED": [tb(1, 0), tb(4, 0)], "DISABLED": []}
        en["PWDN_N"] = {"DISABLED": [tb(27, 0)], "ENABLED": []}
        en["IDDQ_PCS"] = {"ENABLED": [tb(21, 0)], "DISABLED": []}
        en["PHY_MODE"] = {"SATAMODE": [tb(25, 0)], "PCIEMODE": []}
        pj = json.load(open(os.path.join(S, "pipe_ln2lk.json")))
        en["PIPE_LN2LK"] = {v: [tb(f, 0, f not in bits) for f in pj["bits"]] for v, bits in pj["opts"].items()}
    T = ["(", "  pips: {},", "  words: {"]
    if n in (0, 4):
        # TX_BOND_MODE and RX_BOND_MODE (always equal): bit k sets F(38+k) and F(43+k)
        T.append('    "BOND_MODE": (')
        T.append("      bits: [")
        for k in range(5):
            T.append("        [" + tb(38 + k, 0) + ", " + tb(43 + k, 0) + "],")
        T += ["      ],", "    ),"]
    T += ["  },", "  enums: {"]
    for e in sorted(en):
        T.append('    "%s": (' % e)
        T.append("      options: {")
        for o in sorted(en[e]):
            T.append('        "%s": [' % o)
            for x in en[e][o]:
                T.append("        " + x + ",")
            T.append("        ],")
        T += ["      },", "    ),"]
    T += ["  },", "  conns: {},", ")"]
    open(os.path.join(DB, "LFCPNX", "tiletypes", "PCS_%d.ron" % n), "w").write("\n".join(T) + "\n")
print("baseaddr: PCS_LANE0..7; tiletypes PCS_0..7")
