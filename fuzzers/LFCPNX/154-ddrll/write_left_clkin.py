"""
Write the clock input of the left-side DDRDLL (DDRDLL_CORE_R68C1, tile CIB_R68C0:DOSCL_P18) on
LFCPNX-100 (see README.md, "Left DDRDLL clock input"):

- DOSCL_P18 pips JCLKOUT_I0 <- JECLK0_I0 .. JECLK3_I0 / JPCLK_I0: the DDRDLL's CLKIN mux, the left
  counterpart of DDR_OSC_R's W1:JCLKOUT_I0 mux. The wires are tile-local (R68C0): sv2udb accepts
  R68C0_JCLKOUT_I0 from R68C0_JECLK0_I0 .. JECLK3_I0 and JPCLK_I0 (and rejects a made-up
  JECLK9_I0). Their bits are from Radiant-routed designs: the DDRDLL pinned to R68C1, its CLKIN from
  an ECLKSYNC pinned to each of R73C73A / B / C / D (edge clock 0-3; R73C72B, bank 5, gives the same
  as R73C73B), or from a primary clock.
- DDR40_ECLK_L (CIB_R74C14) enums ECLKDDRL.ECLK<k> (OFF / ON): F(101+k)B1, set exactly when edge
  clock k reaches the left DDRDLL's CLKIN mux, whichever bank's ECLKSYNC drives it; never with the
  DDRDLL on the right or clocked from a primary clock. Written as an enum because Radiant's routing
  does not name the wires of this step.

Only pips and enums are added, so FASM that packed before packs to the same bitstream. Re-running
is a no-op.

Usage: write_left_clkin.py [database root]
"""
import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")
# DOSCL_P18: CLKIN mux source -> bits (frame, bit), all at row bit 0
CLKIN_MUX = {
    "JECLK0_I0": [(9, 0)],
    "JECLK1_I0": [(9, 0), (11, 0)],
    "JECLK2_I0": [(9, 0), (10, 0)],
    "JECLK3_I0": [(9, 0), (10, 0), (11, 0)],
    "JPCLK_I0": [(11, 0)],
}
ECLK_DESC = ("set when edge clock {k} feeds the CLKIN mux of the left DDRDLL (DDRDLL_CORE_R68C1, DOSCL_P18 "
             "JCLKOUT_I0 <- JECLK{k}_I0), from the ECLKSYNC of bank 4 or bank 5 alike. From Radiant-built "
             "designs with the DDRDLL and the ECLKSYNC pinned")


def bits(bs):
    return "[" + "".join("(frame:%d,bit:%d,invert:false,)," % fb for fb in bs) + "]"


def write_pips(fn):
    t = open(fn).read()
    if '"JCLKOUT_I0": [' in t:
        return False
    body = '  pips: {\n    "JCLKOUT_I0": [\n'
    for src, bs in sorted(CLKIN_MUX.items()):
        body += '      (\n        from_wire: "%s",\n        bits: %s,\n      ),\n' % (src, bits(bs))
    body += '    ],\n  },\n'
    if "  pips: {},\n" not in t:
        raise SystemExit(fn + ": pips are not empty; merge by hand")
    open(fn, "w").write(t.replace("  pips: {},\n", body, 1))
    return True


def add_enum(t, name, on, desc):
    if '    "%s": (\n' % name in t:
        return t, False
    i = t.index("  enums: {\n") + len("  enums: {\n")
    end = t.index("\n  },\n", i)
    body = t[i:end]
    pos = len(body) + 1
    for m in re.finditer(r'^    "([^"]+)": \(', body, re.M):
        if m[1] > name:
            pos = m.start()
            break
    new = ('    "%s": (\n      options: {\n        "OFF": [],\n        "ON": %s,\n      },\n      desc: "%s",\n'
           '    ),\n' % (name, bits(on), desc))
    body = body[:pos] + new + body[pos:] if pos <= len(body) else body + "\n" + new.rstrip("\n")
    return t[:i] + body + t[end:], True


def main():
    tdir = os.path.join(root, "LFCPNX", "tiletypes")
    print("DOSCL_P18 CLKIN mux pips", "added" if write_pips(os.path.join(tdir, "DOSCL_P18.ron")) else "present")
    fn = os.path.join(tdir, "DDR40_ECLK_L.ron")
    t = open(fn).read()
    for k in range(4):
        t, a = add_enum(t, "ECLKDDRL.ECLK%d" % k, [(101 + k, 1)], ECLK_DESC.format(k=k))
        print("DDR40_ECLK_L ECLKDDRL.ECLK%d" % k, "added" if a else "present")
    open(fn, "w").write(t)


if __name__ == "__main__":
    main()
