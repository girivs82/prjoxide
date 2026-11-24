#!/usr/bin/env python3
"""
Infer the fixed connections between CIB wires and the LFCPNX EBR (EBR_CORE) pins from Radiant-routed
designs (timing/fuzzers/LFCPNX/19-ebr-pins: many EBRs, every pin on its own register).

Same method as infer_block_conns.py (LRAM): for every SDF interconnect arc into an EBR input pin, the
CIBMUX outputs and CE/LSR/CLK wires near the block that the source's net reaches are the candidates
for that pin's driver; for an output pin, the undriven CIBTEST wires near the block where the sink's
route starts. Per (tile type, pin) the candidates of all arcs are intersected (or voted, --vote).

An EBR_CORE site R<r>C<c> belongs to the EBR_1 / EBR_4 / EBR_7 / EBR_9 tile at R<r+1>C<c+1> (the
tile types' pin wires are N1W1:J<pin>_EBR_CORE); the site -> tile match is checked and reported.

Output pins: the route from an EBR output to its capture register starts at a CIB wire that only the
tile type's fixed connections drive, so tracing it backward ends at the EBR pin through those
connections. --check counts, per (tile type, output pin), the arcs whose backward trace ends at the
very pin the SDF names (confirmed) and those ending anywhere else (contradicted).

--check: compare the inferred connections with the database's (from LIFCL).
--replace: replace the database's connection of each pin resolved unanimously by at least
MIN_REPLACE_ARCS arcs (the pin's old connections in that tile type are removed).

Usage (in the container, PYTHONPATH with util/common, util/fuzz and timing/util):
  infer_ebr_conns.py <out.json> <design dir>... [--vote] [--check] [--replace]
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

SITE_RE = re.compile(r'^EBR_CORE(?:_EBR_CORE)?_R(\d+)C(\d+)$')
EBR_TTS = ("EBR_1", "EBR_4", "EBR_7", "EBR_9")
WINDOW = 12
INPUT_WIRE_RE = re.compile(r'^J(CIBMUXOUT[A-D]\d|CE\d|LSR\d|CLK\d)$')
# CIB wires an EBR output drives (the tile types' conns list both J<F|Q>n and J<F|Q>n_CIBTEST)
OUTPUT_WIRE_RE = re.compile(r'^J[FQ]\d+(_CIBTEST)?$')
MIN_ARCS = 2
MIN_REPLACE_ARCS = 3


def ebr_tile(dev, r, c):
    for tt in EBR_TTS:
        if (r + 1, c + 1) in dev.tiles_of.get(tt, ()):
            return tt, r + 1, c + 1
    return None


def near(k, r, c):
    return k[0] == "W" and abs(k[1] - r) <= 2 and abs(k[2] - c) <= WINDOW


def db_conns(tt):
    import database
    t = open(path.join(database.get_db_root(), "LFCPNX", "tiletypes", tt + ".ron")).read()
    ci = t.index("\n  conns: {")
    ce = t.index("\n  },\n", ci)
    out = defaultdict(set)      # pin -> {(to, from)}
    for to, body in re.findall(r'\n    "([^"]+)": \[(.*?)\n    \],', t[ci:ce], re.S):
        for fw in re.findall(r'from_wire: "([^"]+)"', body):
            for w, other, d in ((fw, to, "in_to"), (to, fw, "out_from")):
                m = re.search(r'J(\w+?)_EBR_CORE$', w)
                if m:
                    out[m.group(1)].add((to, fw))
    return out


def replace_conns(tt, pin, new):
    """Drop every connection of tt that involves J<pin>_EBR_CORE, add the new (to, from)."""
    import database
    fn = path.join(database.get_db_root(), "LFCPNX", "tiletypes", tt + ".ron")
    t = open(fn).read()
    ci = t.index("\n  conns: {")
    ce = t.index("\n  },\n", ci) + len("\n  },\n")
    head, rest, tail = t[:ci], t[ci:ce], t[ce:]
    have = defaultdict(list)
    pw = re.compile(r'(^|:)J{}_EBR_CORE$'.format(re.escape(pin)))
    for to, body in re.findall(r'\n    "([^"]+)": \[(.*?)\n    \],', rest, re.S):
        for fw in re.findall(r'from_wire: "([^"]+)"', body):
            if pw.search(to) or pw.search(fw):
                continue
            have[to].append(fw)
    to, frm = new
    if frm not in have[to]:
        have[to].append(frm)
    body = "".join('    "{}": [\n{}    ],\n'.format(
        t_, "".join('      (\n        from_wire: "{}",\n      ),\n'.format(fw) for fw in sorted(fws)))
        for t_, fws in sorted(have.items()) if fws)
    open(fn, "w").write(head + "\n  conns: {\n" + body + "  },\n" + tail)


def main():
    out_json = sys.argv[1]
    vote, check, replace = "--vote" in sys.argv, "--check" in sys.argv, "--replace" in sys.argv
    dirs = [a for a in sys.argv[2:] if not a.startswith("--")]
    dev = E.Device(E.FAMILY, E.DEVICE)
    cands, counts = {}, defaultdict(int)
    votes = defaultdict(lambda: defaultdict(int))
    sites_seen, unmatched = defaultdict(int), set()
    out_chk = defaultdict(lambda: defaultdict(int))
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
            sdf = parse_sdf_file(vo[:-3] + ".sdf").cells["top"]
            arcs = [(tuple(E.unescape(x) for x in f.rsplit("/", 1)), tuple(E.unescape(x) for x in t.rsplit("/", 1)))
                    for f, t in sorted(sdf.interconnect.keys())]
            E.place_from_routing(dev, routing, arcs, site)
            fw = B.Forward(dev, routing)
            reach_cache = {}
            for src, dst in arcs:
                if src[0] not in site or dst[0] not in site:
                    continue
                for (cell, pin), other, is_input in ((dst, src, True), (src, dst, False)):
                    m = SITE_RE.match(site[cell])
                    if not m:
                        continue
                    r, c = int(m.group(1)), int(m.group(2))
                    t = ebr_tile(dev, r, c)
                    if t is None:
                        unmatched.add(site[cell])
                        continue
                    tt, tr, tc = t
                    sites_seen[(tt, site[cell])] += 1
                    pin_w = ("W", r, c, "J{}_EBR_CORE".format(pin))
                    if not is_input and check:
                        ends = set()
                        for dk in E.pin_keys(dev, site[other[0]], other[1], routing, {}):
                            parent, fr = {dk}, [dk]
                            while fr and len(parent) < 20000:
                                nx = []
                                for k in fr:
                                    for s_ in routing.drivers(k):
                                        if s_ not in parent:
                                            parent.add(s_)
                                            nx.append(s_)
                                fr = nx
                            ends |= {k for k in parent if not routing.drivers(k)}
                        out_chk[(tt, pin)]["confirmed" if pin_w in ends else "contradicted"] += 1
                    if is_input:
                        sk = frozenset(E.pin_keys(dev, site[other[0]], other[1], routing, {}))
                        if not sk:
                            continue
                        if sk not in reach_cache:
                            reach_cache[sk] = fw.reach(sk)
                        cs = {(B.rel(pin_w, tr, tc), B.rel(k, tr, tc)) for k in reach_cache[sk]
                              if near(k, r, c) and INPUT_WIRE_RE.match(k[3])}
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
                            cs |= {(B.rel(k, tr, tc), B.rel(pin_w, tr, tc)) for k in parent
                                   if near(k, r, c) and OUTPUT_WIRE_RE.match(k[3]) and not routing.drivers(k)}
                    key = (tt, pin, "in" if is_input else "out")
                    if not cs:
                        continue
                    cands[key] = cs if key not in cands else cands[key] & cs
                    counts[key] += 1
                    for c_ in cs:
                        votes[key][c_] += 1
    result, report = {}, {}
    for (tt, pin, dr), cs in sorted(cands.items()):
        n = counts[tt, pin, dr]
        ranked = sorted(votes[tt, pin, dr].items(), key=lambda kv: -kv[1])
        rep = dict(arcs=n, candidates=sorted(cs), votes=[[list(c_), v] for c_, v in ranked[:4]])
        if len(cs) == 1 and n >= MIN_ARCS:
            result[(tt, pin)] = (next(iter(cs)), n, True)
        elif vote and ranked and n >= B.MIN_VOTE_ARCS and ranked[0][1] >= B.VOTE_SHARE * n and \
                (len(ranked) < 2 or ranked[1][1] <= B.RUNNER_UP_SHARE * n):
            result[(tt, pin)] = (ranked[0][0], n, False)
            rep["by_vote"] = True
        report["{} {} {}".format(tt, pin, dr)] = rep
    cmp = {}
    if check or replace:
        for tt in EBR_TTS:
            have = db_conns(tt)
            for (tt_, pin), (conn, n, unan) in sorted(result.items()):
                if tt_ != tt:
                    continue
                old = sorted(have.get(pin, ()))
                if pin.startswith("DO"):
                    st = "same" if tuple(conn) in {tuple(o) for o in old} else "missing" if not old else "different"
                else:
                    st = "same" if (tuple(conn) in {tuple(o) for o in old} and len(old) == 1) else \
                         "missing" if not old else "different"
                cmp["{} {}".format(tt, pin)] = dict(inferred=list(conn), arcs=n, unanimous=unan, db=old, status=st)
                if replace and st != "same" and unan and n >= MIN_REPLACE_ARCS:
                    replace_conns(tt, pin, conn)
    json.dump(dict(conns={"{} {}".format(*k): [list(v[0]), v[1], v[2]] for k, v in sorted(result.items())},
                   compare=cmp, report=report,
                   outputs={"{} {}".format(*k): dict(v) for k, v in sorted(out_chk.items())},
                   sites={"{} {}".format(*k): v for k, v in sorted(sites_seen.items())},
                   unmatched_sites=sorted(unmatched)), open(out_json, "w"), indent=1)
    by_tt = defaultdict(int)
    for (tt, pin) in result:
        by_tt[tt] += 1
    print("resolved pins per tile type:", dict(by_tt))
    print("sites per tile type:", {tt: len({s for (t, s) in sites_seen if t == tt}) for tt in EBR_TTS})
    print("unmatched sites:", sorted(unmatched)[:8])
    if cmp:
        st = defaultdict(int)
        for v in cmp.values():
            st[v["status"]] += 1
        print("vs database:", dict(st))
    if out_chk:
        print("output pins: {} confirmed by {} arcs, {} with contradicting arcs".format(
            sum(1 for v in out_chk.values() if v["confirmed"]), sum(v["confirmed"] for v in out_chk.values()),
            sum(1 for v in out_chk.values() if v["contradicted"])))
    amb = sum(1 for v in report.values() if len(v["candidates"]) != 1 and not v.get("by_vote"))
    print("{} pins with several or no candidates".format(amb))


if __name__ == "__main__":
    main()
