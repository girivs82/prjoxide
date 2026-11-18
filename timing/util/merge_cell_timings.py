"""
Merge cell timing tables extracted from a separate set of designs (extract_cell_timings.py --out=DIR)
into a family's timing/cells_<grade>.json: cell types the tables do not have yet are added; cell
types they already have are left as they are, and how the new designs' values compare is reported.

Used for the LFCPNX DDR blocks (DQSBUF, DDRDLL, ECLKSYNC, ECLKDIV, the x4 DQ IO logic), extracted
from a Radiant build of a DDR PHY, without re-extracting every other design.

Usage: merge_cell_timings.py <dir with cells_<grade>.json> <family>
"""
import json
import os
import sys

import database
from timing_config import families


def arcs(v):
    a = {("iopath", p["from_pin"], p["to_pin"]): (p["minv"], p["maxv"]) for p in v["iopaths"]}
    a.update({("check", p["pin"], p["clock"]): (p["min_setup"], p["max_setup"], p["min_hold"], p["max_hold"])
              for p in v["setupholds"]})
    return a


def main():
    src, family = sys.argv[1], sys.argv[2]
    root = os.path.join(database.get_db_root(), family, "timing")
    for g in families[family]["speedgrades"]:
        fn = os.path.join(root, "cells_{}.json".format(g))
        db = json.load(open(fn))
        new = json.load(open(os.path.join(src, "cells_{}.json".format(g))))["celltypes"]
        added, kept = [], []
        for ct, v in sorted(new.items()):
            if ct in db["celltypes"]:
                a, b = arcs(db["celltypes"][ct]), arcs(v)
                diff = sorted(k for k in set(a) & set(b) if a[k] != b[k])
                kept.append("{} ({} arcs only in the new designs, {} with other values)".format(
                    ct, len(set(b) - set(a)), len(diff)))
                continue
            db["celltypes"][ct] = v
            added.append(ct)
        with open(fn, "w") as f:
            json.dump(db, f, sort_keys=True, indent=4)
        print("grade {}: added {}".format(g, ", ".join(added) or "nothing"))
        if kept:
            print("    kept existing: " + "; ".join(kept))


if __name__ == "__main__":
    main()
