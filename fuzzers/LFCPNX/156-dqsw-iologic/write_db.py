"""
Write IOLOGIC<x>.MODDRXN.DQSW_CLK into the bank 3 / 4 / 5 SYSIO tile types (see README.md).

The bit was found by decoding the Radiant-built variants from gen_variants.py: it is set on
every IOLOGIC whose output gearing is clocked by the DQS group's DQSBUF (ODDRX4DQ on DQSW270,
ODDRX4DQS on DQSW; MODDRXN mode) and on no other. Only a new enum is added, so FASM that packed
before packs to the same bitstream. Re-running is a no-op.

Usage: write_db.py [database root]
"""
import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")
DESC = ("output gearing clocked by the DQSBUF of the DQS group (DQSW or DQSW270: ODDRX4DQ, ODDRX4DQS), "
        "set with MODDRXN.DDRMODE MODDRX*_DQSW*; the structural MODDRXN builds of 070 (no DQSBUF "
        "connected) do not set it. From Radiant-built PHY designs, X4 and X2 gearing")
# tile type -> (enum, frame, bit)
BITS = {}
# Bank 3 from this fuzzer's designs. Banks 4 / 5 from designs of the DQSBUF generator
# (timing/fuzzers/LFCPNX/12-dqsbuf-ivref/gen_dqsbuf_ivref.py): its DQSBUF_IVREF designs, then plain
# DQSBUF designs with a DQ pad in every bank 4 / 5 tile type (README.md, "Banks 4 and 5"). Every tile
# type is listed only once the bit was seen there on a DQ / DQS pad of a DQSBUF-clocked output.
for t in ("SYSIO_B3_0", "SYSIO_B3_0_DQS1", "SYSIO_B3_0_DQS3",
          "SYSIO_B4_0", "SYSIO_B4_0_DQS1", "SYSIO_B4_0_DQS3", "SYSIO_B4_0_DQS1_MID", "SYSIO_B4_0_DQS3_MID",
          "SYSIO_B5_0", "SYSIO_B5_0_DQS1", "SYSIO_B5_0_DQS3"):
    BITS[t] = ("IOLOGICA.MODDRXN.DQSW_CLK", 62, 0)
for t in ("SYSIO_B3_1", "SYSIO_B3_1_DQS0", "SYSIO_B3_1_DQS2", "SYSIO_B3_1_DQS4", "SYSIO_B3_1_V18",
          "SYSIO_B3_1_V18_32", "SYSIO_B3_1_ECLK_R",
          "SYSIO_B4_1", "SYSIO_B4_1_DQS0", "SYSIO_B4_1_DQS2", "SYSIO_B4_1_DQS4", "SYSIO_B4_1_V18",
          "SYSIO_B4_1_V18_42", "SYSIO_B4_1_DQS0_MID", "SYSIO_B4_1_DQS2_MID", "SYSIO_B4_1_DQS4_MID",
          "SYSIO_B5_1", "SYSIO_B5_1_DQS0", "SYSIO_B5_1_DQS2", "SYSIO_B5_1_DQS4", "SYSIO_B5_1_V18",
          "SYSIO_B5_1_V18_51"):
    BITS[t] = ("IOLOGICB.MODDRXN.DQSW_CLK", 63, 0)


def add(fn, name, frame, bit):
    t = open(fn).read()
    if '"%s"' % name in t:
        # present: refresh its description only
        i = t.index('    "%s": (\n' % name)
        d = t.index('      desc: "', i)
        e = t.index('",\n', d)
        new = t[:d] + '      desc: "%s' % DESC + t[e:]
        if new != t:
            open(fn, "w").write(new)
            return "desc"
        return False
    i = t.index("  enums: {\n") + len("  enums: {\n")
    end = t.index("\n  },\n", i)
    body = t[i:end]
    pos = len(body) + 1
    for m in re.finditer(r'^    "([^"]+)": \(', body, re.M):
        if m[1] > name:
            pos = m.start()
            break
    block = ('    "%s": (\n      options: {\n        "OFF": [],\n'
             '        "ON": [(frame:%d,bit:%d,invert:false,),],\n      },\n      desc: "%s",\n    ),\n'
             % (name, frame, bit, DESC))
    body = body[:pos] + block + body[pos:] if pos <= len(body) else body + "\n" + block.rstrip("\n")
    open(fn, "w").write(t[:i] + body + t[end:])
    return True


def main():
    for tt, (name, frame, bit) in sorted(BITS.items()):
        fn = os.path.join(root, "LFCPNX", "tiletypes", tt + ".ron")
        r = add(fn, name, frame, bit)
        print(tt, name, {True: "added", "desc": "description updated", False: "present"}[r])


if __name__ == "__main__":
    main()
