#!/usr/bin/env python3
"""
Merge LIFCL's connections for a tile type into the LFCPNX tile type of the same name: keep every
LIFCL connection that no LFCPNX observation contradicts, i.e. unless the LFCPNX tile type (whose
connections come from Radiant-routed LFCPNX designs) has the same sink driven from a different
source; keep all LFCPNX connections. Unobserved LIFCL connections are kept, not dropped: LIFCL's
set is proven on silicon, and a connection the timing designs did not exercise is not evidence
against it.

Usage: union_block_conns.py [--dry-run] <tile type> [...]
"""
import re
import sys
from collections import defaultdict
from os import path

sys.path.insert(0, path.join(path.dirname(__file__), "..", "..", "util", "common"))
import database  # noqa: E402

BLOCK = re.compile(r'\n    "([^"]+)": \[(.*?)\n    \],', re.S)


def conns(fn):
    t = open(fn).read()
    ci = t.index("\n  conns: {")
    return t, ci, [(to, fw) for to, body in BLOCK.findall(t[ci:]) for fw in re.findall(r'from_wire: "([^"]+)"', body)]


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    root = database.get_db_root()
    for tt in [a for a in args if a != "--dry-run"]:
        _, _, ref = conns(path.join(root, "LIFCL", "tiletypes", tt + ".ron"))
        fn = path.join(root, "LFCPNX", "tiletypes", tt + ".ron")
        t, ci, have = conns(fn)
        src_of = defaultdict(set)
        for to, fw in have:
            src_of[to].add(fw)
        contradicted = [(to, fw) for to, fw in ref if src_of[to] and fw not in src_of[to]]
        added = [(to, fw) for to, fw in ref if (to, fw) not in set(have) and (to, fw) not in contradicted]
        confirmed = sum(1 for c in ref if c in set(have))
        print("{}: LIFCL {}, LFCPNX observed {}; LIFCL confirmed {}, contradicted {}, kept unobserved {}; "
              "LFCPNX-only {}".format(tt, len(ref), len(have), confirmed, len(contradicted), len(added),
                                      sum(1 for c in have if c not in set(ref))))
        for c in contradicted[:5]:
            print("   contradicted: {} <- {} (LFCPNX: {})".format(c[0], c[1], sorted(src_of[c[0]])))
        if dry or not added:
            continue
        by_to = defaultdict(list)
        for to, fw in have + added:
            by_to[to].append(fw)
        body = "".join('    "{}": [\n{}    ],\n'.format(
            to, "".join('      (\n        from_wire: "{}",\n      ),\n'.format(fw) for fw in sorted(fws)))
            for to, fws in sorted(by_to.items()))
        open(fn, "w").write(t[:ci] + "\n  conns: {\n" + body + "  },\n)\n")


if __name__ == "__main__":
    main()
