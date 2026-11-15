#!/usr/bin/env python3
"""
Check the clock connections of the LFCPNX HP-bank edge-clock blocks against Radiant's routing, in the
designs of timing/fuzzers/LFCPNX/18-eclk-pins (every ECLKSYNC / ECLKDIV pinned to its site, each
ECLKSYNC fed from its own PCLK pin, cascade runs feeding a bank's edge clock j from another bank).
The clock pins have no fabric route to trace, but the pips Radiant sets in the edge-clock tiles show
which mux inputs it used:

- ECLKIN of ECLKSYNC<b>_<k> <- G:JMUXIN<k>_ECLKBANK<b>: Radiant sets JMUXIN<m> <- JPCLKT<p> for each
  used ECLKSYNC. If m = k, every PCLK ball must map to one JPCLKT index p in every design, however the
  balls are assigned to ECLKSYNCs (random per design). A wrong k <-> m mapping breaks that.
- ECLKOUT of ECLKSYNC<b>_<j> -> JECLKSYNCM<j> of ECLKCASMUX<b>, and the cascade inputs: for each
  bank b and edge clock j that is used, Radiant sets JECLKOUT<j> <- JECLKSYNCM<j> (its own ECLKSYNC
  j), or <- JECLKCAS0M<j> / JECLKCAS1M<j> (another bank's ECLKSYNC j). Which input it took is compared
  with the bank the design fed edge clock j from, and with the database's connections of those inputs.
  A cascade mux's select bits are split over two of the four edge-clock tiles (ECLK_0, BMID_0_ECLK_1,
  BMID_1_ECLK_2, ECLK_3), and per tile some inputs share bits (CAS0M and SYNCM have the same bit in one
  tile, CAS1M and SYNCM in the other), so the per-tile decode can mislabel the input. The input is read
  from the raw select bits instead: the design is unpacked with a copy of the database in which every
  bit of the cascade-mux pips is an enum of its own, and the set bits are matched against each input's
  full bit set over all four tiles.

Usage: check_eclk_routing.py <design dir> <prjoxide binary> [out.json]
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile
import re
import sys
from collections import defaultdict
from os import path

# the database's (LIFCL-derived) cascade inputs: ECLKCASMUX<b> CAS<n>M <- ECLKSYNC of bank
DB_CAS = {3: {"CAS0M": 5, "CAS1M": 4}, 4: {"CAS0M": 3, "CAS1M": 5}, 5: {"CAS0M": 4, "CAS1M": 3}}

ECLK_TILES = {72: "ECLK_0", 73: "BMID_0_ECLK_1", 74: "BMID_1_ECLK_2", 75: "ECLK_3"}


def probe_db(dbroot, out):
    """Copy the database to out, replacing the cascade-mux pips of the edge-clock tiles by one enum
    per bit (PROBE.F<f>B<b>); return (bank, j, input kind) -> its set bits as (column, frame, bit)."""
    shutil.copytree(dbroot, out)
    sig = defaultdict(set)
    for col, tt in ECLK_TILES.items():
        fn = os.path.join(out, "LFCPNX", "tiletypes", tt + ".ron")
        s = open(fn).read()
        pi = s.index("  pips: {\n")
        pe = s.index("\n  },\n", pi)
        keep, bits = [], set()
        for to, body in re.findall(r'\n    "([^"]+)": \[(.*?)\n    \],', s[pi:pe], re.S):
            m = re.match(r'G:JECLKOUT(\d)_ECLKCASMUX_CORE_ECLKCASMUX(\d)$', to)
            if not m:
                keep.append((to, body))
                continue
            for fw, b in re.findall(r'from_wire: "([^"]+)",\s*bits: \[(.*?)\]', body, re.S):
                k = re.search(r'JECLK(SYNCM|CAS0M|CAS1M)\d', fw).group(1)
                bb = {(int(f), int(x)) for f, x, inv in re.findall(r'frame:(\d+),bit:(\d+),invert:(\w+)', b)
                      if inv == "false"}
                sig[(int(m.group(2)), int(m.group(1)), k)] |= {(col,) + fb for fb in bb}
                bits |= bb
        s = s[:pi] + ("  pips: {\n" + "".join('    "%s": [%s\n    ],\n' % kb for kb in keep)).rstrip("\n") + s[pe:]
        add = "".join('    "PROBE.F%dB%d": (\n      options: {\n        "1": [(frame:%d,bit:%d,invert:false,),],\n'
                      '      },\n    ),\n' % (f, b, f, b) for f, b in sorted(bits))
        if "  enums: {\n" in s:
            ei = s.index("  enums: {\n") + len("  enums: {\n")
            s = s[:ei] + add + s[ei:]
        else:
            s = s.replace("  enums: {},", "  enums: {\n" + add + "  },", 1)
        open(fn, "w").write(s)
    return sig


PROBE_RE = re.compile(r'^CIB_R74C(\d+)__\w+\.PROBE\.F(\d+)B(\d+)\.1$')
MUXIN_RE = re.compile(r'PIP\.G__JMUXIN(\d)_ECLKBANK_CORE_ECLKBANK(\d)\.G__JPCLKT(\d)_ECLKBANK_CORE_ECLKBANK\d$')
CAS_RE = re.compile(r'PIP\.G__JECLKOUT(\d)_ECLKCASMUX_CORE_ECLKCASMUX(\d)\.\w*?__JECLK(SYNCM|CAS0M|CAS1M)(\d)_ECLKCASMUX_CORE_ECLKCASMUX\d$')


def main():
    global SIG, TMP, BIN
    d, BIN = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None
    TMP = tempfile.mkdtemp()
    SIG = probe_db(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "database"),
                   os.path.join(TMP, "db"))
    ball_p = defaultdict(lambda: defaultdict(list))       # (bank, ball) -> p -> [design]
    mux_ok, mux_bad = 0, []
    cas_seen = defaultdict(lambda: defaultdict(list))     # (bank, src bank) -> input kind -> [design]
    cas_bad = []
    designs = 0
    for fasm in sorted(glob.glob(path.join(d, "work", "design_*.fasm")),
                       key=lambda f: int(re.search(r'design_(\d+)', f).group(1))):
        n = int(re.search(r'design_(\d+)', fasm).group(1))
        v = open(path.join(d, "work", "design_{}.v".format(n))).read()
        pdc = open(path.join(d, "work", "design_{}.pdc".format(n))).read()
        lines = [l.strip() for l in open(fasm)]
        designs += 1
        syncs = {(int(b), int(k)) for b, k in re.findall(r'u_es(\d)_(\d) \(', v)}
        src = {(int(b), int(j)): int(sb) for b, j, sb in
               re.findall(r'u_ed(\d)_(\d) \(\.ECLKIN\(e(\d)_\d\)', v)}
        # an edge clock j of bank b is also used by ODDRX2 (b, j)
        for b, j, sb in re.findall(r'u_od(\d)_(\d) \(.*?\.ECLK\(e(\d)_\d\)', v):
            src.setdefault((int(b), int(j)), int(sb))
        balls = dict(((int(b), int(k)), ball) for ball, b, k in
                     re.findall(r'-site \{(\w+)\} \[get_ports pclk(\d)_(\d)\]', pdc))
        muxin = defaultdict(dict)       # bank -> m -> p
        for l in lines:
            m = MUXIN_RE.search(l)
            if m:
                muxin[int(m.group(2))][int(m.group(1))] = int(m.group(3))
        pf = os.path.join(TMP, "p.fasm")
        subprocess.run([BIN, "unpack", "--db", os.path.join(TMP, "db"), fasm[:-5] + ".bit", pf],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        set_bits = set()
        for l in open(pf):
            m = PROBE_RE.match(l.strip())
            if m:
                set_bits.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
        cas = {}
        for (b, j) in {(b, j) for b in (3, 4, 5) for j in range(4)}:
            mine = set().union(*[SIG[(b, j, k)] for k in ("SYNCM", "CAS0M", "CAS1M")])
            on = set_bits & mine
            if not on:
                continue
            kinds = [k for k in ("SYNCM", "CAS0M", "CAS1M") if SIG[(b, j, k)] == on]
            cas[(b, j)] = (kinds[0], j) if len(kinds) == 1 else ("?" + str(sorted(on)), j)
        # ECLKIN: the used ECLKSYNC indices are the used JMUXIN indices
        for b in (3, 4, 5):
            ks = {k for (bb, k) in syncs if bb == b}
            if set(muxin[b]) != ks:
                mux_bad.append((n, b, sorted(ks), sorted(muxin[b])))
                continue
            mux_ok += 1
            for k in ks:
                ball_p[(b, balls[(b, k)])][muxin[b][k]].append(n)
        # ECLKOUT / cascade
        for (b, j), sb in sorted(src.items()):
            kind_idx = cas.get((b, j))
            if kind_idx is None or kind_idx[1] != j:
                cas_bad.append((n, b, j, sb, kind_idx))
                continue
            kind = kind_idx[0]
            cas_seen[(b, sb)][kind].append(n)
            want = "SYNCM" if sb == b else None
            if want and kind != want:
                cas_bad.append((n, b, j, sb, kind_idx))
    # PCLK ball -> JPCLKT: one index per ball in every design
    ball_rep = {"{} {}".format(b, ball): {str(p): ds for p, ds in ps.items()} for (b, ball), ps in sorted(ball_p.items())}
    ball_consistent = all(len(ps) == 1 for ps in ball_p.values())
    cas_rep = {}
    cas_agree = True
    for (b, sb), kinds in sorted(cas_seen.items()):
        k_ = sorted(kinds)
        db = "SYNCM" if sb == b else [kk for kk, bank in DB_CAS[b].items() if bank == sb]
        db = db if isinstance(db, str) else (db[0] if db else None)
        agree = len(k_) == 1 and k_[0] == db
        cas_agree &= agree
        cas_rep["CASMUX{} from bank {}".format(b, sb)] = dict(
            radiant={kk: len(v) for kk, v in kinds.items()}, database=db, agree=agree)
    rep = dict(designs=designs, eclkin=dict(banks_ok=mux_ok, mismatches=mux_bad, ball_to_jpclkt=ball_rep,
                                            consistent=ball_consistent),
               eclkout_cascade=dict(inputs=cas_rep, all_agree=cas_agree, mismatches=cas_bad))
    if out:
        json.dump(rep, open(out, "w"), indent=1)
    print("designs:", designs)
    print("ECLKIN <- JMUXIN<k> (used ECLKSYNC indices = used JMUXIN indices): {} bank-designs ok, {} not: {}".format(
        mux_ok, len(mux_bad), mux_bad[:4]))
    print("PCLK ball -> JPCLKT index, one per ball in every design:", ball_consistent)
    for k, v in ball_rep.items():
        print("   ", k, {p: len(ds) for p, ds in v.items()})
    print("edge clock j inputs (Radiant vs database):")
    for k, v in cas_rep.items():
        print("   ", k, v)
    print("cascade / ECLKOUT mismatches:", cas_bad[:6])


if __name__ == "__main__":
    main()
