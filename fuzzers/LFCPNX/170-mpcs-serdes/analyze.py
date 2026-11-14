#!/usr/bin/env python3
"""Decode each variant's bitstream (native prjoxide) and summarise, against the empty baseline:
SERDES-related tile bits, IP-bus writes, and other non-routing differences."""
import json, os, re, subprocess, sys
from collections import defaultdict
P = os.path.expanduser("~/src/radiant-work/target-host/release/prjoxide")
DB = os.path.expanduser("~/src/prjoxide/database")
F = os.path.expanduser("~/src/radiant-work/serdes/fuzz")
SER = re.compile(r'__(PCS_\d|SERDES_REFCLK|CDR\d|PCIE_LL)\.')

def decode(bit, fasm):
    if not os.path.exists(fasm) or os.path.getmtime(fasm) < os.path.getmtime(bit):
        subprocess.run([P, "unpack", "--db", DB, bit, fasm], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    tiles, ip, other = defaultdict(set), {}, set()
    for l in open(fasm):
        l = l.strip()
        if l.startswith("IP_UNKNOWN.0x"):
            ip[int(l[13:21], 16)] = int(l.split("8'h")[1][:2], 16)
        elif SER.search(l):
            m = re.match(r'^(\S+?)__(\S+?)\.(.*)$', l)
            tiles[m.group(1) + ":" + m.group(2)].add(m.group(3))
        elif l and not l.startswith(("#", "{")) and ".PIP." not in l and "__PLC." not in l:
            other.add(l)
    return tiles, ip, other

def main(names):
    base = decode(os.path.join(F, "../base_t.bit"), os.path.join(F, "base.fasm"))
    out = {}
    for n in names:
        bit = os.path.join(F, n, "b", n + ".bit")
        if not os.path.exists(bit):
            out[n] = None; continue
        t, ip, other = decode(bit, os.path.join(F, n, n + ".fasm"))
        out[n] = dict(
            tiles={k: sorted(v - base[0].get(k, set())) for k, v in t.items() if v - base[0].get(k, set())},
            tiles_cleared={k: sorted(base[0][k] - t.get(k, set())) for k in base[0] if base[0][k] - t.get(k, set())},
            ip={"0x%08X" % a: v for a, v in sorted(ip.items())},
            other_new=sorted(other - base[2]), other_gone=sorted(base[2] - other))
    return out

if __name__ == "__main__":
    names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    res = main(names)
    json.dump(res, open(sys.argv[2], "w"), indent=1)
    for n, r in res.items():
        if r is None: print(n, "NO BIT"); continue
        blocks = sorted({a[:6] for a in r["ip"]})
        print(n, "tiles:", {k.split(":")[1] + "@" + k.split("__")[0].split("_")[-1]: len(v) for k, v in r["tiles"].items()},
              "ip:", len(r["ip"]), "bytes in", blocks, "other+:", len(r["other_new"]))
