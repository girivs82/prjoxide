#!/usr/bin/env python3
"""
Infer the fixed connections between CIB wires and the HP-bank (3 / 4 / 5) IO logic pins on LFCPNX from
Radiant-routed timing-fuzzer designs (timing/fuzzers/LFCPNX/25-iologic-delay): the delay cells'
dynamic pins (OUTDELAYA LOAD_N / MOVE / DIRECTION_LPDDR4_WT in, COUT_LPDDR4_WT out; DELAYA LOAD_N /
MOVE / DIR in, COUT (CFLAG) out) and any other IO logic pin with an SDF arc.

Same method as infer_dqsbuf_conns.py: Radiant's SDF names the IO logic of a pad <port>_pad[<i>]_IOL
with the IOLOGIC pin names. For an arc into a pin, the CIBMUX outputs and CE / LSR / CLK wires near
the pad that the source's net reaches are candidates; for an arc from a pin, the undriven wires near
the pad where the sink's route starts. Per (tile type, pad side, pin) the candidates of all arcs are
intersected.

Both pads' IO logic pin wires belong to the pad pair's SYSIO_B<n>_0* tile (column = the pad offset):
J<pin>_IOLOGIC_CORE_I_GEARING_PIC_TOP_<A|B>, as the database's existing connections name them; the
inferred connections are written relative to that tile.

Usage (in the container, PYTHONPATH with util/common, util/fuzz, timing/util and tools/radiant-fuzz):
  infer_iologic_conns.py <out.json> <design dir>... [--check]
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

IOL_RE = re.compile(r'^(.*)_pad(\[\d+\])?(?:\.bb_inst)?_IOL$')


def near(k, tr, tc):
    """a CIB wire beside the pad pair: the CIB row above the IO row, columns tc - 1 .. tc + 2"""
    return k[0] == "W" and tr - 1 <= k[1] <= tr and tc - 1 <= k[2] <= tc + 2


def main():
    out_json = sys.argv[1]
    check = "--check" in sys.argv
    dirs = [a for a in sys.argv[2:] if not a.startswith("--")]
    dev = E.Device(E.FAMILY, E.DEVICE)
    import database
    iodb = json.load(open(path.join(database.get_db_root(), "LFCPNX", "LFCPNX-100", "iodb.json")))
    pk = iodb["packages"].index("LFG672")
    pin2pad = {p["pins"][pk]: p for p in iodb["pads"] if p["pins"][pk]}
    cands, counts, votes = {}, defaultdict(int), defaultdict(lambda: defaultdict(int))
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
            padf = path.join(d, "work", "design_{}.tmp".format(i), "par.pad")
            port2site, pin2site = E.parse_pad(padf)
            for cell, ports in cell2ports.items():
                for p in ports:
                    if port2site.lookup(p):
                        site[cell] = port2site.lookup(p)
            # port -> package pin, from par.pad's port table
            port_pin = {}
            for line in open(padf, errors="replace"):
                m = re.match(r'^\|\s*(\S+)\s*\|\s*(\w+)/\d+\s*\|', line)
                if m:
                    port_pin[m.group(1)] = m.group(2)
            sdf = parse_sdf_file(vo[:-3] + ".sdf").cells["top"]
            arcs = [(tuple(E.unescape(x) for x in f.rsplit("/", 1)), tuple(E.unescape(x) for x in t.rsplit("/", 1)))
                    for f, t in sorted(sdf.interconnect.keys())]
            E.place_from_routing(dev, routing, arcs, site)
            fw = B.Forward(dev, routing)

            def iol_tile(cell):
                """(tile type, row, col, side) of the SYSIO_B<n>_0* tile holding this IO logic's pins"""
                m = IOL_RE.match(cell)
                if not m:
                    return None
                port = m.group(1) + (m.group(2) or "")
                pin = port_pin.get(port)
                pad = pin2pad.get(pin)
                if pad is None or pad["side"] != "B" or pad["bank"] not in (3, 4, 5):
                    return None
                c0 = pad["offset"]
                for tt in dev.tiles_at.get((74, c0), ()):
                    if re.match(r'SYSIO_B[345]_0', tt):
                        return tt, 74, c0, pad["name"][-1]
                return None

            def drv(k):
                # the database's own IO logic pin connections (what is being checked) end the trace
                return [s_ for s_ in routing.drivers(k)
                        if not (s_[0] == "W" and isinstance(s_[3], str) and "_IOLOGIC_CORE_I_GEARING_PIC_TOP_" in s_[3])]
            reach_cache = {}
            for src, dst in arcs:
                for cell, pin, is_out in ((src[0], src[1], True), (dst[0], dst[1], False)):
                    t = iol_tile(cell)
                    if t is None:
                        continue
                    tt, tr, tc, side = t
                    pin_w = ("W", tr, tc, "J{}_IOLOGIC_CORE_I_GEARING_PIC_TOP_{}".format(pin, side))
                    other = dst if is_out else src
                    if other[0] not in site or IOL_RE.match(other[0]):
                        continue
                    if is_out:
                        cs = set()
                        for dk in E.pin_keys(dev, site[other[0]], other[1], routing, {}):
                            parent = {dk: None}
                            fr = [dk]
                            while fr and len(parent) < 20000:
                                nx = []
                                for k in fr:
                                    for s_ in drv(k):
                                        if s_ not in parent:
                                            parent[s_] = k
                                            nx.append(s_)
                                fr = nx
                            cs |= {(B.rel(k, tr, tc), B.rel(pin_w, tr, tc)) for k in parent
                                   if near(k, tr, tc) and not drv(k)}
                    else:
                        sk = frozenset(E.pin_keys(dev, site[other[0]], other[1], routing, {}))
                        if not sk:
                            continue
                        if sk not in reach_cache:
                            reach_cache[sk] = fw.reach(sk)
                        cs = {(B.rel(pin_w, tr, tc), B.rel(k, tr, tc)) for k in reach_cache[sk]
                              if near(k, tr, tc) and B.INPUT_WIRE_RE.match(k[3])}
                    if not cs:
                        continue
                    key = (tt, side, pin, "out" if is_out else "in")
                    cands[key] = cs if key not in cands else cands[key] & cs
                    counts[key] += 1
                    for c_ in cs:
                        votes[key][c_] += 1
    report, resolved = {}, defaultdict(list)
    for key, cs in sorted(cands.items()):
        n = counts[key]
        ranked = sorted(votes[key].items(), key=lambda kv: -kv[1])
        report[" ".join(key)] = dict(arcs=n, candidates=sorted(cs), votes=[[list(c_), v] for c_, v in ranked[:4]])
        if len(cs) == 1:
            resolved[key[0]].append((key, next(iter(cs)), n))
    json.dump(dict(report=report), open(out_json, "w"), indent=1)
    have_all = {}
    for tt in sorted({k[0] for k in cands}):
        t = open(path.join(database.get_db_root(), "LFCPNX", "tiletypes", tt + ".ron")).read()
        have = defaultdict(set)
        for to, body in re.findall(r'\n    "([^"]+)": \[(.*?)\n    \],', t[t.index("\n  conns: {"):], re.S):
            have[to] |= set(re.findall(r'from_wire: "([^"]+)"', body))
        have_all[tt] = have
    for key, cs in sorted(cands.items()):
        tt, side, pin, io = key
        n = counts[key]
        if len(cs) == 1:
            to, frm = next(iter(cs))
            st = ""
            if check:
                st = " [db: agrees]" if frm in have_all[tt].get(to, ()) else " [db: {}]".format(
                    sorted(have_all[tt].get(to, ())) if io == "in" else sorted(k for k, v in have_all[tt].items() if frm in v) or "none")
            print("{} {} {:22s} {:3s} {} <- {} ({} arcs){}".format(tt, side, pin, io, to, frm, n, st))
        else:
            print("{} {} {:22s} {:3s} UNRESOLVED {} candidates over {} arcs: {}".format(tt, side, pin, io, len(cs), n, sorted(cs)[:4]))


if __name__ == "__main__":
    main()
