"""
IOLOGIC DIRMUX, MOVEMUX and LOAD_NMUX (the DELAYA DIRECTION / MOVE / LOAD_N inputs) on the HP-bank
pads.

LIFCL fuzzes these in its 070 structural template with a constant and a signal value; Radiant
2026.1 refuses both there (the constant is a syntax error, and a signal needs a driven pin). Here
each design is a synthesized DELAYA on the pad, its output going through fabric logic to an output
pin (so the delay stays in the pad's IOLOGIC), with one control input driven from an input pin and
the others tied to their inactive constants (LOAD_N high, MOVE and DIRECTION low). The option
names are LIFCL's: the constant ("0", or "1" for LOAD_N) and the signal.

Usage: dynamic.py [site ...]   (run after fuzzer.py, in the same environment)
"""
import importlib.util
import os
import sys

import fuzzloops
import nonrouting

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, fn)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 070's sites and wrappers, and the HP pad balls of its gearing.py (which imports 070 as "fuzzer")
iol070 = _load("fuzzer", os.path.join(HERE, "..", "070-iologic_mode", "fuzzer.py"))
gearing = _load("gearing070", os.path.join(HERE, "..", "070-iologic_mode", "gearing.py"))

INACTIVE = {"LOAD_N": "1'b1", "MOVE": "1'b0", "DIRECTION": "1'b0"}
MUXES = (("DIR", "DIRECTION", "0"), ("MOVE", "MOVE", "0"), ("LOAD_N", "LOAD_N", "1"))


def main():
    sel = [c for c in iol070.configs if "P" + c[0][4:] in gearing.PADS and (not sys.argv[1:] or c[0] in sys.argv[1:])]

    def per_config(x):
        site, prim, cfg = x
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.struct_mode = False
        cfg.sv = os.path.join(HERE, "dynamic.v")
        ball = gearing.PADS["P" + site[4:]][0]
        for mux, port, const in MUXES:
            def substs(v, port=port):
                ties = dict(INACTIVE)
                if v != const:
                    ties[port] = "c"
                return dict(d_ball=ball, load_n=ties["LOAD_N"], move=ties["MOVE"], direction=ties["DIRECTION"])
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}MUX".format(prim, mux), [const, mux], substs, False)

    fuzzloops.parallel_foreach(sel, per_config)


if __name__ == "__main__":
    main()
