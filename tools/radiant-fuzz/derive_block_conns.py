#!/usr/bin/env python3
"""
Write fixed connections confirmed by Radiant-routed LFCPNX designs into LFCPNX tile types that
have none yet (the EBR, LRAM and DSP tiles' connections between CIB wires and the block's pins).

Input: the *.ref_arcs.json files that timing/util/extract_route_cram.py writes next to each
route pickle. They list the LIFCL tile type arcs (candidates for an LFCPNX tile type with no
routing) that the extractor used, with a count:
  "traced":    on an SDF interconnect arc traced from its sink pin back to its source pin;
  "sink_side": between a sink pin and the first node a set pip drives, on an arc whose source
               was not reached (e.g. a block clock pin whose clock route is lost at a TAP).

On LFCPNX a block output drives the CIB's J*_CIBTEST input, which reaches the CIB wire through a
J* <- J*_CIBTEST pip, where LIFCL connects the block pin to the CIB wire directly; the extractor
already reports such arcs with the _CIBTEST name.

Usage: derive_block_conns.py <timing output dir> <tile type> [...]
"""
import glob
import json
import re
import sys
from collections import defaultdict
from os import path

sys.path.insert(0, path.join(path.dirname(__file__), "..", "..", "util", "common"))
import database  # noqa: E402


def main():
    folder, types = sys.argv[1], set(sys.argv[2:])
    conns = defaultdict(lambda: defaultdict(int))
    for f in glob.glob(path.join(folder, "*.ref_arcs.json")):
        d = json.load(open(f))
        for kind in ("traced", "sink_side"):
            for tt, to, fw, n in d[kind]:
                if tt in types:
                    conns[tt][to, fw] += n
    for tt in sorted(types):
        fn = path.join(database.get_db_root(), "LFCPNX", "tiletypes", tt + ".ron")
        t = open(fn).read()
        if "\n  conns: {},\n" not in t:
            raise SystemExit("{} already has conns; not overwriting".format(tt))
        by_to = defaultdict(list)
        for to, fw in sorted(conns[tt]):
            by_to[to].append(fw)
        body = "".join('    "{}": [\n{}    ],\n'.format(
            to, "".join('      (\n        from_wire: "{}",\n      ),\n'.format(fw) for fw in fws))
            for to, fws in sorted(by_to.items()))
        t = t.replace("\n  conns: {},\n", "\n  conns: {\n" + body + "  },\n")
        open(fn, "w").write(t)
        print("{}: {} conns".format(tt, len(conns[tt])))


if __name__ == "__main__":
    main()
