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

# LFCPNX-100 LRAM sites, found with single sv2udb builds over a window around
# each LRAM tile (Radiant warns 'Invalid site ... left unplaced' for the others):
#   right edge: tile CIB_R{r}C159 -> site LRAM_CORE_R{r}C158   (0, -1)
#   top edge:   tile CIB_R0C89    -> site LRAM_CORE_R1C90      (+1, +1)
#               tile CIB_R0C{c}   -> site LRAM_CORE_R1C{c}     (+1, 0) for c = 105, 110, 125
configs = [
    ("LRAM_CORE_R21C158", "LRAM0", FuzzConfig(job="LRAM0", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R21C159:LRAM_0"])),
    ("LRAM_CORE_R41C158", "LRAM1", FuzzConfig(job="LRAM1", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R41C159:LRAM_1"])),
    ("LRAM_CORE_R57C158", "LRAM2", FuzzConfig(job="LRAM2", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R57C159:LRAM_2"])),
    ("LRAM_CORE_R1C90",   "LRAM3", FuzzConfig(job="LRAM3", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R0C89:LRAM_3"])),
    ("LRAM_CORE_R1C105",  "LRAM4", FuzzConfig(job="LRAM4", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R0C105:LRAM_4"])),
    ("LRAM_CORE_R1C110",  "LRAM5", FuzzConfig(job="LRAM5", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R0C110:LRAM_5"])),
    ("LRAM_CORE_R1C125",  "LRAM6", FuzzConfig(job="LRAM6", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=["CIB_R0C125:LRAM_6"])),
]

def main():
    def per_config(x):
        site, lram, cfg = x
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "lram.v"

        def get_substs(mode="NONE", kv=None, mux=False):
            if kv is None:
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
            return dict(cmt="//" if mode == "NONE" else "", config=config, site=site)
        modes = ["NONE", "LRAM_CORE"]
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.MODE".format(lram), modes,
            lambda x: get_substs(mode=x), False,
            desc="{} primitive mode".format(lram))
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.ASYNC_RST_RELEASE".format(lram), ["SYNC", "ASYNC"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("ASYNC_RST_RELEASE", x)), False,
            desc="LRAM reset release configuration")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.DATA_PRESERVE".format(lram), ["DISABLE", "ENABLE"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("DATA_PRESERVE", x)), False,
            desc="LRAM data preservation across resets")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.EBR_SP_EN".format(lram), ["DISABLE", "ENABLE"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("EBR_SP_EN", x)), False,
            desc="EBR single port mode")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.ECC_BYTE_SEL".format(lram), ["ECC_EN", "BYTE_EN"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("ECC_BYTE_SEL", x)), False,
            desc="")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.GSR".format(lram), ["ENABLED", "DISABLED"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("GSR", x)), False,
            desc="LRAM global set/reset mask")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.OUT_REGMODE_A".format(lram), ["NO_REG", "OUT_REG"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("OUT_REGMODE_A", x)), False,
            desc="LRAM output pipeline register A enable")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.OUT_REGMODE_B".format(lram), ["NO_REG", "OUT_REG"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("OUT_REGMODE_B", x)), False,
            desc="LRAM output pipeline register B enable")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.RESETMODE".format(lram), ["SYNC", "ASYNC"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("RESETMODE", x)), False,
            desc="LRAM sync/async reset select")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.RST_AB_EN".format(lram), ["RESET_AB_DISABLE", "RESET_AB_ENABLE"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("RST_AB_EN", x)), False,
            desc="LRAM reset A/B enable")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.SP_EN".format(lram), ["DISABLE", "ENABLE"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("SP_EN", x)), False,
            desc="LRAM single port mode")
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.UNALIGNED_READ".format(lram), ["DISABLE", "ENABLE"],
            lambda x: get_substs(mode="LRAM_CORE", kv=("UNALIGNED_READ", x)), False,
            desc="LRAM unaligned read support")
        # Radiant 2026.1: CEA/CEB/OCEA/OCEB accept no programming at all on LFCPNX
        # (not signal, inverted, tied low or tied high), so they have no mux here.
        for port in ("CLK", "CSA", "CSB", "RSTA", "RSTB", "WEA", "WEB"):
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}MUX".format(lram, port), [port, "INV"],
                lambda x: get_substs(mode="LRAM_CORE", kv=(port, x), mux=True), False,
                desc="LRAM {} inversion control".format(port))
    fuzzloops.parallel_foreach(configs, per_config)
if __name__ == "__main__":
    main()
