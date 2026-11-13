"""
IO delay settings (DELAYA in the HP-bank IOLOGIC, DELAYB in SIOLOGIC) and the IOLOGIC RANK* delay
control muxes for every LFCPNX SYSIO tile type with pads: LIFCL's 071-iodelay on the sites of
070-iologic_mode (whose pre-check / retry / skip handling and work-directory cleanup this reuses).

DIRMUX, MOVEMUX and LOAD_NMUX are in dynamic.py: Radiant 2026.1 refuses both their constant
values (a syntax error) and their signal values in this structural template.
"""
import importlib.util
import os

import fuzzloops
import nonrouting

# 070's SITES and its wrappers (robust enum pre-check, no core dumps, .tmp cleanup)
_spec = importlib.util.spec_from_file_location(
    "iol070", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "070-iologic_mode", "fuzzer.py"))
iol070 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iol070)


def main():
    def per_config(x):
        site, prim, cfg = x
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "iodelay_100.v"
        s = (prim[0] == "S")

        def get_substs(mode="IREG_OREG", deltype="DELAYA", kv=None, mux=False):
            if s and deltype == "DELAYA":
                deltype = "DELAYB"
            if kv is not None:
                if mux:
                    if kv[1] == "OFF":
                        config = "{0}MUX:#OFF".format(kv[0])
                    else:
                        config = "{0}MUX:{0}:::{0}=#SIG".format(kv[0])
                else:
                    config = "{}:::{}={}".format(deltype, kv[0], kv[1])
            else:
                config = ""
            return dict(mode=mode, cmt="//" if mode == "NONE" else "", config=config, site=site,
                        s="S" if s else "", pinconn="", sig="")

        def intval(vec):
            x = 0
            for i, b in enumerate(vec):
                if b:
                    x |= (1 << i)
            return x

        nonrouting.fuzz_word_setting(cfg, "{}.DELAY.DEL_VALUE".format(prim), 7,
                                     lambda x: get_substs(kv=("DEL_VALUE", str(intval(x)))),
                                     desc="initial fine delay value")

        nonrouting.fuzz_enum_setting(cfg, empty, "{}.DELAY.COARSE_DELAY".format(prim), ["0NS", "0P8NS", "1P6NS"],
                                     lambda x: get_substs(kv=("COARSE_DELAY", x)), False)
        if not s:
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.DELAY.COARSE_DELAY_MODE".format(prim), ["DYNAMIC", "STATIC"],
                                         lambda x: get_substs(kv=("COARSE_DELAY_MODE", x)), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.DELAY.EDGE_MONITOR".format(prim), ["ENABLED", "DISABLED"],
                                         lambda x: get_substs(kv=("EDGE_MONITOR", x)), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.DELAY.WAIT_FOR_EDGE".format(prim), ["ENABLED", "DISABLED"],
                                         lambda x: get_substs(kv=("WAIT_FOR_EDGE", x)), False)

            for pin in ["CIBCRS0", "CIBCRS1", "RANKSELECT", "RANKENABLE", "RANK0UPDATE", "RANK1UPDATE"]:
                nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}MUX".format(prim, pin), ["OFF", pin],
                                             lambda x: get_substs(kv=(pin, x), mux=True), False)

    import sys
    sel = [c for c in iol070.configs if not sys.argv[1:] or c[0] in sys.argv[1:]]
    fuzzloops.parallel_foreach(sel, per_config)


if __name__ == "__main__":
    main()
