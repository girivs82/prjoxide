#!/usr/bin/env python3
"""
Infer the fixed connections between CIB wires and a hard block's pins (LFCPNX LRAM) from
Radiant-routed designs, where no reference tile type fits.

For every SDF interconnect arc of the designs that ends or starts at a block pin:
  - into a block input pin: the CIBMUX outputs and CE/LSR/CLK wires near the block that the
    source's net reaches
    (forward from the source pin through set pips, fixed connections, zero-bit options of
    otherwise undriven muxes, and edge turn-rounds) are candidates for that pin's driver;
  - from a block output pin: the undriven CIBTEST inputs near the block where the sink's route
    starts (backward from the sink pin) are candidates for the wire that pin drives.
Per block pin, the candidates of all its arcs are intersected; a pin whose intersection is a
single wire, agreed by at least MIN_ARCS arcs, gets that connection. Pins left with several candidates, or with none, are reported
and not written.

Usage (in the container, PYTHONPATH with util/common and timing/util):
  infer_block_conns.py <out.json> <design dir>... [--write]
where a design dir is a timing fuzzer directory (its work/design_N.* and the
timing/output/LFCPNX/<NAME>_N_9.* files are used).
"""
import glob
import json
import re
import sys
from collections import defaultdict
from os import path

import extract_route_cram as E
from parse_sdf import parse_sdf_file

# LFCPNX LRAM tile types: bel offset (rel_x, rel_y) from the tile, as in libprjoxide bels.rs
LRAM_OFFSETS = {"LRAM_0": (-1, 0), "LRAM_1": (-1, 0), "LRAM_2": (-1, 0), "LRAM_3": (1, 1),
                "LRAM_4": (0, 1), "LRAM_5": (0, 1), "LRAM_6": (0, 1)}
SITE_RE = re.compile(r'^LRAM_CORE(?:_LRAM_CORE)?_R(\d+)C(\d+)$')
WINDOW = 16
# CIB wires that can drive a block input: CIBMUX outputs and the control wires
INPUT_WIRE_RE = re.compile(r'^J(CIBMUXOUT[A-D]\d|CE\d|LSR\d|CLK\d)$')
MIN_ARCS = 2   # write a connection only when at least this many arcs agree on it


def lram_tile(dev, r, c):
    for tt, (dx, dy) in LRAM_OFFSETS.items():
        for tr, tc in dev.tiles_of.get(tt, ()):
            if (tr + dy, tc + dx) == (r, c):
                return tt, tr, tc
    return None


def near(k, r, c, dev):
    if k[0] != "W":
        return False
    if c >= dev.max_col - 2:          # right edge: a column of CIBs beside the block
        return abs(k[2] - c) <= 1 and abs(k[1] - r) <= WINDOW
    return abs(k[1] - r) <= 1 and abs(k[2] - c) <= WINDOW   # top edge: a row of CIBs below


def rel(k, tr, tc):
    dr, dc = k[1] - tr, k[2] - tc
    p = ("N{}".format(-dr) if dr < 0 else "S{}".format(dr) if dr > 0 else "") + \
        ("W{}".format(-dc) if dc < 0 else "E{}".format(dc) if dc > 0 else "")
    return (p + ":" if p else "") + k[3]


class Forward:
    """Forward reachability through the routing of one design."""
    def __init__(self, dev, routing):
        self.dev, self.routing = dev, routing
        self.fwd = defaultdict(set)
        for d, ss in routing.drv.items():
            for s_ in ss:
                self.fwd[s_].add(d)
        # fixed connections / zero-bit options by source wire name
        self.by_src = defaultdict(list)
        for name, ents in dev.by_dst().items():
            for tt, to, fw, kind in ents:
                if kind in ("conn", "zero"):
                    self.by_src[E.split_rel(fw)[1]].append((tt, to, fw))

    def succ(self, k):
        out = set(self.fwd.get(k, ()))
        if k[0] == "W":
            for tt, to, fw in self.by_src.get(k[3], ()):
                p = E.split_rel(fw)[0]
                m = E.DIR_RE.match(p)
                if not m:
                    continue
                ns, nd, ew, ed = m.groups()
                dr = (int(nd) if ns == "S" else -int(nd)) if ns else 0
                dc = (int(ed) if ew == "E" else -int(ed)) if ew else 0
                r, c = k[1] - dr, k[2] - dc
                if tt in self.dev.tiles_at.get((r, c), ()) and E.wire_key(self.dev, r, c, tt, fw) == k:
                    d = E.wire_key(self.dev, r, c, tt, to)
                    if d not in self.routing.drv:     # a set pip overrides a zero-bit option
                        out.add(d)
            # edge turn-round: the mirrored wire, if nothing else drives it
            for a in self.mirror(k):
                out.add(a)
        return out

    def mirror(self, k):
        m = self.routing.EDGE_WIRE_RE.match(k[3])
        if not m or not self.dev.near_edge(k[1], k[2]) or k not in self.routing.drv:
            return []
        hv, span, d, track = m.groups()
        flipped = hv + span + self.routing.FLIP[d] + track
        pos, top = (k[2], self.dev.max_col) if hv == "H" else (k[1], self.dev.max_row)
        total = 1 if pos <= self.dev.EDGE_MARGIN else 2 * top - 1
        a = ("W", k[1], total - pos, flipped) if hv == "H" else ("W", total - pos, k[2], flipped)
        return [a] if a not in self.routing.drv else []

    def reach(self, srcs, limit=200000):
        seen = set(srcs)
        fr = list(srcs)
        while fr and len(seen) < limit:
            nx = []
            for k in fr:
                for d in self.succ(k):
                    if d not in seen:
                        seen.add(d)
                        nx.append(d)
            fr = nx
        return seen


def write_conns(tt, conns):
    """Merge connections into an LFCPNX tile type's conns (existing entries are kept)."""
    import database
    fn = path.join(database.get_db_root(), "LFCPNX", "tiletypes", tt + ".ron")
    t = open(fn).read()
    ci = t.index("\n  conns: {")
    head, rest = t[:ci], t[ci:]
    have = defaultdict(list)
    for to, body in re.findall(r'\n    "([^"]+)": \[(.*?)\n    \],', rest, re.S):
        have[to] += re.findall(r'from_wire: "([^"]+)"', body)
    new = 0
    for to, frm in conns:
        if frm not in have[to]:
            have[to].append(frm)
            new += 1
    body = "".join('    "{}": [\n{}    ],\n'.format(
        to, "".join('      (\n        from_wire: "{}",\n      ),\n'.format(fw) for fw in sorted(fws)))
        for to, fws in sorted(have.items()))
    open(fn, "w").write(head + "\n  conns: {\n" + body + "  },\n)\n")
    print("  {}: {} new conns written".format(tt, new))


def main():
    out_json, dirs, write = sys.argv[1], [a for a in sys.argv[2:] if a != "--write"], "--write" in sys.argv
    dev = E.Device(E.FAMILY, E.DEVICE)
    cands = {}            # (tile type, to, from) candidate sets per (site, pin, dir)
    counts = defaultdict(int)
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
                    if p in port2site:
                        site[cell] = port2site[p]
            sdf = parse_sdf_file(vo[:-3] + ".sdf").cells["top"]
            arcs = [(tuple(E.unescape(x) for x in f.rsplit("/", 1)), tuple(E.unescape(x) for x in t.rsplit("/", 1)))
                    for f, t in sorted(sdf.interconnect.keys())]
            E.place_from_routing(dev, routing, arcs, site)
            fw = Forward(dev, routing)
            reach_cache = {}
            for src, dst in arcs:
                if src[0] not in site or dst[0] not in site:
                    continue
                for (cell, pin), other, is_input in ((dst, src, True), (src, dst, False)):
                    m = SITE_RE.match(site[cell])
                    if not m:
                        continue
                    r, c = int(m.group(1)), int(m.group(2))
                    t = lram_tile(dev, r, c)
                    if t is None:
                        continue
                    tt, tr, tc = t
                    pin_w = ("W", r, c, "J{}_LRAM_CORE".format(pin))
                    if is_input:
                        sk = frozenset(E.pin_keys(dev, site[other[0]], other[1], routing, {}))
                        if not sk:
                            continue
                        if sk not in reach_cache:
                            reach_cache[sk] = fw.reach(sk)
                        cs = {(rel(pin_w, tr, tc), rel(k, tr, tc)) for k in reach_cache[sk]
                              if near(k, r, c, dev) and INPUT_WIRE_RE.match(k[3])}
                    else:
                        cs = set()
                        for dk in E.pin_keys(dev, site[other[0]], other[1], routing, {}):
                            parent = {dk: None}
                            fr = [dk]
                            while fr and len(parent) < 20000:
                                nx = []
                                for k in fr:
                                    for s_ in routing.drivers(k):
                                        if s_ not in parent:
                                            parent[s_] = k
                                            nx.append(s_)
                                fr = nx
                            cs |= {(rel(k, tr, tc), rel(pin_w, tr, tc)) for k in parent
                                   if near(k, r, c, dev) and k[3].endswith("_CIBTEST") and not routing.drivers(k)}
                    key = (tt, pin, "in" if is_input else "out")
                    if not cs:
                        continue
                    cands[key] = cs if key not in cands else cands[key] & cs
                    counts[key] += 1
    result = defaultdict(list)
    report = {}
    for (tt, pin, dr), cs in sorted(cands.items()):
        report["{} {} {}".format(tt, pin, dr)] = dict(arcs=counts[tt, pin, dr], candidates=sorted(cs))
        if len(cs) == 1 and counts[tt, pin, dr] >= MIN_ARCS:
            to, frm = next(iter(cs))
            result[tt].append((to, frm, counts[tt, pin, dr]))
    json.dump(dict(conns={k: sorted(v) for k, v in result.items()}, report=report), open(out_json, "w"), indent=1)
    for tt in sorted(result):
        print("{}: {} pins resolved".format(tt, len(result[tt])))
        if write:
            write_conns(tt, [(to, frm) for to, frm, n in result[tt]])
    amb = sum(1 for v in report.values() if len(v["candidates"]) != 1)
    print("{} pins with several or no candidates".format(amb))


if __name__ == "__main__":
    main()
