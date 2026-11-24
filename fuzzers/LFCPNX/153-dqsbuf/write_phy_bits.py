"""
Write the DQSBUF bits that 153-dqsbuf's structural builds cannot set, found in Radiant-built PHY
designs (see ../README.md):
- DQSBUF.DLLCODE (DLLCODE from the right-side DDRDLL), in the DQS1 tile types;
- the DQSBUF's edge-clock input select, in the DQS3 tile types: pips
  N1W8:JECLKOUT_I_DQS_TOP_ECLK_ROUTING_MUX <- N1W8:JECLK<k>_I_DQS_TOP_ECLK_ROUTING_MUX (LIFCL's form),
  ECLK0 no bits, ECLK1 F52B1, ECLK2 F51B1, ECLK3 both. From DQSBUF designs of the
  timing/fuzzers/LFCPNX/12-dqsbuf-ivref generator with the ECLKSYNC / ECLKDIV pinned to each edge
  clock (ECLK_IDX=0-3), on a group of bank 3, 4 (normal and middle) and 5 at once.
F52B1 had been written as an enum DQSBUF.DQSI ("DQSI from the pad"): every earlier PHY design used
edge clock 1, and F52B1 is clear with edge clock 0 and DQSI still on the pad. That enum is removed.
Bank 3 from 156-dqsw-iologic's designs, banks 4 and 5 (the bank-4 middle group included) from designs
of the 12-dqsbuf-ivref generator; written only into the tile types where they were seen. Re-running
is a no-op, apart from refreshing the descriptions.

Usage: write_phy_bits.py [database root]
"""
import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")
DLLCODE = ("DLLCODE input of the DQSBUF of the group: set when it comes from the CODE output of the "
           "right-side DDRDLL (DDRDLL_CORE_R72C158), on banks 3, 4 and 5 alike. Clear both when it comes "
           "from the left-side DDRDLL (DDRDLL_CORE_R68C1) and when it is tied to 0; no bit tells those "
           "two apart. From Radiant-built PHY designs with the DDRDLL placed on either side")
ENUMS = []
for tt in ("SYSIO_B3_0_DQS1", "SYSIO_B4_0_DQS1", "SYSIO_B4_0_DQS1_MID", "SYSIO_B5_0_DQS1"):
    ENUMS.append((tt, "DQSBUF.DLLCODE", "DDRDLL", 45, 1, DLLCODE))
ECLK_SEL_TILES = ("SYSIO_B3_0_DQS3", "SYSIO_B4_0_DQS3", "SYSIO_B4_0_DQS3_MID", "SYSIO_B5_0_DQS3")
ECLK_SEL_TO = "N1W8:JECLKOUT_I_DQS_TOP_ECLK_ROUTING_MUX"
ECLK_SEL = [("N1W8:JECLK%d_I_DQS_TOP_ECLK_ROUTING_MUX" % k, bits)
            for k, bits in enumerate([[], [(52, 1)], [(51, 1)], [(51, 1), (52, 1)]])]


def remove_enum(fn, name):
    t = open(fn).read()
    key = '    "%s": (\n' % name
    if key not in t:
        return False
    i = t.index(key)
    j = t.index("\n    ),\n", i) + len("\n    ),\n")
    open(fn, "w").write(t[:i] + t[j:])
    return True


def add_pips(fn, to, options):
    t = open(fn).read()
    if '    "%s": [' % to in t:
        return False
    if "  pips: {}," in t:
        t = t.replace("  pips: {},", "  pips: {\n  },", 1)
    pi = t.index("  pips: {\n") + len("  pips: {\n")
    pe = t.index("\n  },\n", pi - 1)
    body = t[pi:pe]
    block = '    "%s": [\n%s    ],\n' % (to, "".join(
        '      (\n        from_wire: "%s",\n        bits: [%s],\n      ),\n'
        % (fw, "".join("(frame:%d,bit:%d,invert:false,)," % fb for fb in bits)) for fw, bits in options))
    pos = len(body) + 1
    for m in re.finditer(r'^    "([^"]+)": \[', body, re.M):
        if m[1] > to:
            pos = m.start()
            break
    body = body[:pos] + block + body[pos:] if pos <= len(body) else body + "\n" + block.rstrip("\n")
    open(fn, "w").write(t[:pi] + body + t[pe:])
    return True


def add(fn, name, opt, frame, bit, desc):
    t = open(fn).read()
    if '"%s"' % name in t:
        # present: refresh its description only
        i = t.index('    "%s": (\n' % name)
        d = t.index('      desc: "', i)
        e = t.index('",\n', d)
        new = t[:d] + '      desc: "%s' % desc + t[e:]
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
    opts = sorted([("OFF", ""), (opt, "(frame:%d,bit:%d,invert:false,)," % (frame, bit))])
    block = '    "%s": (\n      options: {\n%s      },\n      desc: "%s",\n    ),\n' % (
        name, "".join('        "%s": [%s],\n' % o for o in opts), desc)
    body = body[:pos] + block + body[pos:] if pos <= len(body) else body + "\n" + block.rstrip("\n")
    open(fn, "w").write(t[:i] + body + t[end:])
    return True


def main():
    for tt in ECLK_SEL_TILES:
        fn = os.path.join(root, "LFCPNX", "tiletypes", tt + ".ron")
        print(tt, "DQSBUF.DQSI", "removed" if remove_enum(fn, "DQSBUF.DQSI") else "absent")
        print(tt, ECLK_SEL_TO, "pips added" if add_pips(fn, ECLK_SEL_TO, ECLK_SEL) else "present")
    for tt, name, opt, frame, bit, desc in ENUMS:
        fn = os.path.join(root, "LFCPNX", "tiletypes", tt + ".ron")
        r = add(fn, name, opt, frame, bit, desc)
        print(tt, name, {True: "added", "desc": "description updated", False: "present"}[r])


if __name__ == "__main__":
    main()
