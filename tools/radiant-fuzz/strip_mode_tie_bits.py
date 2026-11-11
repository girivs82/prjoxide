#!/usr/bin/env python3
"""Remove pin-tie bits that leak into DSP <site>.MODE options.

fuzzers/LFCPNX/080's MODE defaults tie the control pins: CLK=0, RST*=0 and
CE*=1 (Radiant 2026.1 refuses clock enables tied low). On LFCPNX these tie
values have bits of their own (the <site>.<pin>MUX "0"/"1" options, which are
empty on LIFCL), and because MODE is diffed against NONE those bits end up
in the <site>.MODE.<primitive> option too. They are already described by the
mux enums, so they are stripped from the MODE option here.

Usage: strip_mode_ce_bits.py <prjoxide database root> [tile glob, default DSP_*]
Prints what it removed; rewrites only the affected .ron files.
"""
import glob
import os
import re
import sys

# pins tied in 080's MODE defaults -> the mux option value they are tied to
TIES = {
    "MULT9_CORE": {"CLK": "0", "RSTA": "0", "RSTP": "0", "CEA": "1", "CEP": "1"},
    "PREADD9_CORE": {"CLK": "0", "RSTB": "0", "RSTCL": "0", "CEB": "1", "CECL": "1"},
    "REG18_CORE": {"CLK": "0", "RSTP": "0", "CEP": "1"},
    "ACC54_CORE": {"CLK": "0", "RSTCIN": "0", "RSTCTRL": "0", "RSTO": "0", "RSTC": "0",
                   "CECIN": "1", "CECTRL": "1", "CEO": "1", "CEC": "1"},
}
BIT = re.compile(r"\(frame:(\d+),bit:(\d+),invert:(\w+),\)")


def enum_block(text, name):
    """(start, end) of the options body of enum `name`, or None."""
    m = re.search(r'\n    "{}": \(\n      options: \{{\n(.*?)\n      \}},'.format(re.escape(name)), text, re.S)
    return (m.start(1), m.end(1)) if m else None


def option_bits(body, opt):
    m = re.search(r'^        "{}": \[(.*?)\],$'.format(re.escape(opt)), body, re.M)
    return set(BIT.findall(m.group(1))) if m else None


def main():
    root = sys.argv[1]
    pattern = sys.argv[2] if len(sys.argv) > 2 else "DSP_*"
    changed = 0
    for path in sorted(glob.glob(os.path.join(root, "LFCPNX", "tiletypes", pattern + ".ron"))):
        text = open(path).read()
        sites = sorted(set(re.findall(r'\n    "([A-Z0-9_]+)\.MODE": \(', text)))
        new = text
        for site in sites:
            span = enum_block(new, site + ".MODE")
            body = new[span[0]:span[1]]
            prims = [p for p in TIES if re.search(r'^        "{}": \['.format(p), body, re.M)]
            if not prims:
                continue
            prim = prims[0]
            leak = set()
            for pin, val in TIES[prim].items():
                mux_span = enum_block(new, "{}.{}MUX".format(site, pin))
                if mux_span:
                    leak |= option_bits(new[mux_span[0]:mux_span[1]], val) or set()
            mode_bits = option_bits(body, prim)
            drop = mode_bits & leak
            if not drop:
                continue
            keep = sorted(mode_bits - drop, key=lambda b: (int(b[0]), int(b[1])))
            line = "        \"{}\": [{}],".format(prim, "".join(
                "(frame:{},bit:{},invert:{},),".format(*b) for b in keep))
            body2 = re.sub(r'^        "{}": \[.*?\],$'.format(prim), line.replace("\\", "\\\\"), body, count=1, flags=re.M)
            new = new[:span[0]] + body2 + new[span[1]:]
            print("{}: {}.MODE.{}: removed {}".format(os.path.basename(path), site, prim,
                  " ".join("{}.{}".format(f, b) for f, b, _ in sorted(drop, key=lambda b: (int(b[0]), int(b[1]))))))
        if new != text:
            open(path, "w").write(new)
            changed += 1
    print("files changed:", changed)


if __name__ == "__main__":
    main()
