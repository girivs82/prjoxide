from fuzzconfig import FuzzConfig
import nonrouting
import fuzzloops
import re

# LFCPNX / Radiant 2026.1 rejects some LIFCL options (e.g. SEIO33 BANK_VCCIO=1.0).
# Pre-build every option (the bitstream cache makes the real run reuse these)
# and drop the ones Radiant refuses, instead of crashing the worker thread.
import os, threading
_fuzz_enum_setting = nonrouting.fuzz_enum_setting
import subprocess, string, database as _database
def _retry_build(config, substs, prefix):
    """Rebuild one design with Radiant's output captured; returns (bitfile exists, Radiant ERROR lines)."""
    subst = dict(substs)
    subst.setdefault("arcs_attr", "")
    subst.setdefault("device", config.device)
    desfile = os.path.join(config.workdir, prefix + "design.v")
    bitfile = os.path.join(config.workdir, prefix + "design.bit")
    logfile = os.path.join(config.workdir, prefix + "design.log")
    if os.path.exists(bitfile):
        os.remove(bitfile)
    with open(config.sv) as inf, open(desfile, "w") as ouf:
        ouf.write(string.Template(inf.read()).substitute(**subst))
    env = os.environ.copy()
    if config.struct_mode:
        env["STRUCT_VER"] = "1"
    if config.rbk_mode:
        env["RBK_MODE"] = "1"
    r = subprocess.run(["bash", os.path.join(_database.get_oxide_root(), "radiant.sh"), config.device, desfile],
                       env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    with open(logfile, "w") as lf:
        lf.write(r.stdout)
    errors = [l for l in r.stdout.splitlines() if re.match(r"ERROR <\d+>", l)]
    return os.path.exists(bitfile), errors
def _robust_enum_setting(config, empty_bitfile, name, values, get_sv_substs, *args, **kwargs):
    if kwargs.get("min_cover"):
        # callers using min_cover pass tuples to get_sv_substs; leave those alone
        return _fuzz_enum_setting(config, empty_bitfile, name, values, get_sv_substs, *args, **kwargs)
    ok = []
    for v in values:
        bit = config.build_design(config.sv, get_sv_substs(v), "chk{}_{}_".format(threading.get_ident(), v))
        if os.path.exists(bit):
            ok.append(v)
            continue
        # No bitstream: retry once with a fresh prefix and Radiant's output captured, so a
        # transient failure can't turn into a silently missing option.
        built, errors = _retry_build(config, get_sv_substs(v), "chkretry{}_{}_".format(threading.get_ident(), v))
        if built:
            print("RETRY-OK {} = {} (first pre-check build produced no bitstream)".format(name, v), flush=True)
            ok.append(v)
        elif errors:
            print("SKIP {} = {} (rejected by Radiant: {})".format(name, v, errors[0]), flush=True)
        else:
            raise RuntimeError("{} = {}: no bitstream on retry and no Radiant ERROR line; "
                               "transient failure? see chkretry*_{}_design.log".format(name, v, v))
    if not any(v != "NONE" for v in ok):
        # Every real option failed: almost certainly a template/primitive problem
        # (unknown module, DRC), not illegal settings. Stop instead of skipping.
        raise RuntimeError("all options of {} rejected; check the Radiant logs".format(name))
    if len(ok) < 2:
        print("SKIP {}: fewer than two legal values".format(name), flush=True)
        return
    return _fuzz_enum_setting(config, empty_bitfile, name, ok, get_sv_substs, *args, **kwargs)
nonrouting.fuzz_enum_setting = _robust_enum_setting

configs = [
    # LFCPNX EBR row 11, group at C14..C25 (same layout as LIFCL's C26..C37, SPINE_L0 replaced by MIB_EBR)
    ("EBR_CORE_R10C14", "EBR0", FuzzConfig(job="EBRMODE0", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R11C14:MIB_EBR", "CIB_R11C15:EBR_1", "CIB_R11C16:EBR_2"])),
    ("EBR_CORE_R10C17", "EBR1", FuzzConfig(job="EBRMODE1", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R11C17:MIB_EBR", "CIB_R11C18:EBR_4", "CIB_R11C19:EBR_5"])),
    ("EBR_CORE_R10C20", "EBR2", FuzzConfig(job="EBRMODE2", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R11C20:MIB_EBR", "CIB_R11C21:EBR_7", "CIB_R11C22:EBR_8", "CIB_R11C23:EBR_9", "CIB_R11C24:EBR_10", "CIB_R11C25:MIB_EBR"])),
    ("EBR_CORE_R10C22", "EBR3", FuzzConfig(job="EBRMODE3", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R11C20:MIB_EBR", "CIB_R11C21:EBR_7", "CIB_R11C22:EBR_8", "CIB_R11C23:EBR_9", "CIB_R11C24:EBR_10", "CIB_R11C25:MIB_EBR"])),
]

# These config sets create a minimum bit change for mode fuzzing.
# Radiant 2026.1 FIFO16K_MODE uses write/read names (DATA_WIDTH_W/R, CLKW/CLKR,
# RSTW/RPRST, single OUTREG/RESETMODE/ASYNC_RST_RELEASE) instead of the A/B names
# LIFCL's 060 uses; the A/B names are rejected (ERROR 1051343). PDP16K_MODE and
# PDPSC16K_MODE have no WE pin in Radiant 2026.1 (writes are gated by CEW).
defaults = {
    "NONE": "",
    "DP16K_MODE": "DP16K_MODE:::DATA_WIDTH_A=X18,DATA_WIDTH_B=X18,INIT_DATA=NO_INIT,WID=0b00000000000:CLKA=0,CLKB=0",
    "PDP16K_MODE": "PDP16K_MODE:::DATA_WIDTH_R=X36,DATA_WIDTH_W=X36,INIT_DATA=NO_INIT,WID=0b00000000000:CLKR=0,CLKW=0",
    "PDPSC16K_MODE": "PDPSC16K_MODE:::DATA_WIDTH_R=X36,DATA_WIDTH_W=X36,INIT_DATA=NO_INIT,WID=0b00000000000:CLK=0",
    "SP16K_MODE": "SP16K_MODE:::DATA_WIDTH=X18,INIT_DATA=NO_INIT,WID=0b00000000000:CLK=0",
    "FIFO16K_MODE": "FIFO16K_MODE:::FULLBITS=0b00000000000000,DATA_WIDTH_W=X36,DATA_WIDTH_R=X36 FIFO16K_MODE::::CLKW=0,CLKR=0"
}

def main():
    def per_config(x):
        site, ebr, cfg = x
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "ebr.v"

        def get_substs(mode="NONE", default_cfg=False, kv=None, mux=False):
            if default_cfg:
                config = defaults[mode]
            elif kv is None:
                config = ""
            elif mux:
                val = "#SIG"
                if kv[1] in ("0", "1"):
                    val = kv[1]
                if kv[1] == "INV":
                    val = "#INV"
                config = "{}::::{}={}".format(mode, kv[0], val)
            else:
                config = "{}:::{}={}".format(mode, kv[0], kv[1])
            return dict(mode=mode, cmt="//" if mode == "NONE" else "", config=config, site=site)
        modes = ["NONE", "DP16K_MODE", "PDP16K_MODE", "PDPSC16K_MODE", "SP16K_MODE", "FIFO16K_MODE"]
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.MODE".format(ebr), modes,
            lambda x: get_substs(x, default_cfg=True), False,
            desc="{} primitive mode".format(ebr))
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.DP16K_MODE.DATA_WIDTH_A".format(ebr), ["X1", "X2", "X4", "X9", "X18"],
            lambda x: get_substs(mode="DP16K_MODE", kv=("DATA_WIDTH_A", x)), False,
            desc="data width of port A in DP16K_MODE")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.DP16K_MODE.DATA_WIDTH_B".format(ebr), ["X1", "X2", "X4", "X9", "X18"],
            lambda x: get_substs(mode="DP16K_MODE", kv=("DATA_WIDTH_B", x)), False,
            desc="data width of port B in DP16K_MODE")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.PDP16K_MODE.DATA_WIDTH_W".format(ebr), ["X1", "X2", "X4", "X9", "X18", "X32", "X36"],
            lambda x: get_substs(mode="PDP16K_MODE", kv=("DATA_WIDTH_W", x)), False,
            desc="data width of write port in PDP16K_MODE")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.PDP16K_MODE.DATA_WIDTH_R".format(ebr), ["X1", "X2", "X4", "X9", "X18", "X32", "X36"],
            lambda x: get_substs(mode="PDP16K_MODE", kv=("DATA_WIDTH_R", x)), False,
            desc="data width of read port in PDP16K_MODE")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.PDPSC16K_MODE.DATA_WIDTH_W".format(ebr), ["X1", "X2", "X4", "X9", "X18", "X32", "X36"],
            lambda x: get_substs(mode="PDPSC16K_MODE", kv=("DATA_WIDTH_W", x)), False,
            desc="data width of write port in PDPSC16K_MODE")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.PDPSC16K_MODE.DATA_WIDTH_R".format(ebr), ["X1", "X2", "X4", "X9", "X18", "X32", "X36"],
            lambda x: get_substs(mode="PDPSC16K_MODE", kv=("DATA_WIDTH_R", x)), False,
            desc="data width of read port in PDPSC16K_MODE")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.SP16K_MODE.DATA_WIDTH".format(ebr), ["X1", "X2", "X4", "X9", "X18"],
            lambda x: get_substs(mode="SP16K_MODE", kv=("DATA_WIDTH", x)), False,
            desc="data width of R/W port in SP16K_MODE")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.FIFO16K_MODE.DATA_WIDTH_W".format(ebr), ["X1", "X2", "X4", "X9", "X18", "X32", "X36"],
            lambda x: get_substs(mode="FIFO16K_MODE", kv=("DATA_WIDTH_W", x)), False,
            desc="data width of write port in FIFO16K_MODE")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.FIFO16K_MODE.DATA_WIDTH_R".format(ebr), ["X1", "X2", "X4", "X9", "X18", "X32", "X36"],
            lambda x: get_substs(mode="FIFO16K_MODE", kv=("DATA_WIDTH_R", x)), False,
            desc="data width of read port in FIFO16K_MODE")

        for mode, clksigs in [("DP16K_MODE", ["CLKA", "CLKB"]),
                                ("PDP16K_MODE", ["CLKW", "CLKR"]),
                                ("PDPSC16K_MODE", ["CLK"]),
                                ("SP16K_MODE", ["CLK"]),
                                ("FIFO16K_MODE", ["CLKW", "CLKR"])]:
            for sig in clksigs:
                nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}.{}MUX".format(ebr, mode, sig), ["0", sig, "INV"],
                    lambda x: get_substs(mode=mode, kv=(sig, x), mux=True), False,
                    desc="clock inversion control for {}".format(sig))
        for mode, cwesigs in [("DP16K_MODE", ["WEA", "WEB", "CEA", "CEB", "RSTA", "RSTB", "ADA0", "ADA1", "ADA2", "ADA3", "ADB0", "ADB1"]),
                                ("PDP16K_MODE", ["CER", "CEW", "RST", "ADW0", "ADW1", "ADW2", "ADW3", "ADR0", "ADR1"]),
                                ("PDPSC16K_MODE", ["CER", "CEW", "RST", "ADW0", "ADW1", "ADW2", "ADW3", "ADR0", "ADR1"]),
                                ("SP16K_MODE", ["WE", "CE", "RST", "AD0", "AD1", "AD2", "AD3"]),
                                ("FIFO16K_MODE", ["RSTW", "RPRST"])]:
            for sig in cwesigs:
                nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}.{}MUX".format(ebr, mode, sig), [sig, "INV"],
                    lambda x: get_substs(mode=mode, kv=(sig, x), mux=True), False)

        for mode, outregs in [("DP16K_MODE", ["OUTREG_A", "OUTREG_B"]),
                                ("PDP16K_MODE", ["OUTREG"]),
                                ("PDPSC16K_MODE", ["OUTREG"]),
                                ("SP16K_MODE", ["OUTREG"]),
                                ("FIFO16K_MODE", ["OUTREG"])]:
            for outreg in outregs:
                nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}.{}".format(ebr, mode, outreg), ["USED", "BYPASSED"],
                    lambda x: get_substs(mode=mode, kv=(outreg, x)), False,
                    desc="extra output pipeline register enable/bypass")

        for mode, ports in [("DP16K_MODE", ["_A", "_B"]),
                                ("PDP16K_MODE", [""]),
                                ("PDPSC16K_MODE", [""]),
                                ("SP16K_MODE", [""]),
                                ("FIFO16K_MODE", [""])]:
            for port in ports:
                nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}.RESETMODE{}".format(ebr, mode, port), ["ASYNC", "SYNC"],
                    lambda x: get_substs(mode=mode, kv=("RESETMODE{}".format(port), x)), False)
                nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}.ASYNC_RST_RELEASE{}".format(ebr, mode, port), ["ASYNC", "SYNC"],
                    lambda x: get_substs(mode=mode, kv=("ASYNC_RST_RELEASE{}".format(port), x)), False)

        for mode, csds in [("DP16K_MODE", ["CSDECODE_A", "CSDECODE_B"]),
                                ("PDP16K_MODE", ["CSDECODE_R", "CSDECODE_W"]),
                                ("PDPSC16K_MODE", ["CSDECODE_R", "CSDECODE_W"]),
                                ("SP16K_MODE", ["CSDECODE"]),]:
            for csd in csds:
                nonrouting.fuzz_word_setting(cfg, "{}.{}.{}".format(ebr, mode, csd), 3,
                    lambda x: get_substs(mode=mode, kv=(csd, "".join(reversed(["1" if b else "0" for b in x])))),
                    desc="port is enabled when CS inputs match this value".format(csd))

        nonrouting.fuzz_enum_setting(cfg, empty, "{}.GSR".format(ebr), ["ENABLED", "DISABLED"],
            lambda x: get_substs(mode="DP16K_MODE", kv=("GSR", x)), False,
            desc="if `ENABLED`, then read ports are reset by user GSR")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.INIT_DATA".format(ebr), ["DYNAMIC", "STATIC", "NO_INIT"],
            lambda x: get_substs(mode="DP16K_MODE", kv=("INIT_DATA", x)), False,
            desc="selects initialisation mode")
        nonrouting.fuzz_word_setting(cfg, "{}.WID".format(ebr), 11,
            lambda x: get_substs(mode="DP16K_MODE", kv=("WID", "0b" + "".join(reversed(["1" if b else "0" for b in x])))),
            desc="unique ID for the BRAM, used to initialise it in the bitstream")

        nonrouting.fuzz_word_setting(cfg, "{}.FIFO16K_MODE.FULLBITS".format(ebr), 14,
            lambda x: get_substs(mode="FIFO16K_MODE", kv=("FULLBITS", "0b" + "".join(reversed(["1" if b else "0" for b in x])))),
            desc="FIFO 'full' threshold")
        nonrouting.fuzz_word_setting(cfg, "{}.FIFO16K_MODE.ALMOST_FULL".format(ebr), 14,
            lambda x: get_substs(mode="FIFO16K_MODE", kv=("ALMOST_FULL", "0b" + "".join(reversed(["1" if b else "0" for b in x])))),
            desc="FIFO 'almost full' output threshold")
        nonrouting.fuzz_word_setting(cfg, "{}.FIFO16K_MODE.EMPTYBITS".format(ebr), 5,
            lambda x: get_substs(mode="EBR_CORE", kv=("EMPTY", "0b" + "".join(reversed(["1" if b else "0" for b in x])))),
            desc="FIFO 'empty' threshold")
        nonrouting.fuzz_word_setting(cfg, "{}.FIFO16K_MODE.ALMOST_EMPTY".format(ebr), 14,
            lambda x: get_substs(mode="FIFO16K_MODE", kv=("ALMOST_EMPTY", "0b" + "".join(reversed(["1" if b else "0" for b in x])))),
            desc="FIFO 'almost empty' output threshold")
    fuzzloops.parallel_foreach(configs, per_config)
if __name__ == "__main__":
    main()
