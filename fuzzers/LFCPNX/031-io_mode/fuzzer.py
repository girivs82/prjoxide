from fuzzconfig import FuzzConfig
import nonrouting
import fuzzloops
import re

# LFCPNX / Radiant 2026.1 rejects some LIFCL options (e.g. SEIO33 BANK_VCCIO=1.0).
# Pre-build every option (the bitstream cache makes the real run reuse these)
# and drop the ones Radiant refuses, instead of crashing the worker thread.
import os, threading
_fuzz_enum_setting = nonrouting.fuzz_enum_setting
def _robust_enum_setting(config, empty_bitfile, name, values, get_sv_substs, *args, **kwargs):
    if kwargs.get("min_cover"):
        # callers using min_cover pass tuples to get_sv_substs; leave those alone
        return _fuzz_enum_setting(config, empty_bitfile, name, values, get_sv_substs, *args, **kwargs)
    ok = []
    for v in values:
        bit = config.build_design(config.sv, get_sv_substs(v), "chk{}_{}_".format(threading.get_ident(), v))
        if os.path.exists(bit):
            ok.append(v)
        else:
            print("SKIP {} = {} (rejected by Radiant)".format(name, v), flush=True)
    if not any(v != "NONE" for v in ok):
        # Every real option failed: almost certainly a template/primitive problem
        # (unknown module, DRC), not illegal settings. Stop instead of skipping.
        raise RuntimeError("all options of {} rejected; check the Radiant logs".format(name))
    if len(ok) < 2:
        print("SKIP {}: fewer than two legal values".format(name), flush=True)
        return
    return _fuzz_enum_setting(config, empty_bitfile, name, ok, get_sv_substs, *args, **kwargs)
nonrouting.fuzz_enum_setting = _robust_enum_setting

# Generated from the LFCPNX-100 LFG672 pinout: one A/B pad pair per SYSIO tile type.
# Upstream LFCPNX SYSIO tiles have no PIO enums at all, so every type is fuzzed.
configs = [
    ("A", "G2", # PT134A
        FuzzConfig(job="PT134A_B0_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R0C134:SYSIO_B0_0_EVEN'])),
    ("B", "G4", # PT134B
        FuzzConfig(job="PT134B_B0_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R0C134:SYSIO_B0_0_EVEN'])),
    ("A", "G6", # PT136A
        FuzzConfig(job="PT136A_B0_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R0C136:SYSIO_B0_0_ODD'])),
    ("B", "G5", # PT136B
        FuzzConfig(job="PT136B_B0_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R0C136:SYSIO_B0_0_ODD'])),
    ("A", "H20", # PL3A
        FuzzConfig(job="PL3A_B7_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R3C0:SYSIO_B7_0_EVEN'])),
    ("B", "H21", # PL3B
        FuzzConfig(job="PL3B_B7_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R3C0:SYSIO_B7_0_EVEN'])),
    ("B", "L1", # PR3B
        FuzzConfig(job="PR3B_B1_DED", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R3C159:SYSIO_B1_DED'])),
    ("A", "H22", # PL4A
        FuzzConfig(job="PL4A_B7_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R4C0:SYSIO_B7_0_ODD'])),
    ("B", "H23", # PL4B
        FuzzConfig(job="PL4B_B7_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R4C0:SYSIO_B7_0_ODD'])),
    ("A", "L2", # PR4A
        FuzzConfig(job="PR4A_B1_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R4C159:SYSIO_B1_0_ODD'])),
    ("B", "L3", # PR4B
        FuzzConfig(job="PR4B_B1_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R4C159:SYSIO_B1_0_ODD'])),
    ("A", "L6", # PR6A
        FuzzConfig(job="PR6A_B1_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R6C159:SYSIO_B1_0_EVEN'])),
    ("B", "L7", # PR6B
        FuzzConfig(job="PR6B_B1_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R6C159:SYSIO_B1_0_EVEN'])),
    ("A", "J23", # PL10A
        FuzzConfig(job="PL10A_B7_0_C_B7_0_REM", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R10C0:SYSIO_B7_0_C', 'CIB_R11C0:SYSIO_B7_0_REM'])),
    ("B", "J22", # PL10B
        FuzzConfig(job="PL10B_B7_0_C_B7_0_REM", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R10C0:SYSIO_B7_0_C', 'CIB_R11C0:SYSIO_B7_0_REM'])),
    ("A", "M9", # PR10A
        FuzzConfig(job="PR10A_B1_0_C_B1_0_REM", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R10C159:SYSIO_B1_0_C', 'CIB_R11C159:SYSIO_B1_0_REM'])),
    ("B", "M8", # PR10B
        FuzzConfig(job="PR10B_B1_0_C_B1_0_REM", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R10C159:SYSIO_B1_0_C', 'CIB_R11C159:SYSIO_B1_0_REM'])),
    ("A", "P26", # PL40A
        FuzzConfig(job="PL40A_B6_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R40C0:SYSIO_B6_0_EVEN'])),
    ("B", "P25", # PL40B
        FuzzConfig(job="PL40B_B6_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R40C0:SYSIO_B6_0_EVEN'])),
    ("A", "T3", # PR40A
        FuzzConfig(job="PR40A_B2_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R40C159:SYSIO_B2_0_EVEN'])),
    ("B", "T2", # PR40B
        FuzzConfig(job="PR40B_B2_0_EVEN", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R40C159:SYSIO_B2_0_EVEN'])),
    ("A", "P24", # PL42A
        FuzzConfig(job="PL42A_B6_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R42C0:SYSIO_B6_0_ODD'])),
    ("B", "P23", # PL42B
        FuzzConfig(job="PL42B_B6_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R42C0:SYSIO_B6_0_ODD'])),
    ("A", "T1", # PR42A
        FuzzConfig(job="PR42A_B2_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R42C159:SYSIO_B2_0_ODD'])),
    ("B", "U1", # PR42B
        FuzzConfig(job="PR42B_B2_0_ODD", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R42C159:SYSIO_B2_0_ODD'])),
    ("A", "R20", # PL46A
        FuzzConfig(job="PL46A_B6_0_C_B6_0_REM", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R46C0:SYSIO_B6_0_C', 'CIB_R47C0:SYSIO_B6_0_REM'])),
    ("B", "R21", # PL46B
        FuzzConfig(job="PL46B_B6_0_C_B6_0_REM", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R46C0:SYSIO_B6_0_C', 'CIB_R47C0:SYSIO_B6_0_REM'])),
    ("A", "U6", # PR46A
        FuzzConfig(job="PR46A_B2_0_C_B2_0_REM", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R46C159:SYSIO_B2_0_C', 'CIB_R47C159:SYSIO_B2_0_REM'])),
    ("B", "U7", # PR46B
        FuzzConfig(job="PR46B_B2_0_C_B2_0_REM", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R46C159:SYSIO_B2_0_C', 'CIB_R47C159:SYSIO_B2_0_REM'])),
]

def main():
    def per_config(config):
        pio, site, cfg = config
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "iob_100.v"
        primtype = "SEIO33_CORE"
        def get_bank_vccio(iotype):
            if iotype == "":
                return "3.3"
            iov = iotype[-2:] if iotype[-1].isdigit() else iotype[-3:-1]
            if iov == "10":
                return "1.0"
            return "{}.{}".format(iov[0], iov[1])
        def get_substs(iotype="BIDIR_LVCMOS33", kv=None, vcc=None, tmux="T"):
            iodir, iostd = iotype.split("_", 2) if iotype != "NONE" else ("","")
            if iodir == "INPUT":
                pintype = "input"
                t = "1"
            elif iodir == "OUTPUT":
                pintype = "output"
                t = "0"
            else:
                pintype = "inout"
                if tmux == "INV":
                    t = "#INV"
                else:
                    t = "#SIG"
            if kv is not None:
                extra_config = ",{}={}".format(kv[0], kv[1])
            else:
                extra_config = ""
            if vcc is None:
                vcc = get_bank_vccio(iostd)
            return dict(cmt="//" if iotype == "NONE" else "",
                pintype=pintype, primtype=primtype, site=site, iotype=iostd, t=t, extra_config=extra_config, vcc=vcc)
        seio_types = [
            "NONE",
            "INPUT_LVCMOS10",
            "INPUT_LVCMOS12", "OUTPUT_LVCMOS12", "BIDIR_LVCMOS12",
            "INPUT_LVCMOS15", "OUTPUT_LVCMOS15", "BIDIR_LVCMOS15",
            "INPUT_LVCMOS18", "OUTPUT_LVCMOS18", "BIDIR_LVCMOS18",
            "INPUT_LVCMOS25", "OUTPUT_LVCMOS25", "BIDIR_LVCMOS25",
            "INPUT_LVCMOS33", "OUTPUT_LVCMOS33", "BIDIR_LVCMOS33",
            "OUTPUT_LVCMOS25D", "OUTPUT_LVCMOS33D"
        ]

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.BASE_TYPE".format(pio), seio_types,
                        lambda x: get_substs(iotype=x), False, assume_zero_base=True)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DRIVE_3V3".format(pio), ["2", "4", "8", "12", "50RS"],
                        lambda x: get_substs(iotype="OUTPUT_LVCMOS33", kv=("DRIVE", x)), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DRIVE_2V5".format(pio), ["2", "4", "8", "10", "50RS"],
                        lambda x: get_substs(iotype="OUTPUT_LVCMOS25", kv=("DRIVE", x)), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DRIVE_1V8".format(pio), ["2", "4", "8", "50RS"],
                        lambda x: get_substs(iotype="OUTPUT_LVCMOS18", kv=("DRIVE", x)), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DRIVE_1V5".format(pio), ["2", "4", "8", "12"],
                        lambda x: get_substs(iotype="OUTPUT_LVCMOS15", kv=("DRIVE", x)), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DRIVE_1V2".format(pio), ["2", "4", "8", "12"],
                        lambda x: get_substs(iotype="OUTPUT_LVCMOS12", kv=("DRIVE", x)), True)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.PULLMODE".format(pio), ["NONE", "UP", "DOWN", "KEEPER", "I3C"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS33", kv=("PULLMODE", x)), True)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.HYSTERESIS_3V3".format(pio), ["ON", "OFF"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS33", kv=("HYSTERESIS", x)), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.HYSTERESIS_2V5".format(pio), ["ON", "OFF"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS25", kv=("HYSTERESIS", x)), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.HYSTERESIS_1V8".format(pio), ["ON", "OFF"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS18", kv=("HYSTERESIS", x)), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.HYSTERESIS_1V5".format(pio), ["ON", "OFF"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS15", kv=("HYSTERESIS", x)), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.HYSTERESIS_1V2".format(pio), ["ON", "OFF"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS12", kv=("HYSTERESIS", x)), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.UNDERDRIVE_3V3".format(pio), ["ON", "OFF"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS33" if x=="OFF" else "INPUT_LVCMOS25", vcc="3.3"), True)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.UNDERDRIVE_1V8".format(pio), ["ON", "OFF"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS18" if x=="OFF" else "INPUT_LVCMOS15", vcc="1.8"), True)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.CLAMP".format(pio), ["OFF", "ON"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS33", kv=("CLAMP", x)), True)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DFTDO2DI".format(pio), ["DISABLED", "ENABLED"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS33", kv=("DFTDO2DI", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.GLITCHFILTER".format(pio), ["OFF", "ON"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS33", kv=("GLITCHFILTER", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.LOOPBKCD2AB".format(pio), ["DISABLED", "ENABLED"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS33", kv=("LOOPBKCD2AB", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.OPENDRAIN".format(pio), ["OFF", "ON"],
                        lambda x: get_substs(iotype="OUTPUT_LVCMOS33", kv=("OPENDRAIN", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SLEEPHIGHLEAKAGE".format(pio), ["DISABLED", "ENABLED"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS33", kv=("SLEEPHIGHLEAKAGE", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SLEWRATE".format(pio), ["FAST", "MED", "SLOW"],
                        lambda x: get_substs(iotype="OUTPUT_LVCMOS33", kv=("SLEWRATE", x)), False)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.TERMINATION_1V8".format(pio), ["OFF", "40", "50", "60", "75", "150"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS18", kv=("TERMINATION", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.TERMINATION_1V5".format(pio), ["OFF", "40", "50", "60", "75"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS15", kv=("TERMINATION", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.TERMINATION_1V2".format(pio), ["OFF", "40", "50", "60", "75"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS12", kv=("TERMINATION", x)), False)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.TMUX".format(pio), ["T", "INV"],
                        lambda x: get_substs(iotype="BIDIR_LVCMOS33", tmux=x), False)

    fuzzloops.parallel_foreach(configs, per_config)
if __name__ == "__main__":
    main()
