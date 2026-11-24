#!/usr/bin/env python3
"""
Infer the fixed connections between CIB wires and the fabric pins of an LFCPNX edge block from
Radiant-routed designs, with the method of infer_adc_conns.py / infer_block_conns.py:

- an input pin: the CIBMUX / CE / LSR / CLK wires near the block that the source register's net
  reaches are its candidates;
- an output pin: the wires near the block where the route to the capturing register starts.

Per pin, the candidates of all arcs are intersected. A pin is written only when exactly one wire is
left and at least MIN_ARCS arcs agree, every arc offering it.

Clock outputs (--clock-out=PIN,...): their route to a clocked register is traced backward to where it
starts (the wires with no driver in the decoded routing). The global wires (G:) that start every arc
of a pin are its candidates. They are assigned iteratively: a pin with exactly one candidate not yet
taken by another pin gets it (a clocked register's CLK pin key can cover both clock inputs of its
slice, so one pin's arcs may also show another pin's global). With --write each assigned pin is
written as G:<wire> <- the pin wire.

Blocks (pin wires named as in LIFCL's tile types, relative to the block's tile):
  adc       ADC_CORE_R68C158, tile ADC at the site's column + 1: W1:J<pin>_ADC_CORE_ADC0
  osc       OSC_CORE_R1C137, tile EFB_1_OSC one row above the site: S1:J<pin>_OSC_CORE
  eclksync  ECLKSYNC_CORE_R73C<c><A-D> (bank 3 / 4 / 5 at C74 / C73 / C72, edge clock 0-3), tile one
            row below (BMID_1_ECLK_2 / BMID_0_ECLK_1 / ECLK_0): N1:J<pin>_ECLKSYNC_CORE_ECLKSYNC<bank>_<k>
  eclkdiv   ECLKDIV_CORE_R73C<c><A-D>, the same tiles: N1:J<pin>_ECLKDIV_CORE_ECLKDIVB<bank>_<k>
A cell pinned by the design's own `ldc_set_location -site {...} [get_cells ...]` constraint is at that
site (it overrides the timing report); an unsited block cell gets the one block site the report names.

Usage (in the container, PYTHONPATH with util/common, util/fuzz, timing/util and this directory):
  infer_edge_block_conns.py <block> <out.json> <design dir>... [--write] [--runs=A-B] [--clock-out=P,...]
                            [--clock-sink=PIN,...]
--clock-sink limits the clock-output trace to arcs into those sink pins (e.g. CLK of fabric registers;
an IOLOGIC's SCLK pin key does not resolve to one route).
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

MIN_ARCS = 10

ECLK_BANK = {74: 3, 73: 4, 72: 5}
ECLK_TILES = {"ECLK_0", "BMID_0_ECLK_1", "BMID_1_ECLK_2"}
BLOCKS = {
    # site regex, tile types, (tile row - site row, tile col - site col), pin wire suffix (from the site
    # match), marker of the block's pin wires (a backward trace stops there), cell regex
    "adc": (re.compile(r'^ADC_CORE(?:_ADC_CORE)?_R(\d+)C(\d+)$'), {"ADC"}, (0, 1),
            lambda m: "_ADC_CORE_ADC0", "_ADC_CORE_", re.compile(r'ADC_inst$')),
    "osc": (re.compile(r'^OSC_CORE(?:_OSC_CORE)?_R(\d+)C(\d+)$'), {"EFB_1_OSC"}, (-1, 0),
            lambda m: "_OSC_CORE", "_OSC_CORE", re.compile(r'OSCA_inst$')),
    "eclksync": (re.compile(r'^ECLKSYNC_CORE(?:_ECLKSYNC_CORE)?_R(\d+)C(\d+)([A-D])$'), ECLK_TILES, (1, 0),
                 lambda m: "_ECLKSYNC_CORE_ECLKSYNC{}_{}".format(ECLK_BANK[int(m.group(2))], "ABCD".index(m.group(3))),
                 "_ECLKSYNC_CORE_", re.compile(r'ECLKSYNC_inst$')),
    "eclkdiv": (re.compile(r'^ECLKDIV_CORE(?:_ECLKDIV_CORE)?_R(\d+)C(\d+)([A-D])$'), ECLK_TILES, (1, 0),
                lambda m: "_ECLKDIV_CORE_ECLKDIVB{}_{}".format(ECLK_BANK[int(m.group(2))], "ABCD".index(m.group(3))),
                "_ECLKDIV_CORE_", re.compile(r'ECLKDIV_inst$')),
}


def main():
    block = sys.argv[1]
    site_re, tiletypes, (dr, dc), suffix_of, marker, cell_re = BLOCKS[block]
    out_json, write = sys.argv[2], "--write" in sys.argv
    runs, clock_out, clock_sink = None, [], None
    for a in sys.argv:
        if a.startswith("--runs="):
            lo, hi = a.split("=")[1].split("-")
            runs = set(range(int(lo), int(hi) + 1))
        if a.startswith("--clock-out="):
            clock_out = a.split("=")[1].split(",")
        if a.startswith("--clock-sink="):
            clock_sink = set(a.split("=")[1].split(","))
    dirs = [a for a in sys.argv[3:] if not a.startswith("--")]
    dev = E.Device(E.FAMILY, E.DEVICE)
    cands, counts = {}, defaultdict(int)
    votes = defaultdict(lambda: defaultdict(int))
    clock_reach = defaultdict(list)

    def block_tile(r, c):
        tr, tc = r + dr, c + dc
        for tt in dev.tiles_at.get((tr, tc), ()):
            if tt in tiletypes:
                return tt, tr, tc
        return None

    for d in dirs:
        name = re.search(r'^NAME=(\S+)', open(path.join(d, "Makefile")).read(), re.M).group(1)
        outdir = path.join(d, "..", "..", "..", "output", "LFCPNX")
        for fasm in sorted(glob.glob(path.join(d, "work", "design_*.fasm"))):
            i = re.search(r'design_(\w+)\.fasm', fasm).group(1)
            if runs and int(i) not in runs:
                continue
            vo = path.join(outdir, "{}_{}_9.vo".format(name, i))
            if not path.exists(vo):
                continue
            routing = E.Routing(dev, fasm)
            member2cell, cell2ports = E.parse_vo(vo)
            site = E.parse_twr([path.join(d, "work", "design_{}.twr".format(i))], member2cell)
            # the timing report names the block's site, but parse_twr may not tie it to the cell (the
            # oscillator's paths do not); give an unsited block cell the one block site the report names
            twr_sites = set()
            for t_ in re.findall(r'\b[A-Z_]+_R\d+C\d+\b', open(path.join(d, "work", "design_{}.twr".format(i))).read()):
                if site_re.match(t_):
                    twr_sites.add(t_)
            pdc = path.join(d, "work", "design_{}.pdc".format(i))
            pinned = dict((c_, s_) for s_, c_ in re.findall(r'ldc_set_location -site \{(\S+)\} \[get_cells (\S+)\]',
                                                           open(pdc).read())) if path.exists(pdc) else {}
            # a cell pinned by the design's constraints is at that site, whatever the report says
            site.update({c_: s_ for c_, s_ in pinned.items() if c_ in cell2ports})
            for cell in cell2ports:
                if cell not in site and cell_re.search(cell) and len(twr_sites) == 1:
                    site[cell] = next(iter(twr_sites))
            port2site, pin2site = E.parse_pad(path.join(d, "work", "design_{}.tmp".format(i), "par.pad"))
            for cell, ports in cell2ports.items():
                for p in ports:
                    if port2site.lookup(p):
                        site[cell] = port2site.lookup(p)
            sdf = parse_sdf_file(vo[:-3] + ".sdf").cells["top"]
            arcs = [(tuple(E.unescape(x) for x in f.rsplit("/", 1)), tuple(E.unescape(x) for x in t.rsplit("/", 1)))
                    for f, t in sorted(sdf.interconnect.keys())]
            E.place_from_routing(dev, routing, arcs, site)
            fw = B.Forward(dev, routing)
            reach_cache = {}

            def drv(k):
                # the database's own pin connections of this block (if any) end a backward trace
                return [s_ for s_ in routing.drivers(k)
                        if not (isinstance(s_[-1], str) and marker in s_[-1])]

            # clock outputs: per SDF arc from the pin, the wires where the route to the clocked
            # register starts (wires of the decoded routing with no driver), traced backward
            for (scell, spin), (dcell, dpin) in arcs:
                if spin not in clock_out or scell not in site or dcell not in site:
                    continue
                if clock_sink and dpin not in clock_sink:
                    continue
                m_ = site_re.match(site[scell])
                if not m_:
                    continue
                t_ = block_tile(int(m_.group(1)), int(m_.group(2)))
                if t_ is None:
                    continue
                inst = (t_[0], spin, suffix_of(m_), int(m_.group(1)), int(m_.group(2)), t_[1], t_[2])
                roots = set()
                for dk in E.pin_keys(dev, site[dcell], dpin, routing, {}):
                    seen, fr = {dk}, [dk]
                    while fr and len(seen) < 20000:
                        nx = []
                        for k in fr:
                            for s_ in drv(k):
                                if s_ not in seen:
                                    seen.add(s_)
                                    nx.append(s_)
                        fr = nx
                    roots |= {k for k in seen if not drv(k)}
                clock_reach[inst].append(roots)

            for src, dst in arcs:
                for (cell, pin), other, is_input in ((dst, src, True), (src, dst, False)):
                    if cell not in site or other[0] not in site:
                        continue
                    m = site_re.match(site[cell])
                    if not m:
                        continue
                    r, c = int(m.group(1)), int(m.group(2))
                    t = block_tile(r, c)
                    if t is None:
                        continue
                    tt, tr, tc = t
                    suffix = suffix_of(m)
                    pin_w = ("W", r, c, "J{}{}".format(pin, suffix))
                    if is_input:
                        sk = frozenset(E.pin_keys(dev, site[other[0]], other[1], routing, {}))
                        if not sk:
                            continue
                        if sk not in reach_cache:
                            reach_cache[sk] = fw.reach(sk)
                        cs = {(B.rel(pin_w, tr, tc), B.rel(k, tr, tc)) for k in reach_cache[sk]
                              if B.near(k, r, c, dev) and B.INPUT_WIRE_RE.match(k[3])}
                    else:
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
                                   if B.near(k, r, c, dev) and not drv(k)}
                    if not cs:
                        continue
                    key = (tt, pin + suffix, "in" if is_input else "out")
                    cands[key] = cs if key not in cands else cands[key] & cs
                    counts[key] += 1
                    for c_ in cs:
                        votes[key][c_] += 1
    result, report = defaultdict(list), {}
    for (tt, pin, dr_), cs in sorted(cands.items()):
        n = counts[tt, pin, dr_]
        ranked = sorted(votes[tt, pin, dr_].items(), key=lambda kv: -kv[1])
        unan = len(cs) == 1 and ranked[0][1] == n and n >= MIN_ARCS
        report["{} {} {}".format(tt, pin, dr_)] = dict(arcs=n, candidates=sorted(cs), unanimous=unan,
                                                       votes=[[list(c_), v] for c_, v in ranked[:4]])
        if unan:
            to, frm = next(iter(cs))
            result[tt].append((to, frm, pin, dr_))
    clocks = {}
    common = {pin: (set.intersection(*sets) if sets else set()) for pin, sets in clock_reach.items()}
    cand = {pin: {k for k in v if k[0] == "G"} for pin, v in common.items()
            if len(clock_reach[pin]) >= MIN_ARCS}
    assigned = {}
    changed = True
    while changed:
        changed = False
        taken = set(assigned.values())
        for pin in sorted(cand):
            left = cand[pin] - taken
            if pin not in assigned and len(left) == 1:
                assigned[pin] = next(iter(left))
                taken.add(assigned[pin])
                changed = True
    for inst, sets in clock_reach.items():
        tt, pin, sfx, r, c, tr, tc = inst
        label = pin + sfx
        clocks[label] = dict(arcs=len(sets), common=sorted(str(x) for x in common[inst]),
                             conn=("G:" + assigned[inst][1]) if inst in assigned else None)
        if clocks[label]["conn"]:
            result[tt].append((clocks[label]["conn"], B.rel(("W", r, c, "J" + label), tr, tc), label, "clock"))
    json.dump(dict(conns={k: sorted(v) for k, v in result.items()}, report=report, clock_out=clocks),
              open(out_json, "w"), indent=1)
    for tt in sorted(result):
        print("{}: {} pins resolved".format(tt, len(result[tt])))
        for to, frm, pin, dr_ in sorted(result[tt], key=lambda x: x[2]):
            print("   {:9s} {:3s} {} <- {}".format(pin, dr_, to, frm))
    unres = [k for k, v in report.items() if not v["unanimous"]]
    print("{} pins not resolved: {}".format(len(unres), ", ".join(sorted(unres))))
    for pin, v in clocks.items():
        print("clock output {}: {} arcs, route start shared by all: {}; connection: {}".format(
            pin, v["arcs"], v["common"][:12], v["conn"]))
    if write:
        for tt in sorted(result):
            B.write_conns(tt, [(to, frm) for to, frm, pin, dr_ in result[tt]])


if __name__ == "__main__":
    main()
