"""
IDDRXN gearing (IDDRX2, IDDR71, IDDRX4, IDDRX5) for the IOLOGIC of the HP-bank (3-5) pads.

In fuzzer.py's structural template (an IOLOGIC_CORE with no connections) bitgen in Radiant 2026.1
segfaults on MODE IDDRXN. Here each design is a synthesized IDDRX2 / IDDR71 / IDDRX4 / IDDRX5 on
the pad, clocked like a real gearing input: a PCLK pin of the same bank drives an ECLKSYNC, whose
output is the IDDR's ECLK and, through an ECLKDIV of the matching ratio, its SCLK. The designs of
one pad differ only in the gearing mode (and the ECLKDIV ratio and IDDR outputs, which are
outside the pad's SYSIO tiles), so the enum's options come from diffing them against each other.

No setting of the IDDRXN primitive leaves DDRMODE unset, so there is no NONE sample: as on LIFCL
(where IDDRXN.DDRMODE=#OFF has no bits and MODE IDDRXN has none of its own), NONE and MODE IDDRXN
are added with no bits. That holds here: every other bit these designs set in the pad's tiles
decodes as another setting (pad type, GSR, SCLKINMUX, the ECLK pip).

Usage: gearing.py [site ...]   (run after fuzzer.py, in the same environment)
"""
import os
import re

import fuzzer  # noqa: F401  (SITES; installs the robust enum wrapper and the work-dir cleanup)
import fuzzloops
import nonrouting
import database

# HP-bank bottom pads on LFG672: (ball, bank)
PADS = {
    "PB2A": ("V24", 5),
    "PB2B": ("V25", 5),
    "PB4A": ("V23", 5),
    "PB4B": ("V22", 5),
    "PB36A": ("AC25", 5),
    "PB36B": ("AD26", 5),
    "PB42A": ("AE26", 5),
    "PB42B": ("AF25", 5),
    "PB44A": ("AE24", 5),
    "PB44B": ("AF24", 5),
    "PB48A": ("AC20", 5),
    "PB48B": ("AB20", 5),
    "PB50A": ("AE22", 4),
    "PB50B": ("AE23", 4),
    "PB52A": ("AD21", 4),
    "PB52B": ("AE21", 4),
    "PB54A": ("AF22", 4),
    "PB54B": ("AF23", 4),
    "PB56A": ("AD20", 4),
    "PB56B": ("AC19", 4),
    "PB62A": ("W17", 4),
    "PB62B": ("W18", 4),
    "PB64A": ("AF19", 4),
    "PB64B": ("AE19", 4),
    "PB66A": ("AF21", 4),
    "PB66B": ("AF20", 4),
    "PB80A": ("AC18", 4),
    "PB80B": ("AD18", 4),
    "PB108A": ("Y12", 4),
    "PB108B": ("W12", 4),
    "PB110A": ("AA12", 3),
    "PB110B": ("AB12", 3),
    "PB112A": ("AC12", 3),
    "PB112B": ("AD12", 3),
    "PB134A": ("AC7", 3),
    "PB134B": ("AB7", 3),
    "PB138A": ("AF6", 3),
    "PB138B": ("AF5", 3),
    "PB140A": ("AD6", 3),
    "PB140B": ("AE6", 3),
    "PB144A": ("AD5", 3),
    "PB144B": ("AE5", 3),
    "PB156A": ("AD3", 3),
    "PB156B": ("AE3", 3),
}
# ECLK source per bank: a PCLK input pin not used as a data pad
ECLK_PIN = {3: "AB11", 4: "AB19", 5: "W24"}
OUT_PIN = "AA1"     # bank 2
MODES = {"IDDRX2": ("2", 4), "IDDR71": ("3P5", 7), "IDDRX4": ("4", 8), "IDDRX5": ("5", 10)}



def add_empty_options(tiletypes):
    """NONE for IDDRXN.DDRMODE and IDDRXN for MODE, both with no bits (see the docstring)."""
    root = os.path.join(database.get_db_root(), "LFCPNX", "tiletypes")
    for tt in sorted(tiletypes):
        fn = os.path.join(root, tt + ".ron")
        t = open(fn).read()
        for p in sorted(set(re.findall(r'"(IOLOGIC[AB])\.IDDRXN\.DDRMODE"', t))):
            for enum, opt in (("IDDRXN.DDRMODE", "NONE"), ("MODE", "IDDRXN")):
                m = re.search(r'\n    "{}\.{}": \(\n      options: \{{\n(.*?)\n      \}},'.format(p, re.escape(enum)), t, re.S)
                if m is None or '"{}":'.format(opt) in m.group(1):
                    continue
                opts = m.group(1).split("\n") + ['        "{}": [],'.format(opt)]
                body = "\n".join(sorted(opts, key=lambda l: l.split('"')[1]))
                t = t[:m.start(1)] + body + t[m.end(1):]
        open(fn, "w").write(t)


def main():
    import sys
    sel = [c for c in fuzzer.configs if "P" + c[0][4:] in PADS and (not sys.argv[1:] or c[0] in sys.argv[1:])]

    def per_config(x):
        site, prim, cfg = x
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.struct_mode = False
        cfg.sv = "gearing.v"
        ball, bank = PADS["P" + site[4:]]

        def substs(mode):
            div, nq = MODES[mode]
            return dict(d_ball=ball, eclk_ball=ECLK_PIN[bank], q_ball=OUT_PIN, nq1=nq - 1, div=div, mode=mode,
                        qconn=", ".join(".Q{}(qq[{}])".format(i, i) for i in range(nq)))
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.IDDRXN.DDRMODE".format(prim), list(MODES), substs, False)

    fuzzloops.parallel_foreach(sel, per_config)
    add_empty_options({tile.split(":")[1] for _, _, cfg in sel for tile in cfg.tiles})


if __name__ == "__main__":
    main()
