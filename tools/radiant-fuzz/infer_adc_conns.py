#!/usr/bin/env python3
"""
Infer the fixed connections between CIB wires and the LFCPNX ADC's fabric pins (ADC_CORE, site
ADC_CORE_R68C158, tile CIB_R68C159:ADC) from Radiant-routed designs
(timing/fuzzers/LFCPNX/15-adc-pins), with the method of infer_block_conns.py / infer_dqsbuf_conns.py:

- an input pin: the CIBMUX / CE / LSR / CLK wires near the block that the source register's net
  reaches are its candidates;
- an output pin: the wires near the block where the route to the capturing register starts.

Per pin, the candidates of all arcs are intersected. A pin is written only when exactly one wire is
left and at least MIN_ARCS arcs agree, every arc offering it. Pin wires are named as in LIFCL's ADC
tile type: W1:J<pin>_ADC_CORE_ADC0, relative to the ADC tile (the site is one column left of it).

Usage (in the container, PYTHONPATH with util/common, util/fuzz, timing/util and this directory):
  infer_adc_conns.py <out.json> <design dir>... [--write] [--runs=A-B]
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

SITE_RE = re.compile(r'^ADC_CORE(?:_ADC_CORE)?_R(\d+)C(\d+)$')
MIN_ARCS = 10
# --runs A-B: only those runs (to judge a batch on its own)
RUNS = None


def adc_tile(dev, r, c):
    for tt in dev.tiles_at.get((r, c + 1), ()):
        if tt == "ADC":
            return tt, r, c + 1
    return None


def main():
    global RUNS
    out_json, write = sys.argv[1], "--write" in sys.argv
    for a in sys.argv:
        if a.startswith("--runs="):
            lo, hi = a.split("=")[1].split("-")
            RUNS = set(range(int(lo), int(hi) + 1))
    dirs = [a for a in sys.argv[2:] if not a.startswith("--")]
    dev = E.Device(E.FAMILY, E.DEVICE)
    cands, counts = {}, defaultdict(int)
    votes = defaultdict(lambda: defaultdict(int))
    for d in dirs:
        name = re.search(r'^NAME=(\S+)', open(path.join(d, "Makefile")).read(), re.M).group(1)
        outdir = path.join(d, "..", "..", "..", "output", "LFCPNX")
        for fasm in sorted(glob.glob(path.join(d, "work", "design_*.fasm"))):
            i = re.search(r'design_(\w+)\.fasm', fasm).group(1)
            if RUNS and int(i) not in RUNS:
                continue
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
            sdf = parse_sdf_file(vo[:-3] + ".sdf").cells["top"]
            arcs = [(tuple(E.unescape(x) for x in f.rsplit("/", 1)), tuple(E.unescape(x) for x in t.rsplit("/", 1)))
                    for f, t in sorted(sdf.interconnect.keys())]
            E.place_from_routing(dev, routing, arcs, site)
            fw = B.Forward(dev, routing)
            reach_cache = {}

            def drv(k):
                # the database's own ADC pin connections (if any) end a backward trace
                return [s_ for s_ in routing.drivers(k)
                        if not (s_[0] == "W" and isinstance(s_[3], str) and s_[3].endswith("_ADC_CORE_ADC0"))]

            for src, dst in arcs:
                for (cell, pin), other, is_input in ((dst, src, True), (src, dst, False)):
                    if cell not in site or other[0] not in site:
                        continue
                    m = SITE_RE.match(site[cell])
                    if not m:
                        continue
                    r, c = int(m.group(1)), int(m.group(2))
                    t = adc_tile(dev, r, c)
                    if t is None:
                        continue
                    tt, tr, tc = t
                    pin_w = ("W", r, c, "J{}_ADC_CORE_ADC0".format(pin))
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
                    key = (tt, pin, "in" if is_input else "out")
                    cands[key] = cs if key not in cands else cands[key] & cs
                    counts[key] += 1
                    for c_ in cs:
                        votes[key][c_] += 1
    result, report = defaultdict(list), {}
    for (tt, pin, dr), cs in sorted(cands.items()):
        n = counts[tt, pin, dr]
        ranked = sorted(votes[tt, pin, dr].items(), key=lambda kv: -kv[1])
        unan = len(cs) == 1 and ranked[0][1] == n and n >= MIN_ARCS
        report["{} {} {}".format(tt, pin, dr)] = dict(arcs=n, candidates=sorted(cs), unanimous=unan,
                                                      votes=[[list(c_), v] for c_, v in ranked[:4]])
        if unan:
            to, frm = next(iter(cs))
            result[tt].append((to, frm, pin, dr))
    json.dump(dict(conns={k: sorted(v) for k, v in result.items()}, report=report), open(out_json, "w"), indent=1)
    for tt in sorted(result):
        print("{}: {} pins resolved".format(tt, len(result[tt])))
        for to, frm, pin, dr in sorted(result[tt], key=lambda x: x[2]):
            print("   {:9s} {:3s} {} <- {}".format(pin, dr, to, frm))
    unres = [k for k, v in report.items() if not v["unanimous"]]
    print("{} pins not resolved: {}".format(len(unres), ", ".join(sorted(unres))))
    if write:
        for tt in sorted(result):
            B.write_conns(tt, [(to, frm) for to, frm, pin, dr in result[tt]])


if __name__ == "__main__":
    main()
