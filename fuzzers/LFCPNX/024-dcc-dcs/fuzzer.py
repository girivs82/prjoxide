"""
DCC enables (DCCEN) and DCS mode on LFCPNX-100: LIFCL's 024-dcc-dcs. Every DCC is fuzzed against
all the clock tiles (as on LIFCL); a site name that does not exist on LFCPNX-100 is rejected by
Radiant and skipped.

Usage: fuzzer.py [site ...]
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

DEV = "LFCPNX-100"
DCC_TILES = ["CIB_R37C0:LMID", "CIB_R37C159:RMID", "CIB_R74C73:BMID_0_ECLK_1", "CIB_R74C74:BMID_1_ECLK_2",
             "CIB_R0C73:TMID_0", "CIB_R0C74:TMID_1", "CIB_R38C73:CMUX_0", "CIB_R38C74:CMUX_1_GSR",
             "CIB_R47C73:CMUX_2_TRUNK_LL", "CIB_R47C74:CMUX_3_TRUNK_LR", "CIB_R29C73:CMUX_4_TRUNK_UL",
             "CIB_R29C74:CMUX_5_TRUNK_UR", "CIB_R56C73:CMUX_6", "CIB_R56C74:CMUX_7"]
DCS_TILES = [t for t in DCC_TILES if ":CMUX_" in t]
DCC_PRIMS = ["DCC_L{}".format(i) for i in range(12)] + ["DCC_R{}".format(i) for i in range(12)] + \
            ["DCC_T{}".format(i) for i in range(16)] + ["DCC_B{}".format(i) for i in range(18)] + \
            ["DCC_C{}".format(i) for i in range(8)]
# LFCPNX-100's DCS sites are DCSA / DCSB (DCS0 / DCS1 are not sites; the routed clock designs place
# DCS at DCSA); the settings keep LIFCL's names, DCS0 / DCS1
DCS_PRIMS = ["DCSA", "DCSB"]
DCS_NAME = {"DCSA": "DCS0", "DCSB": "DCS1"}


def main():
    sel = [s for s in DCC_PRIMS + DCS_PRIMS if not sys.argv[1:] or s in sys.argv[1:]]

    def per_site(site):
        if site.startswith("DCC"):
            cfg = FuzzConfig(job=site, device=DEV, sv="../shared/empty_100.v", tiles=DCC_TILES)
            cfg.setup()
            empty = cfg.build_design(cfg.sv, {})
            cfg.sv = "dcc_100.v"
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.DCCEN".format(site), ["0", "1"],
                                         lambda x: dict(dev=DEV, site=site, dccen=x), False,
                                         desc="DCC bypassed (0) or used as gate (1)")
        else:
            cfg = FuzzConfig(job=site, device=DEV, sv="../shared/empty_100.v", tiles=DCS_TILES)
            cfg.setup()
            empty = cfg.build_design(cfg.sv, {})
            cfg.sv = "dcs_100.v"
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.DCSMODE".format(DCS_NAME[site]),
                                         ["GND", "DCS", "DCS_1", "BUFGCECLK0", "BUFGCECLK0_1", "BUFGCECLK1",
                                          "BUFGCECLK1_1", "BUF0", "BUF1", "VCC"],
                                         lambda x: dict(dev=DEV, site=site, dcsmode=x), False, desc="clock selector mode")

    fuzzloops.parallel_foreach(sel, per_site)


if __name__ == '__main__':
    main()
