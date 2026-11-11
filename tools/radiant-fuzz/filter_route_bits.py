#!/usr/bin/env python3
"""
Remove routing bits that leaked into SYSIO PIO enums.

The LFCPNX IO templates have to drive the pad's PADDO from a VHI, because
Radiant 2026.1's bitgen refuses an undriven net. The route from the VHI to the
pad sets pip bits in the CIB tile at the IO's location, and the enum fuzzer
attributes them to settings such as BASE_TYPE (compared with NONE, which has
no route). Every SYSIO tile shares its position with a CIB tile type whose pip
bits may be known, and LIFCL's tile of the same name carries the IO tile's
own pips (LFCPNX's SYSIO files have almost none). Any enum bit that is a pip
bit in either is routing, not IO configuration.

A first test (PR10A, SYSIO_B1_0_C) put no route bits in the IO tiles at all:
every changed bit matched a LIFCL PIOA enum bit. This is a safety net.

Usage: filter_route_bits.py <db root> [--dry-run]
Prints every removed bit. Rewrites database/LFCPNX/tiletypes/SYSIO_*.ron.
"""
import json
import os
import re
import sys

BIT = re.compile(r"\(frame:(\d+),bit:(\d+),invert:(true|false),\),")


def pip_bits(ron_text):
    pips = ron_text.split("enums:")[0]
    return {(int(f), int(b)) for f, b, _ in BIT.findall(pips)}


def main():
    root = sys.argv[1]
    dry = "--dry-run" in sys.argv
    fam = os.path.join(root, "LFCPNX")
    tiles = json.load(open(os.path.join(fam, "LFCPNX-100", "tilegrid.json")))["tiles"]
    at = {}
    for name, t in tiles.items():
        at.setdefault(name.split(":")[0], []).append(t["tiletype"])
    overlay = {}
    for name, t in tiles.items():
        if t["tiletype"].startswith("SYSIO"):
            overlay.setdefault(t["tiletype"], set()).update(
                x for x in at[name.split(":")[0]] if x.startswith("CIB"))
    for sysio, cibs in sorted(overlay.items()):
        path = os.path.join(fam, "tiletypes", sysio + ".ron")
        if not os.path.exists(path):
            continue
        route = set()
        lifcl = os.path.join(root, "LIFCL", "tiletypes", sysio + ".ron")
        if os.path.exists(lifcl):
            route |= pip_bits(open(lifcl).read())
        for cib in cibs:
            cpath = os.path.join(fam, "tiletypes", cib + ".ron")
            if os.path.exists(cpath):
                route |= pip_bits(open(cpath).read())
        text = open(path).read()
        if "enums:" not in text:
            continue
        head, enums = text.split("enums:", 1)
        removed = []

        def drop(m):
            fb = (int(m.group(1)), int(m.group(2)))
            if fb in route:
                removed.append(fb)
                return ""
            return m.group(0)

        new_enums = BIT.sub(drop, enums)
        if removed:
            print("{} (overlay {}): removed {} route bits: {}".format(
                sysio, ",".join(sorted(cibs)), len(removed), sorted(set(removed))))
            if not dry:
                open(path, "w").write(head + "enums:" + new_enums)
        else:
            print("{}: clean".format(sysio))


if __name__ == "__main__":
    main()
