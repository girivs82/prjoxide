"""
LFCPNX DLLDEL (PCLK input delay cell) timing from the 22-dlldel designs' SDF, which the route
extractor cannot trace (the pad -> DLLDEL CLKIN connection is dedicated and has no routing):
  - interconnect class "io33 -> dlldel": the pad's PADDI -> DLLDEL CLKIN arc (a single dedicated
    connection, so the arc delay is the class delay);
  - cell "DLLDEL": its CLKIN -> CLKOUT arc, into cells_<grade>.json (the "dlldel_internal" pip of a
    route through the cell is a zero-delay class, as the cell arc carries the delay).
Usage: add_dlldel_timing.py <output dir> [family]   (NAME = dlldel designs: <dir>/dlldel_<n>_<grade>.sdf)
"""
import glob
import json
import os
import re
import sys
from os import path

import database
from parse_sdf import parse_sdf_file
from timing_config import families


def main():
    out, family = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "LFCPNX"
    root = path.join(database.get_db_root(), family, "timing")
    for g in families[family]["speedgrades"]:
        ic, cell = [], []
        for sdf in glob.glob(path.join(out, "dlldel_*_{}.sdf".format(g))):
            top = parse_sdf_file(sdf).cells
            for (f, t), d in top["top"].interconnect.items():
                if f.endswith("/PADDI") and "DLLDEL" in t and t.endswith("/CLKIN"):
                    ic.append((min(d.rising.minv, d.falling.minv), max(d.rising.maxv, d.falling.maxv)))
        # the cell arc, read directly from the SDF text (one DLLDEL instance per design)
        for sdf in glob.glob(path.join(out, "dlldel_*_{}.sdf".format(g))):
            t = open(sdf).read()
            m = re.search(r'CELLTYPE "\w*DLLDEL\w*".*?IOPATH CLKIN CLKOUT \((\d+):\d+:(\d+)\)\((\d+):\d+:(\d+)\)', t, re.S)
            if m:
                a, b, c_, d_ = map(int, m.groups())
                cell.append((min(a, c_), max(b, d_)))
        if not ic or not cell:
            print("grade {}: no DLLDEL arcs".format(g))
            continue
        fn = path.join(root, "interconnect_{}.json".format(g))
        j = json.load(open(fn))
        j["pip_classes"]["io33 -> dlldel"] = dict(base=[min(x for x, _ in ic), max(y for _, y in ic)])
        json.dump(j, open(fn, "w"), indent=4, sort_keys=True)
        fn = path.join(root, "cells_{}.json".format(g))
        j = json.load(open(fn))
        j["celltypes"]["DLLDEL"] = dict(iopaths=[dict(from_pin="CLKIN", to_pin="CLKOUT",
                                                      minv=min(x for x, _ in cell), maxv=max(y for _, y in cell))],
                                        setupholds=[])
        json.dump(j, open(fn, "w"), sort_keys=True, indent=4)
        print("grade {}: io33 -> dlldel {}, DLLDEL CLKIN->CLKOUT {}".format(
            g, j and [min(x for x, _ in ic), max(y for _, y in ic)], [min(x for x, _ in cell), max(y for _, y in cell)]))


if __name__ == "__main__":
    main()
