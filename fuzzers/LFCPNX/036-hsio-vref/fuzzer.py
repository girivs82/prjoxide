"""
LVSTL (VCCIO 1.1 V) and the reference-standard slew rate on the LFCPNX-100 HP banks (3, 4, 5).

Adds to the database 032-hsio_mode wrote (new options and new enums only; existing options are never
changed, the database refuses a conflicting option):

per PIO, on 032's 44 A/B pads (one per HP SYSIO tile-type pair):
  PIO<x>.SEIO18.BASE_TYPE      INPUT/OUTPUT/BIDIR_LVSTL_I, INPUT/OUTPUT/BIDIR_LVSTL_II
  PIOA.DIFFIO18.BASE_TYPE      INPUT/OUTPUT/BIDIR_LVSTLD_I, INPUT/OUTPUT/BIDIR_LVSTLD_II
  PIO<x>.SEIO18.DRIVE_LVSTL    LVSTL_I output drive 2/4/6/8/10/12 (Radiant's default is 8)
  PIO<x>.SEIO18.TERMINATION_1V1  LVSTL_I on-die termination: OFF and 40/48/60/80/120 ohm; Radiant
                               also accepts 50/75/150, which set no termination bits and clear F95
  PIO<x>.SEIO18.SLEWRATE_REF   slew rate of the referenced standards (SSTL, HSTL, HSUL, LVSTL), whose
                               MED encoding differs from the LVCMOS one in SLEWRATE
per bank (BANKREF tile):       BANK<n>.LVSTL  OFF / LVSTL_I / LVSTL_II
chip-wide (DOSCL_P18):         LVSTL  OFF / LVSTL_I / LVSTL_II (the same bits for every HP bank)

LVSTL inputs have no VREF bits at the pad: VREF1_LOAD / VREF2_LOAD (VREF1 is the default) only set
F94B1 in the tile of the bank's VREF1 or VREF2 pin, which 032's VREF enum of that tile already
decodes, so no LVSTL VREF enum is written.

The voltage-specific enums share bits with 032's (DRIVE_*, TERMINATION_*, SLEWRATE); the
LFCPNX decoder keeps the one that matches the PIO's BASE_TYPE (lfcpnx_decode.rs). describe.py
writes the descriptions.

Usage: fuzzer.py [pio|bank]   (default: both)
"""
import importlib.util
import os
import sys

from fuzzconfig import FuzzConfig
import fuzzloops
import nonrouting

_here = os.path.dirname(os.path.abspath(__file__))
# 032's pad configs, its pre-check / retry / skip wrapper around fuzz_enum_setting (installed when the
# module loads) and drop_default_drive
_spec = importlib.util.spec_from_file_location("hsio032", os.path.join(_here, "..", "032-hsio_mode", "fuzzer.py"))
hsio032 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hsio032)

LVSTL_SE = ["LVSTL_I", "LVSTL_II"]
LVSTL_DIFF = ["LVSTLD_I", "LVSTLD_II"]
DEFAULT = hsio032.DEFAULT_DRIVE


def substs(site, iotype="BIDIR_LVSTL_I", kv=None, vcc="1.1"):
    """Template substitutions for 032's iob_100.v: one SEIO18A/DIFFIO18A pad."""
    if iotype == "NONE":
        return dict(cmt="//", pintype="inout", primtype="SEIO18A_CORE", site=site, iotype="", t="#SIG",
                    extra_config="", vcc=vcc)
    iodir, iostd = iotype.split("_", 1)
    pintype, t = {"INPUT": ("input", "1"), "OUTPUT": ("output", "0"), "BIDIR": ("inout", "#SIG")}[iodir]
    extra = "".join(",{}={}".format(k, v) for k, v in (kv or []))
    prim = "DIFFIO18A_CORE" if iostd in LVSTL_DIFF else "SEIO18A_CORE"
    return dict(cmt="", pintype=pintype, primtype=prim, site=site, iotype=iostd, t=t, extra_config=extra, vcc=vcc)


def fuzz_pio(config):
    pio, site, cfg = config
    cfg.setup()
    empty = cfg.build_design(cfg.sv, {})
    cfg.sv = os.path.join(_here, "..", "032-hsio_mode", "iob_100.v")
    E = nonrouting.fuzz_enum_setting
    pre = "PIO{}.SEIO18.".format(pio)

    se_types = ["NONE"] + ["{}_{}".format(d, s) for s in LVSTL_SE for d in ("INPUT", "OUTPUT", "BIDIR")]
    # same solver settings as 032's BASE_TYPE, so NONE comes out as before
    E(cfg, empty, pre + "BASE_TYPE", se_types, lambda x: substs(site, x), False, assume_zero_base=True)
    if pio == "A":
        di_types = ["NONE"] + ["{}_{}".format(d, s) for s in LVSTL_DIFF for d in ("INPUT", "OUTPUT", "BIDIR")]
        E(cfg, empty, "PIOA.DIFFIO18.BASE_TYPE", di_types, lambda x: substs(site, x), False)

    # drive: the design with DRIVE unset (Radiant's default, 8, as in the BASE_TYPE options) is an extra
    # sample, as in 032, and the helper option is removed afterwards
    E(cfg, empty, pre + "DRIVE_LVSTL", [DEFAULT, "2", "4", "6", "8", "10", "12"],
      lambda x: substs(site, "OUTPUT_LVSTL_I", None if x == DEFAULT else [("DRIVE", x)]), True,
      desc="LVSTL_I output drive (mA)")
    E(cfg, empty, pre + "TERMINATION_1V1", ["OFF", "40", "48", "60", "80", "120", "50", "75", "150"],
      lambda x: substs(site, "INPUT_LVSTL_I", [("TERMINATION", x)]), False)
    E(cfg, empty, pre + "SLEWRATE_REF", ["SLOW", "MED", "FAST"],
      lambda x: substs(site, "OUTPUT_HSUL12", [("SLEWRATE", x)], vcc="1.2"), True)


# bank: (pad site, its BANKREF tile)
BANKS = {3: ("AA12", "CIB_R73C159:BANKREF3_DDR42"), 4: ("AF22", "CIB_R74C77:BANKREF4_DLY42_DDR41"),
         5: ("AC25", "CIB_R74C25:BANKREF5")}


def fuzz_bank(bank):
    site, tile = BANKS[bank]
    if bank == 3:
        jobs = [("BANK3", [tile], "BANK3.LVSTL", "LVSTL class (VCCIO 1.1 V) used in bank 3"),
                ("LVSTLGLOBAL", ["CIB_R68C0:DOSCL_P18"], "LVSTL", "LVSTL class (VCCIO 1.1 V) used in any HP bank")]
    else:
        jobs = [("BANK{}".format(bank), [tile], "BANK{}.LVSTL".format(bank),
                 "LVSTL class (VCCIO 1.1 V) used in bank {}".format(bank))]
    for job, tiles, name, desc in jobs:
        cfg = FuzzConfig(job="LVSTL_" + job, device="LFCPNX-100", sv="../shared/empty_100.v", tiles=tiles)
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = os.path.join(_here, "..", "032-hsio_mode", "iob_100.v")
        # OFF: a referenced 1.2 V input (REF_IO, decoded separately, stays on in every sample)
        nonrouting.fuzz_enum_setting(
            cfg, empty, name, ["OFF", "LVSTL_I", "LVSTL_II"],
            lambda x: substs(site, "INPUT_HSUL12", vcc="1.2") if x == "OFF" else substs(site, "INPUT_" + x),
            False, desc=desc)


def main():
    what = sys.argv[1:] or ["pio", "bank"]
    if "bank" in what:
        fuzzloops.parallel_foreach(list(BANKS), fuzz_bank)
    if "pio" in what:
        fuzzloops.parallel_foreach(hsio032.configs, fuzz_pio)
        hsio032.drop_default_drive()


if __name__ == "__main__":
    main()
