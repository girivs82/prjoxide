#!/usr/bin/env python3
"""
Fill the empty routing (pips and/or fixed connections) of LFCPNX tile types that have no LIFCL
twin from an already filled and checked LFCPNX sibling: a variant of the same IO tile (e.g.
SYSIO_B5_0_DQS1 from SYSIO_B5_0) whose tile wires are named the same. Only sections that are
empty in the target are written; enums and words are left alone. The result is to be confirmed
with Radiant-routed designs that use the target tiles.

Usage: fill_from_sibling.py [--dry-run] <target>=<sibling>[:pips|:conns] ...
"""
import re
import sys
from os import path

sys.path.insert(0, path.join(path.dirname(__file__), "..", "..", "util", "common"))
import database  # noqa: E402


def section(t, name):
    """(start, end) of a top-level section 'name: {...},' in a .ron tile type."""
    i = t.index("\n  {}: {{".format(name))
    if t[i:].startswith("\n  {}: {{}},".format(name)):
        return i, i + len("\n  {}: {{}},".format(name))
    j = t.index("\n  },", i) + len("\n  },")
    return i, j


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    root = database.get_db_root()
    for a in [x for x in args if x != "--dry-run"]:
        tgt, _, rest = a.partition("=")
        sib, _, what = rest.partition(":")
        parts = [what] if what else ["pips", "conns"]
        fn = path.join(root, "LFCPNX", "tiletypes", tgt + ".ron")
        t = open(fn).read()
        s = open(path.join(root, "LFCPNX", "tiletypes", sib + ".ron")).read()
        for p in parts:
            ti, tj = section(t, p)
            si, sj = section(s, p)
            if t[ti:tj].strip() != "{}: {{}},".format(p):
                print("{}: {} not empty, kept".format(tgt, p))
                continue
            n = s[si:sj].count("from_wire")
            t = t[:ti] + s[si:sj] + t[tj:]
            print("{}: {} {} from {}".format(tgt, n, p, sib))
        if not dry:
            open(fn, "w").write(t)


if __name__ == "__main__":
    main()
