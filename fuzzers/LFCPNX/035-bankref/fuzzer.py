"""
Bank settings (BANKREF tile types): LIFCL's 035-bankref on LFCPNX-100, one IO per bank.

3.3 V banks (0, 1, 2, 6, 7): BANKn.VCC. HP banks (3, 4, 5): BANKn.VCC and the DIFF / REF / LVDS /
SLVS / MIPI_DPHY IO and VREF1 / VREF2 use settings. The fuzzed tiles are the bank's BANKREF tile
and, for the HP banks, the other bottom-edge reference tiles (on LIFCL some of these bits are in
the bank's V18 IO tiles and in DOSCL); the pad's own SYSIO tile is left out (its bits are the IO
type settings of 031 / 032).

Usage: fuzzer.py [bank ...]
"""
import importlib.util
import os
import sys

from fuzzconfig import FuzzConfig
import fuzzloops
import nonrouting

# 070's robust enum wrapper (pre-check / retry / skip) and work-directory cleanup
_spec = importlib.util.spec_from_file_location(
    "iol070", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "070-iologic_mode", "fuzzer.py"))
_spec.loader.exec_module(importlib.util.module_from_spec(_spec))

HP_REF = ["CIB_R73C159:BANKREF3_DDR42", "CIB_R74C77:BANKREF4_DLY42_DDR41", "CIB_R74C25:BANKREF5",
          "CIB_R68C0:DOSCL_P18", "CIB_R74C14:DDR40_ECLK_L"]
# bank: (pad site (ball), tiles)
BANKS = {
    0: ("G2", ["CIB_R0C132:BANKREF0"]),
    1: ("L1", ["CIB_R14C159:BANKREF1"]),
    2: ("W5", ["CIB_R54C159:BANKREF2"]),
    6: ("T24", ["CIB_R54C0:BANKREF6"]),
    7: ("H20", ["CIB_R14C0:BANKREF7"]),
    3: ("AA12", HP_REF),   # PB110A
    4: ("AF22", HP_REF),   # PB54A
    5: ("AC25", HP_REF),   # PB36A
}

vcc_to_io_33 = {"NONE": "NONE", "1V2": "LVCMOS12", "1V5": "LVCMOS15", "1V8": "LVCMOS18", "2V5": "LVCMOS25",
                "3V3": "LVCMOS33"}
vcc_to_io_18 = {"NONE": "NONE", "1V0": "LVCMOS10H", "1V2": "LVCMOS12H", "1V5": "LVCMOS15H", "1V8": "LVCMOS18H"}


def main():
    sel = [b for b in BANKS if not sys.argv[1:] or str(b) in sys.argv[1:]]

    def per_bank(bank):
        site, tiles = BANKS[bank]
        cfg = FuzzConfig(job="BANK{}".format(bank), device="LFCPNX-100", sv="../shared/empty_100.v", tiles=tiles)
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "../032-hsio_mode/iob_100.v"

        def get_substs(iotype="LVCMOS18H", kv=None, vcc=None, diff=False, tmux="#SIG"):
            extra_config = ",{}={}".format(kv[0], kv[1]) if kv is not None else ""
            if diff:
                primtype = "DIFFIO18A_CORE"
            elif bank in (3, 4, 5):
                primtype = "SEIO18A_CORE"
            else:
                primtype = "SEIO33_CORE"
            return dict(cmt="//" if iotype == "NONE" else "", pintype="inout", primtype=primtype, site=site,
                        iotype=iotype, t=tmux, extra_config=extra_config, vcc=vcc)

        if bank in (3, 4, 5):
            nonrouting.fuzz_enum_setting(cfg, empty, "BANK{}.VCC".format(bank), ["NONE", "1V0", "1V2", "1V5", "1V8"],
                                         lambda x: get_substs(iotype=vcc_to_io_18[x], vcc=x.replace("V", ".")), False,
                                         assume_zero_base=True, desc="VccIO of bank {}".format(bank))
            for name, on, off, kw in (
                    ("DIFF_IO", "SSTL15D_I", "SSTL15_I", dict(vcc="1.5")),
                    ("REF_IO", "SSTL15_I", "LVCMOS15H", dict(vcc="1.5")),
                    ("LVDS_IO", "LVDS", "LVCMOS18H", dict(vcc="1.8")),
                    ("SLVS_IO", "SLVS", "HSUL12", dict(vcc="1.2")),
                    ("MIPI_DPHY_IO", "MIPI_DPHY", "HSUL12", dict(vcc="1.2"))):
                diff_both = name == "LVDS_IO"
                nonrouting.fuzz_enum_setting(
                    cfg, empty, "BANK{}.{}".format(bank, name), ["OFF", "ON"],
                    lambda x, on=on, off=off, kw=kw, diff_both=diff_both, name=name: get_substs(
                        iotype=on if x == "ON" else off, diff=diff_both or (x == "ON" and name != "REF_IO"), **kw),
                    False, desc="use {} in bank {}".format(name.replace("_IO", " IO"), bank))
            for v in ("VREF1", "VREF2"):
                nonrouting.fuzz_enum_setting(
                    cfg, empty, "BANK{}.{}_USED".format(bank, v), ["OFF", "ON"],
                    lambda x, v=v: get_substs(iotype="SSTL15_I", vcc="1.5",
                                              kv=("VREF", v + "_LOAD" if x == "ON" else "OFF")),
                    False, desc="use {} input for bank {}".format(v, bank))
        else:
            nonrouting.fuzz_enum_setting(cfg, empty, "BANK{}.VCC".format(bank), ["NONE", "1V2", "1V5", "1V8", "2V5", "3V3"],
                                         lambda x: get_substs(iotype=vcc_to_io_33[x], vcc=x.replace("V", ".")), False,
                                         assume_zero_base=True, desc="VccIO of bank {}".format(bank))

    fuzzloops.parallel_foreach(sel, per_bank)


if __name__ == "__main__":
    main()
