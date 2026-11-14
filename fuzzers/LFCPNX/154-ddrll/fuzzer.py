"""
DDRDLL settings on LFCPNX-100: LIFCL's 154-ddrll settings on its two DDRDLLs, R68C1 (in the left
tile DOSCL_P18) and R72C158 (in DDR_OSC_R); the sites were found with designs that place a DDRDLL
at candidate sites near the DDR tiles.

Usage: fuzzer.py
"""
import importlib.util
import os

from fuzzconfig import FuzzConfig
import fuzzloops
import nonrouting

_spec = importlib.util.spec_from_file_location(
    "iol070", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "070-iologic_mode", "fuzzer.py"))
_spec.loader.exec_module(importlib.util.module_from_spec(_spec))   # robust enum wrapper, work-dir cleanup

SITES = [("DDRDLLL", "CIB_R68C0:DOSCL_P18", (68, 1)), ("DDRDLLR", "CIB_R72C159:DDR_OSC_R", (72, 158))]


def main():
    def per_site(x):
        job, tile, (r, c) = x
        cfg = FuzzConfig(job=job, device="LFCPNX-100", sv="../shared/empty_100.v", tiles=[tile])
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "ddrdll_100.v"
        site = "DDRDLL_CORE_R{}C{}".format(r, c)

        def get_substs(mode="DDRDLL_CORE", kv=None, mux=False):
            if kv is None:
                config = ""
            elif mux:
                val = "#INV" if kv[1] == "INV" else (kv[1] if kv[1] in ("0", "1") else "#SIG")
                config = "{}::::{}={}".format(mode, kv[0], val)
            else:
                config = "{}:::{}={}".format(mode, kv[0], kv[1])
            return dict(mode=mode, cmt="//" if mode == "NONE" else "", config=config, site=site)

        nonrouting.fuzz_enum_setting(cfg, empty, "DDRDLL.MODE", ["NONE", "DDRDLL_CORE"], lambda x: get_substs(mode=x),
                                     False, desc="DDRDLL primitive mode")
        nonrouting.fuzz_enum_setting(cfg, empty, "DDRDLL.GSR", ["ENABLED", "DISABLED"],
                                     lambda x: get_substs(kv=("GSR", x)), False, desc="DDRDLL GSR mask")
        nonrouting.fuzz_enum_setting(cfg, empty, "DDRDLL.ENA_ROUNDOFF", ["ENABLED", "DISABLED"],
                                     lambda x: get_substs(kv=("ENA_ROUNDOFF", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "DDRDLL.FORCE_MAX_DELAY",
                                     ["CODE_OR_LOCK_FROM_DLL_LOOP", "FORCE_LOCK_AND_CODE"],
                                     lambda x: get_substs(kv=("FORCE_MAX_DELAY", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "DDRDLL.RSTMUX", ["RST", "INV"],
                                     lambda x: get_substs(kv=("RST", x), mux=True), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "DDRDLL.ENA_OSC", ["ENABLED", "DISABLED"],
                                     lambda x: get_substs(kv=("ENA_OSC", x)), False)

    fuzzloops.parallel_foreach(SITES, per_site)


if __name__ == "__main__":
    main()
