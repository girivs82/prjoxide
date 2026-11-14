"""
ECLKSYNC and ECLKDIV settings of the HP banks' edge clocks on LFCPNX-100: LIFCL's 151-eclkprim.
Banks 5, 4 and 3 have their ECLKSYNC / ECLKDIV A-D at R73C72, R73C73 and R73C74 (as the ECLKBANK
muxes found by 002c-clock-tile-pips); each is fuzzed against the four bottom-middle ECLK tiles.

Usage: fuzzer.py [bank ...]
"""
import importlib.util
import os
import sys

from fuzzconfig import FuzzConfig
import fuzzloops
import nonrouting

_spec = importlib.util.spec_from_file_location(
    "iol070", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "070-iologic_mode", "fuzzer.py"))
_spec.loader.exec_module(importlib.util.module_from_spec(_spec))   # robust enum wrapper, work-dir cleanup

TILES = ["CIB_R74C72:ECLK_0", "CIB_R74C73:BMID_0_ECLK_1", "CIB_R74C74:BMID_1_ECLK_2", "CIB_R74C75:ECLK_3"]
BANKS = {5: (73, 72), 4: (73, 73), 3: (73, 74)}


def main():
    sel = [b for b in BANKS if not sys.argv[1:] or str(b) in sys.argv[1:]]

    def per_bank(bank):
        r, c = BANKS[bank]
        cfg = FuzzConfig(job="ECLK{}".format(bank), device="LFCPNX-100", sv="../shared/empty_100.v", tiles=TILES)
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "eclkprim_100.v"

        def get_substs(prim, site, mode="NONE", kv=None):
            config = "" if kv is None else "{}:::{}={}".format(mode, kv[0], kv[1])
            return dict(mode=mode, cmt="//" if mode == "NONE" else "", config=config, prim=prim, site=site)

        for z in "ABCD":
            site = "ECLKSYNC_CORE_R{}C{}{}".format(r, c, z)
            p = "ECLKSYNC_CORE"
            nonrouting.fuzz_enum_setting(cfg, empty, "ECLKSYNC{}{}.MODE".format(bank, z), ["NONE", "ECLKSYNC"],
                                         lambda x, site=site: get_substs(p, site, mode=x), False,
                                         desc="ECLKSYNC primitive mode")
            nonrouting.fuzz_enum_setting(cfg, empty, "ECLKSYNC{}{}.STOP_EN".format(bank, z), ["DISABLE", "ENABLE"],
                                         lambda x, site=site: get_substs(p, site, mode=p, kv=("STOP_EN", x)), False,
                                         desc="ECLKSYNC stop control enable")
        for z in "ABCD":
            site = "ECLKDIV_CORE_R{}C{}{}".format(r, c, z)
            p = "ECLKDIV_CORE"
            nonrouting.fuzz_enum_setting(cfg, empty, "ECLKDIV{}{}.GSR".format(bank, z), ["DISABLED", "ENABLED"],
                                         lambda x, site=site: get_substs(p, site, mode=p, kv=("GSR", x)), False,
                                         desc="ECLKDIV GSR mask")
            nonrouting.fuzz_enum_setting(cfg, empty, "ECLKDIV{}{}.ECLK_DIV".format(bank, z),
                                         ["DISABLE", "2", "3P5", "4", "5"],
                                         lambda x, site=site: get_substs(p, site, mode=p, kv=("ECLK_DIV", x)), False,
                                         desc="ECLKDIV divide value")

    fuzzloops.parallel_foreach(sel, per_bank)


if __name__ == "__main__":
    main()
