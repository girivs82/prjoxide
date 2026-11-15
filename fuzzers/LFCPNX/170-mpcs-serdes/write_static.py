"""
Record the 9 static bits Radiant 2026.1 sets in every LFCPNX-100 design as always_on bits of their
tile types (the mechanism of the EBR / RBB static bits): the packer sets them in every bitstream and
the decoder counts them as known. Their function is unknown (probably defaults for unused SERDES /
PCS blocks); designs without them work on silicon. See README.md.

Creates SERDES_REFCLK.ron (the database had no data for that tile type). Re-running is a no-op.

Usage: write_static.py [database root]
"""
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")
STATIC = {
    "SERDES_REFCLK": [(0, 0), (1, 0), (2, 0), (3, 0), (10, 0)],   # CIB_R0C131
    "DOSCL_P18": [(6, 1), (11, 1)],                                # CIB_R68C0
    "PCS_1": [(0, 0)],                                             # CIB_R0C11
    "PCS_5": [(0, 0)],                                             # CIB_R0C79
}
EMPTY = "(\n  pips: {},\n  words: {},\n  enums: {},\n  conns: {},\n)"


def ron_list(bits):
    out = "  always_on: [\n"
    for f, b in sorted(bits):
        out += "    (\n      frame: %d,\n      bit: %d,\n      invert: false,\n    ),\n" % (f, b)
    return out + "  ],\n"


def main():
    for tt, bits in STATIC.items():
        fn = os.path.join(root, "LFCPNX", "tiletypes", tt + ".ron")
        t = open(fn).read() if os.path.exists(fn) else EMPTY
        if "\n  always_on: [" in t:
            print(tt, "present")
            continue
        assert t.rstrip().endswith(")")
        body = t.rstrip()[:-1]
        if not body.endswith("\n"):
            body += "\n"
        open(fn, "w").write(body + ron_list(bits) + ")")
        print(tt, "added", len(bits))


if __name__ == "__main__":
    main()
