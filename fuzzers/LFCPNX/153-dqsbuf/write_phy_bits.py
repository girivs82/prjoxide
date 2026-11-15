"""
Write the DQSBUF bits that 153-dqsbuf's structural builds cannot set, found in Radiant-built PHY
designs (see ../README.md): DQSBUF.DLLCODE (DLLCODE from the right-side DDRDLL) and DQSBUF.DQSI
(DQSI on the group's DQS pad, the only source Radiant allows). Bank 3 from 156-dqsw-iologic's
designs, banks 4 and 5 (the bank-4 middle group included) from designs of the
timing/fuzzers/LFCPNX/12-dqsbuf-ivref generator; written only into the tile types where they were
seen. Re-running is a no-op, apart from refreshing the descriptions.

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
DQSI = ("set in every design whose DQSBUF takes DQSI from the DQS pad of the group, the only source Radiant "
        "allows (a fabric source is refused), so it is not separable from that connection; from Radiant-built "
        "PHY designs")
ENUMS = []
for tt in ("SYSIO_B3_0_DQS1", "SYSIO_B4_0_DQS1", "SYSIO_B4_0_DQS1_MID", "SYSIO_B5_0_DQS1"):
    ENUMS.append((tt, "DQSBUF.DLLCODE", "DDRDLL", 45, 1, DLLCODE))
for tt in ("SYSIO_B3_0_DQS3", "SYSIO_B4_0_DQS3", "SYSIO_B4_0_DQS3_MID", "SYSIO_B5_0_DQS3"):
    ENUMS.append((tt, "DQSBUF.DQSI", "PAD", 52, 1, DQSI))


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
    for tt, name, opt, frame, bit, desc in ENUMS:
        fn = os.path.join(root, "LFCPNX", "tiletypes", tt + ".ron")
        r = add(fn, name, opt, frame, bit, desc)
        print(tt, name, {True: "added", "desc": "description updated", False: "present"}[r])


if __name__ == "__main__":
    main()
