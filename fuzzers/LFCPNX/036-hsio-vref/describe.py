"""
Write the database descriptions that document the LFCPNX HP-IO (bank 3/4/5 SYSIO) decode choices:

- enums with options whose bits are identical: the bitstream cannot tell them apart; the decoder
  emits the last of each group by name (the canonical option) and the description lists the others;
- the voltage-specific DRIVE_<v> / TERMINATION_<v> enums share bits; the decoder keeps the one that
  matches the BASE_TYPE of the PIO (libprjoxide/prjoxide/src/lfcpnx_decode.rs);
- the PIOA enums in the pair's second tile (SYSIO_B<n>_1*), which take the first tile's PIOA decode.

Only `desc` fields are written; bits are not touched, so packing is unchanged.

Usage: describe.py [database root]
"""
import glob
import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")
ENUM_RE = re.compile(r'(\n    "([^"]+)": \(\n      options: \{\n)(.*?)(\n      \},\n)((?:      desc: "[^"]*",\n)?)(    \),)', re.S)
OPT_RE = re.compile(r'^        "([^"]+)": \[(.*)\],$', re.M)

VOLTAGE_DESC = {
    "DRIVE": "drive strength for {v} IO types. DRIVE_<v> enums share bits; the decoder keeps only the "
             "one for the BASE_TYPE of the PIO",
    "TERMINATION": "on-die termination for {v} IO types. TERMINATION_<v> enums share bits; the decoder "
                   "keeps only the one for the BASE_TYPE of the PIO",
}
VOLTS = {"1V8": "1.8 V", "1V5": "1.5 V", "1V35": "1.35 V", "1V2": "1.2 V", "1V1": "1.1 V (LVSTL_I)",
         "1V0": "1.0 V", "HSUL12": "HSUL12", "LVSTL": "LVSTL_I"}


def describe(tiletype, name, opts):
    parts = []
    m = re.match(r'PIO[AB]\.SEIO18\.(DRIVE|TERMINATION)_(\w+)$', name)
    if m:
        parts.append(VOLTAGE_DESC[m[1]].format(v=VOLTS.get(m[2], m[2])))
    if name.startswith("PIOA.") and re.match(r'SYSIO_B[345]_1', tiletype):
        parts.append("the bits of PIOA in the second tile of the pair; the decoder takes the option the first tile "
                     "decodes for PIOA (NONE when PIOA is unused)")
    groups = {}
    for o, bits in opts:
        if bits.strip():
            groups.setdefault(bits, []).append(o)
    eq = [sorted(g) for g in groups.values() if len(g) > 1]
    if eq:
        eq.sort(key=lambda g: g[-1])
        parts.append("identical bits, decoded as the last of each group: " +
                     "; ".join(" = ".join([g[-1]] + g[:-1]) for g in eq))
    return ". ".join(parts)


def main():
    n = 0
    for fn in sorted(glob.glob(os.path.join(root, "LFCPNX", "tiletypes", "SYSIO_B[345]_*.ron"))):
        tiletype = os.path.basename(fn)[:-4]
        t = open(fn).read()

        def sub(m):
            nonlocal n
            desc = describe(tiletype, m[2], OPT_RE.findall(m[3]))
            if not desc:
                return m[0]
            n += 1
            return m[1] + m[3] + m[4] + '      desc: "{}",\n'.format(desc) + m[6]
        t2 = ENUM_RE.sub(sub, t)
        if t2 != t:
            open(fn, "w").write(t2)
    print("described", n, "enums")


if __name__ == "__main__":
    main()
