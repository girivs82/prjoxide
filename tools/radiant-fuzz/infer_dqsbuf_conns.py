#!/usr/bin/env python3
"""
Infer the fixed connections from CIB wires to the DQS-group blocks' input pins on LFCPNX: the
DQSBUFA_CORE and the IVREF_CORE (the bank VREF generator, BNKVRGEN18, that DQSBUF_IVREF adds),
from Radiant-routed timing-fuzzer designs (timing/fuzzers/LFCPNX/12-dqsbuf-ivref).

Same method as infer_block_conns.py (LRAM): for every SDF interconnect arc into a block input pin,
the CIBMUX outputs and CE/LSR/CLK wires near the block that the source's net reaches are the
candidates; per pin the candidates of all arcs are intersected (or voted, --vote).

The blocks' sites: DQSBUFA_CORE_R<r>C<c> from Radiant's timing report; its connections belong to
the group's SYSIO_B<n>_1_DQS0 tile type (the tile at R<r+1>C<c+3>), with the pin wires named as that
tile type's existing connections (N1W5:J<pin>_DQSBUFA_CORE_I_DQS_TOP). IVREF_CORE is on no timing
path; there is one per bank (par places at most one DQSBUF_IVREF per bank) and its pins take the
same wires whichever DQS group of the bank uses it, so it is a bank-level block. Its connections are
inferred and written relative to the bank's reference tile (BANK_REF below, the tile that also holds
BANK<n>.IVREF), with the pin wires J<pin>_IVREF_CORE in that tile.

--check: compare the DQSBUFA pins inferred with the connections already in the database.
--replace: for DQSBUFA input pins resolved unanimously by at least MIN_REPLACE_ARCS arcs, replace the
database's connection of that pin (from LIFCL) with the inferred one; pins Radiant does not
contradict are left as they are.

Usage (in the container, PYTHONPATH with util/common, util/fuzz and timing/util):
  infer_dqsbuf_conns.py <out.json> <design dir>... [--write] [--vote] [--check]
"""
import glob
import json
import re
import sys
from collections import defaultdict
from os import path

import extract_route_cram as E
from parse_sdf import parse_sdf_file
import infer_block_conns as B

SITE_RE = re.compile(r'^DQSBUFA_CORE(?:_DQSBUFA_CORE)?_R(\d+)C(\d+)$')
BLOCKS = {"DQSBUFA_inst": "DQSBUFA_CORE", "BNKVRGEN18_inst": "IVREF_CORE"}


# bank -> (reference tile row, column, tile type): the tiles holding BANK<n>.IVREF
BANK_REF = {3: (73, 159, "BANKREF3_DDR42"), 4: (74, 77, "BANKREF4_DLY42_DDR41"), 5: (74, 14, "DDR40_ECLK_L")}


def bank_of(c):
    return 5 if c < 48 else 4 if c < 108 else 3


MIN_REPLACE_ARCS = 10


def replace_conns(tt, conns):
    """Set the driver of each pin wire in conns to the inferred wire (other entries are kept)."""
    import database
    fn = path.join(database.get_db_root(), "LFCPNX", "tiletypes", tt + ".ron")
    t = open(fn).read()
    for to, frm in conns:
        pat = re.compile(r'(\n    "%s": \[\n)(.*?)(\n    \],)' % re.escape(to), re.S)
        new_body = '      (\n        from_wire: "{}",\n      ),'.format(frm)
        t2, n = pat.subn(lambda m: m.group(1) + new_body + m.group(3), t, count=1)
        if n != 1:
            raise RuntimeError("{}: no connection entry for {}".format(tt, to))
        t = t2
    open(fn, "w").write(t)
    print("  {}: {} connections replaced".format(tt, len(conns)))


def dqs0_tile(dev, r, c):
    for tt in dev.tiles_at.get((r + 1, c + 3), ()):
        if re.match(r'SYSIO_B[345]_1_DQS0', tt):
            return tt, r + 1, c + 3
    return None


def main():
    out_json = sys.argv[1]
    write, vote, check = "--write" in sys.argv, "--vote" in sys.argv, "--check" in sys.argv
    replace = "--replace" in sys.argv
    dirs = [a for a in sys.argv[2:] if not a.startswith("--")]
    dev = E.Device(E.FAMILY, E.DEVICE)
    cands, counts = {}, defaultdict(int)
    votes = defaultdict(lambda: defaultdict(int))
    for d in dirs:
        name = re.search(r'^NAME=(\S+)', open(path.join(d, "Makefile")).read(), re.M).group(1)
        outdir = path.join(d, "..", "..", "..", "output", "LFCPNX")
        for fasm in sorted(glob.glob(path.join(d, "work", "design_*.fasm"))):
            i = re.search(r'design_(\w+)\.fasm', fasm).group(1)
            vo = path.join(outdir, "{}_{}_9.vo".format(name, i))
            if not path.exists(vo):
                continue
            routing = E.Routing(dev, fasm)
            member2cell, cell2ports = E.parse_vo(vo)
            site = E.parse_twr([path.join(d, "work", "design_{}.twr".format(i))], member2cell)
            port2site, pin2site = E.parse_pad(path.join(d, "work", "design_{}.tmp".format(i), "par.pad"))
            for cell, ports in cell2ports.items():
                for p in ports:
                    if port2site.lookup(p):
                        site[cell] = port2site.lookup(p)
            # IVREF_CORE: with its own instance's DQSBUFA
            for cell in list(cell2ports):
                if cell.endswith("BNKVRGEN18_inst"):
                    sib = cell[:-len("BNKVRGEN18_inst")] + "DQSBUFA_inst"
                    if sib in site:
                        site[cell] = site[sib]
            sdf = parse_sdf_file(vo[:-3] + ".sdf").cells["top"]
            arcs = [(tuple(E.unescape(x) for x in f.rsplit("/", 1)), tuple(E.unescape(x) for x in t.rsplit("/", 1)))
                    for f, t in sorted(sdf.interconnect.keys())]
            E.place_from_routing(dev, routing, arcs, site)
            fw = B.Forward(dev, routing)
            reach_cache = {}
            for src, dst in arcs:
                cell, pin = dst
                blk = next((b for k, b in BLOCKS.items() if cell.endswith(k)), None)
                if blk is None or cell not in site or src[0] not in site:
                    continue
                m = SITE_RE.match(site[cell])
                if not m:
                    continue
                r, c = int(m.group(1)), int(m.group(2))
                t = dqs0_tile(dev, r, c)
                if t is None:
                    continue
                tt, tr, tc = t
                pin_w = ("W", tr - 1, tc - 5, "J{}_{}_I_DQS_TOP".format(pin, blk))
                if blk == "IVREF_CORE":
                    tr, tc, tt = BANK_REF[bank_of(c)]
                    r, c = tr, tc
                    pin_w = ("W", tr, tc, "J{}_IVREF_CORE".format(pin))
                sk = frozenset(E.pin_keys(dev, site[src[0]], src[1], routing, {}))
                if not sk:
                    continue
                if sk not in reach_cache:
                    reach_cache[sk] = fw.reach(sk)
                cs = {(B.rel(pin_w, tr, tc), B.rel(k, tr, tc)) for k in reach_cache[sk]
                      if B.near(k, r, c, dev) and B.INPUT_WIRE_RE.match(k[3])}
                key = (tt, blk, pin)
                if not cs:
                    continue
                cands[key] = cs if key not in cands else cands[key] & cs
                counts[key] += 1
                for c_ in cs:
                    votes[key][c_] += 1
    result, report = defaultdict(list), {}
    for (tt, blk, pin), cs in sorted(cands.items()):
        n = counts[tt, blk, pin]
        ranked = sorted(votes[tt, blk, pin].items(), key=lambda kv: -kv[1])
        rep = dict(arcs=n, candidates=sorted(cs), votes=[[list(c_), v] for c_, v in ranked[:4]])
        chosen = None
        if len(cs) == 1 and n >= B.MIN_ARCS:
            chosen = next(iter(cs))
        elif vote and ranked and n >= B.MIN_VOTE_ARCS and ranked[0][1] >= B.VOTE_SHARE * n and \
                (len(ranked) < 2 or ranked[1][1] <= B.RUNNER_UP_SHARE * n):
            chosen = ranked[0][0]
            rep["by_vote"] = True
        if chosen:
            result[tt].append((chosen[0], chosen[1], n, blk))
        report["{} {} {}".format(tt, blk, pin)] = rep
    json.dump(dict(conns={k: sorted(v) for k, v in result.items()}, report=report), open(out_json, "w"), indent=1)
    for tt in sorted(result):
        print("{}: {} pins resolved".format(tt, len(result[tt])))
        for to, frm, n, blk in sorted(result[tt]):
            print("   {} <- {} ({} arcs)".format(to, frm, n))
    if check:
        import database
        for tt in sorted(result):
            t = open(path.join(database.get_db_root(), "LFCPNX", "tiletypes", tt + ".ron")).read()
            have = defaultdict(set)
            for to, body in re.findall(r'\n    "([^"]+)": \[(.*?)\n    \],', t[t.index("\n  conns: {"):], re.S):
                have[to] |= set(re.findall(r'from_wire: "([^"]+)"', body))
            ok = bad = new = 0
            for to, frm, n, blk in result[tt]:
                if to not in have:
                    new += 1
                elif frm in have[to]:
                    ok += 1
                else:
                    bad += 1
                    print("   MISMATCH {}: inferred {} database {}".format(to, frm, sorted(have[to])))
            print("{} check: {} agree with the database, {} disagree, {} not in it".format(tt, ok, bad, new))
    if write:
        for tt in sorted(result):
            B.write_conns(tt, [(to, frm) for to, frm, n, blk in result[tt] if blk == "IVREF_CORE"])
    if replace:
        for tt in sorted(result):
            unan = []
            for to, frm, n, blk in result[tt]:
                rep = report["{} {} {}".format(tt, blk, re.match(r'N1W5:J(.*)_DQSBUFA_CORE_I_DQS_TOP', to).group(1))] \
                    if blk == "DQSBUFA_CORE" else None
                if rep and len(rep["candidates"]) == 1 and rep["votes"][0][1] == n and n >= MIN_REPLACE_ARCS:
                    unan.append((to, frm))
            if unan:
                replace_conns(tt, unan)
    amb = sum(1 for v in report.values() if len(v["candidates"]) != 1 and not v.get("by_vote"))
    print("{} pins with several or no candidates".format(amb))


if __name__ == "__main__":
    main()
