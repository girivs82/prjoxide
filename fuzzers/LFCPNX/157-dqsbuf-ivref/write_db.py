"""
Write the bits found by this fuzzer (see README.md) into the LFCPNX tile types. Re-running is a no-op.

- DQSBUF.LPDDR4_BL16_EN (DQSBUF_IVREF's LPDDR4 BL16 mode): F55B1 of each DQS group's DQS0 tile.
- IOLOGIC<A|B>.OUTDELAYA (the pad's output / tristate pass through the OUTDELAYA delay line):
  F37B1 F38B1 F39B1, and IOLOGIC<A|B>.OUTDELAYA.MARGIN_TEST_ENABLE: F33B1 F35B1 F36B1, in every HP
  (bank 3 / 4 / 5) IO tile type. A tile type holds one pad: SYSIO_B<n>_0* is PIOA / IOLOGICA,
  SYSIO_B<n>_1* is PIOB / IOLOGICB.
(BMID_0_ECLK_1 F79B1-F82B1, first named here as an enum BMID.LLC_PLL_FBK, are the ECLKPLLFBL mux's
LLCLKOP setting; 158-pll-eclk-fbk fuzzes that mux, so this script no longer writes them.)

Usage: write_db.py [database root]
"""
import glob
import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")
TT = os.path.join(root, "LFCPNX", "tiletypes")


def bits(fb):
    return "".join("(frame:{},bit:{},invert:false,),".format(f, b) for f, b in fb)


def add_enum(tt, name, options, desc):
    """options: [(option, [(frame, bit)])]; inserted in name order."""
    fn = os.path.join(TT, tt + ".ron")
    t = open(fn).read()
    if '    "{}": ('.format(name) in t:
        return "present"
    block = '    "{}": (\n      options: {{\n{}      }},\n      desc: "{}",\n    ),\n'.format(
        name, "".join('        "{}": [{}],\n'.format(o, bits(b)) for o, b in options), desc)
    if "  enums: {},\n" in t:
        t = t.replace("  enums: {},\n", "  enums: {\n" + block + "  },\n", 1)
    else:
        i = t.index("  enums: {\n") + len("  enums: {\n")
        end = t.index("\n  },\n", i) + 1
        body = t[i:end]
        pos = len(body)
        for m in re.finditer(r'^    "([^"]+)": \(', body, re.M):
            if m[1] > name:
                pos = m.start()
                break
        t = t[:i] + body[:pos] + block + body[pos:] + t[end:]
    open(fn, "w").write(t)
    return "added"


BL16 = [(55, 1)]
OD = [(37, 1), (38, 1), (39, 1)]
MT = [(33, 1), (35, 1), (36, 1)]


def main():
    for tt in sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(TT, "SYSIO_B[345]_1_DQS0*.ron"))):
        print(tt, "DQSBUF.LPDDR4_BL16_EN", add_enum(tt, "DQSBUF.LPDDR4_BL16_EN", [("DISABLED", []), ("ENABLED", BL16)],
              "DQSBUF_IVREF LPDDR4_BL16_EN: the DQSBUF's LPDDR4 burst-length-16 mode"))
    for tt in sorted(os.path.basename(f)[:-4] for f in glob.glob(os.path.join(TT, "SYSIO_B[345]_*.ron"))):
        io = "IOLOGIC" + ("A" if re.match(r"SYSIO_B\d_0", tt) else "B")
        print(tt, io, add_enum(tt, io + ".OUTDELAYA", [("NONE", []), ("USED", OD)],
              "OUTDELAYA on this pad: its output and tristate pass through the output delay line "
              "(LPDDR4 write training; map accepts it only after ODDRX4DQ / ODDRX4DQS)"),
              add_enum(tt, io + ".OUTDELAYA.MARGIN_TEST_ENABLE", [("DISABLED", []), ("ENABLED", MT)],
              "OUTDELAYA MARGIN_TEST_ENABLE: the delay is adjustable through LOAD_N / MOVE / DIRECTION_LPDDR4_WT "
              "(set only with OUTDELAYA.USED)"))


if __name__ == "__main__":
    main()
