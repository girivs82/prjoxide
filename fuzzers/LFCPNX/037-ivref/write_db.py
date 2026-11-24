"""
Write BANK<n>.IVREF (the bank VREF generator used by DQSBUF_IVREF, LVSTL's internal input reference)
into the bank reference tile types. See README.md. Re-running is a no-op.

Usage: write_db.py [database root]
"""
import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")
DESC = ("bank {} VREF generator (IVREF_CORE, from DQSBUF_IVREF) in use: the internal input reference "
        "of the LVSTL inputs, its level set by the fabric through IVREFI[6:0]")
# tile type -> (bank, [(frame, bit)])
BITS = {"BANKREF3_DDR42": (3, [(5, 8), (6, 8)]),
        "BANKREF4_DLY42_DDR41": (4, [(31, 1), (32, 1)]),
        "DDR40_ECLK_L": (5, [(31, 1), (32, 1)])}


def main():
    for tt, (bank, bits) in BITS.items():
        fn = os.path.join(root, "LFCPNX", "tiletypes", tt + ".ron")
        t = open(fn).read()
        name = "BANK{}.IVREF".format(bank)
        if '"{}"'.format(name) in t:
            print(tt, name, "present")
            continue
        on = "".join("(frame:{},bit:{},invert:false,),".format(f, b) for f, b in bits)
        block = ('    "{}": (\n      options: {{\n        "OFF": [],\n        "ON": [{}],\n      }},\n'
                 '      desc: "{}",\n    ),\n').format(name, on, DESC.format(bank))
        if "  enums: {},\n" in t:
            t = t.replace("  enums: {},\n", "  enums: {\n" + block + "  },\n", 1)
        else:
            i = t.index("  enums: {\n") + len("  enums: {\n")
            end = t.index("\n  },\n", i)
            body = t[i:end]
            pos = len(body) + 1
            for m in re.finditer(r'^    "([^"]+)": \(', body, re.M):
                if m[1] > name:
                    pos = m.start()
                    break
            body = body[:pos] + block + body[pos:] if pos <= len(body) else body + "\n" + block.rstrip("\n")
            t = t[:i] + body + t[end:]
        open(fn, "w").write(t)
        print(tt, name, "added")


if __name__ == "__main__":
    main()
