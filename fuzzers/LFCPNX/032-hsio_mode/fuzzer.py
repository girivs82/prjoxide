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
    # ONLY_ENUM=<regex>: fuzz only the settings whose name matches (to redo some of them)
    if os.environ.get("ONLY_ENUM") and not re.search(os.environ["ONLY_ENUM"], name):
        return
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

# Generated from the LFCPNX-100 LFG672 pinout: one A/B pad pair per SYSIO tile type.
# Upstream LFCPNX SYSIO tiles have no PIO enums at all, so every type is fuzzed.
configs = [
    ("A", "V24", # PB2A
        FuzzConfig(job="PB2A_B5_0_B5_1_V18_51", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C2:SYSIO_B5_0', 'CIB_R74C3:SYSIO_B5_1_V18_51'])),
    ("B", "V25", # PB2B
        FuzzConfig(job="PB2B_B5_0_B5_1_V18_51", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C2:SYSIO_B5_0', 'CIB_R74C3:SYSIO_B5_1_V18_51'])),
    ("A", "V23", # PB4A
        FuzzConfig(job="PB4A_B5_0_B5_1_DQS0", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C4:SYSIO_B5_0', 'CIB_R74C5:SYSIO_B5_1_DQS0'])),
    ("B", "V22", # PB4B
        FuzzConfig(job="PB4B_B5_0_B5_1_DQS0", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C4:SYSIO_B5_0', 'CIB_R74C5:SYSIO_B5_1_DQS0'])),
    ("A", "U26", # PB6A
        FuzzConfig(job="PB6A_B5_0_DQS1_B5_1_DQS2", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C6:SYSIO_B5_0_DQS1', 'CIB_R74C7:SYSIO_B5_1_DQS2'])),
    ("B", "V26", # PB6B
        FuzzConfig(job="PB6B_B5_0_DQS1_B5_1_DQS2", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C6:SYSIO_B5_0_DQS1', 'CIB_R74C7:SYSIO_B5_1_DQS2'])),
    ("A", "W25", # PB8A
        FuzzConfig(job="PB8A_B5_0_DQS3_B5_1_DQS4", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C8:SYSIO_B5_0_DQS3', 'CIB_R74C9:SYSIO_B5_1_DQS4'])),
    ("B", "W26", # PB8B
        FuzzConfig(job="PB8B_B5_0_DQS3_B5_1_DQS4", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C8:SYSIO_B5_0_DQS3', 'CIB_R74C9:SYSIO_B5_1_DQS4'])),
    ("A", "W24", # PB10A
        FuzzConfig(job="PB10A_B5_0_B5_1", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C10:SYSIO_B5_0', 'CIB_R74C11:SYSIO_B5_1'])),
    ("B", "W23", # PB10B
        FuzzConfig(job="PB10B_B5_0_B5_1", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C10:SYSIO_B5_0', 'CIB_R74C11:SYSIO_B5_1'])),
    ("A", "AC20", # PB48A
        FuzzConfig(job="PB48A_B5_0_B5_1_V18", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C48:SYSIO_B5_0', 'CIB_R74C49:SYSIO_B5_1_V18'])),
    ("B", "AB20", # PB48B
        FuzzConfig(job="PB48B_B5_0_B5_1_V18", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C48:SYSIO_B5_0', 'CIB_R74C49:SYSIO_B5_1_V18'])),
    ("A", "AE22", # PB50A
        FuzzConfig(job="PB50A_B4_0_B4_1_V18", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C50:SYSIO_B4_0', 'CIB_R74C51:SYSIO_B4_1_V18'])),
    ("B", "AE23", # PB50B
        FuzzConfig(job="PB50B_B4_0_B4_1_V18", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C50:SYSIO_B4_0', 'CIB_R74C51:SYSIO_B4_1_V18'])),
    ("A", "AD21", # PB52A
        FuzzConfig(job="PB52A_B4_0_B4_1_DQS0", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C52:SYSIO_B4_0', 'CIB_R74C53:SYSIO_B4_1_DQS0'])),
    ("B", "AE21", # PB52B
        FuzzConfig(job="PB52B_B4_0_B4_1_DQS0", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C52:SYSIO_B4_0', 'CIB_R74C53:SYSIO_B4_1_DQS0'])),
    ("A", "AF22", # PB54A
        FuzzConfig(job="PB54A_B4_0_DQS1_B4_1_DQS2", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C54:SYSIO_B4_0_DQS1', 'CIB_R74C55:SYSIO_B4_1_DQS2'])),
    ("B", "AF23", # PB54B
        FuzzConfig(job="PB54B_B4_0_DQS1_B4_1_DQS2", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C54:SYSIO_B4_0_DQS1', 'CIB_R74C55:SYSIO_B4_1_DQS2'])),
    ("A", "AD20", # PB56A
        FuzzConfig(job="PB56A_B4_0_DQS3_B4_1_DQS4", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C56:SYSIO_B4_0_DQS3', 'CIB_R74C57:SYSIO_B4_1_DQS4'])),
    ("B", "AC19", # PB56B
        FuzzConfig(job="PB56B_B4_0_DQS3_B4_1_DQS4", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C56:SYSIO_B4_0_DQS3', 'CIB_R74C57:SYSIO_B4_1_DQS4'])),
    ("A", "AB19", # PB58A
        FuzzConfig(job="PB58A_B4_0_B4_1", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C58:SYSIO_B4_0', 'CIB_R74C59:SYSIO_B4_1'])),
    ("B", "AB18", # PB58B
        FuzzConfig(job="PB58B_B4_0_B4_1", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C58:SYSIO_B4_0', 'CIB_R74C59:SYSIO_B4_1'])),
    ("A", "W17", # PB62A
        FuzzConfig(job="PB62A_B4_0_B4_1_DQS0_MID", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C62:SYSIO_B4_0', 'CIB_R74C63:SYSIO_B4_1_DQS0_MID'])),
    ("B", "W18", # PB62B
        FuzzConfig(job="PB62B_B4_0_B4_1_DQS0_MID", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C62:SYSIO_B4_0', 'CIB_R74C63:SYSIO_B4_1_DQS0_MID'])),
    ("A", "AF19", # PB64A
        FuzzConfig(job="PB64A_B4_0_DQS1_MID_B4_1_DQS2_MID", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C64:SYSIO_B4_0_DQS1_MID', 'CIB_R74C65:SYSIO_B4_1_DQS2_MID'])),
    ("B", "AE19", # PB64B
        FuzzConfig(job="PB64B_B4_0_DQS1_MID_B4_1_DQS2_MID", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C64:SYSIO_B4_0_DQS1_MID', 'CIB_R74C65:SYSIO_B4_1_DQS2_MID'])),
    ("A", "AF21", # PB66A
        FuzzConfig(job="PB66A_B4_0_DQS3_MID_B4_1_DQS4_MID", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C66:SYSIO_B4_0_DQS3_MID', 'CIB_R74C67:SYSIO_B4_1_DQS4_MID'])),
    ("B", "AF20", # PB66B
        FuzzConfig(job="PB66B_B4_0_DQS3_MID_B4_1_DQS4_MID", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C66:SYSIO_B4_0_DQS3_MID', 'CIB_R74C67:SYSIO_B4_1_DQS4_MID'])),
    ("A", "Y12", # PB108A
        FuzzConfig(job="PB108A_B4_0_B4_1_V18_42", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C108:SYSIO_B4_0', 'CIB_R74C109:SYSIO_B4_1_V18_42'])),
    ("B", "W12", # PB108B
        FuzzConfig(job="PB108B_B4_0_B4_1_V18_42", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C108:SYSIO_B4_0', 'CIB_R74C109:SYSIO_B4_1_V18_42'])),
    ("A", "AA12", # PB110A
        FuzzConfig(job="PB110A_B3_0_B3_1_V18", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C110:SYSIO_B3_0', 'CIB_R74C111:SYSIO_B3_1_V18'])),
    ("B", "AB12", # PB110B
        FuzzConfig(job="PB110B_B3_0_B3_1_V18", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C110:SYSIO_B3_0', 'CIB_R74C111:SYSIO_B3_1_V18'])),
    ("A", "AC12", # PB112A
        FuzzConfig(job="PB112A_B3_0_B3_1_DQS0", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C112:SYSIO_B3_0', 'CIB_R74C113:SYSIO_B3_1_DQS0'])),
    ("B", "AD12", # PB112B
        FuzzConfig(job="PB112B_B3_0_B3_1_DQS0", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C112:SYSIO_B3_0', 'CIB_R74C113:SYSIO_B3_1_DQS0'])),
    ("A", "AF12", # PB114A
        FuzzConfig(job="PB114A_B3_0_DQS1_B3_1_DQS2", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C114:SYSIO_B3_0_DQS1', 'CIB_R74C115:SYSIO_B3_1_DQS2'])),
    ("B", "AF11", # PB114B
        FuzzConfig(job="PB114B_B3_0_DQS1_B3_1_DQS2", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C114:SYSIO_B3_0_DQS1', 'CIB_R74C115:SYSIO_B3_1_DQS2'])),
    ("A", "AD11", # PB116A
        FuzzConfig(job="PB116A_B3_0_DQS3_B3_1_DQS4", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C116:SYSIO_B3_0_DQS3', 'CIB_R74C117:SYSIO_B3_1_DQS4'])),
    ("B", "AE11", # PB116B
        FuzzConfig(job="PB116B_B3_0_DQS3_B3_1_DQS4", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C116:SYSIO_B3_0_DQS3', 'CIB_R74C117:SYSIO_B3_1_DQS4'])),
    ("A", "AB11", # PB118A
        FuzzConfig(job="PB118A_B3_0_B3_1", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C118:SYSIO_B3_0', 'CIB_R74C119:SYSIO_B3_1'])),
    ("B", "AC11", # PB118B
        FuzzConfig(job="PB118B_B3_0_B3_1", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C118:SYSIO_B3_0', 'CIB_R74C119:SYSIO_B3_1'])),
    ("A", "AD5", # PB144A
        FuzzConfig(job="PB144A_B3_0_B3_1_ECLK_R", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C144:SYSIO_B3_0', 'CIB_R74C145:SYSIO_B3_1_ECLK_R'])),
    ("B", "AE5", # PB144B
        FuzzConfig(job="PB144B_B3_0_B3_1_ECLK_R", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C144:SYSIO_B3_0', 'CIB_R74C145:SYSIO_B3_1_ECLK_R'])),
    ("A", "AD3", # PB156A
        FuzzConfig(job="PB156A_B3_0_B3_1_V18_32", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C156:SYSIO_B3_0', 'CIB_R74C157:SYSIO_B3_1_V18_32'])),
    ("B", "AE3", # PB156B
        FuzzConfig(job="PB156B_B3_0_B3_1_V18_32", device="LFCPNX-100", sv="../shared/empty_100.v", tiles=['CIB_R74C156:SYSIO_B3_0', 'CIB_R74C157:SYSIO_B3_1_V18_32'])),
]

seio_types = [
    ("LVCMOS18H", 1.8, None),
    ("LVCMOS15H", 1.5, None),
    ("LVCMOS12H", 1.2, None),
    ("LVCMOS10H", 1.0, None),
    ("LVCMOS10R", 1.8, ["INPUT"]),
    ("SSTL135_I", 1.35, None),
    ("SSTL135_II", 1.35, None),
    ("SSTL15_I", 1.5, None),
    ("SSTL15_II", 1.5, None),
    ("HSTL15_I", 1.5, None),
    ("HSUL12", 1.2, None),
#    ("MIPI_DPHY", 1.2, None),
#    ("VREF1_DRIVER", 1.5, ["OUTPUT"]),
#    ("VREF2_DRIVER", 1.5, ["OUTPUT"]),
]

diffio_types = [
    ("LVDS", 1.8, None),
    ("SUBLVDS", 1.8, ["INPUT"]),
    ("SUBLVDSEH", 1.8, ["OUTPUT"]),
    ("SLVS", 1.2, None),
    ("MIPI_DPHY", 1.2, None),
    ("SSTL135D_I", 1.35, None),
    ("SSTL135D_II", 1.35, None),
    ("SSTL15D_I", 1.5, None),
    ("SSTL15D_II", 1.5, None),
    ("HSTL15D_I", 1.5, None),
    ("HSUL12D", 1.2, None),
]
DEFAULT_DRIVE = "DEFAULT"


def drop_default_drive():
    """Remove the DEFAULT_DRIVE helper option from the SEIO18 DRIVE enums."""
    import glob
    root = os.path.join(_database.get_db_root(), "LFCPNX", "tiletypes")
    for fn in glob.glob(os.path.join(root, "SYSIO_B[345]_*.ron")):
        t = open(fn).read()
        t2 = re.sub(r'\n        "{}": \[[^\n]*\],'.format(DEFAULT_DRIVE), "", t)
        if t2 != t:
            open(fn, "w").write(t2)


def main():
    def per_config(config):
        pio, site, cfg = config
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "iob_100.v"
        def get_bank_vccio(iotype):
            if iotype == "NONE":
                return "1.8"
            else:
                for t, v, d in (seio_types + diffio_types):
                    if t == iotype:
                        return str(v)
        def is_diff(iotype):
            for t, v, d in diffio_types:
                if t == iotype:
                    return True
            return False
        def get_substs(iotype="BIDIR_LVCMOS18H", kv=None, vcc=None, tmux="T"):
            iodir, iostd = iotype.split("_", 1) if iotype != "NONE" else ("","")
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
            if is_diff(iostd):
                primtype = "DIFFIO18A_CORE"
            else:
                primtype = "SEIO18A_CORE"
            return dict(cmt="//" if iotype == "NONE" else "",
                pintype=pintype, primtype=primtype, site=site, iotype=iostd, t=t, extra_config=extra_config, vcc=vcc)
        all_se_types = ["NONE"]
        all_di_types = ["NONE"]
        for t, v, d in seio_types:
            if d is None:
                all_se_types += ["INPUT_{}".format(t), "BIDIR_{}".format(t), "OUTPUT_{}".format(t)]
            else:
                all_se_types += ["{}_{}".format(di, t) for di in d]
        for t, v, d in diffio_types:
            if d is None:
                all_di_types += ["INPUT_{}".format(t), "BIDIR_{}".format(t), "OUTPUT_{}".format(t)]
            else:
                all_di_types += ["{}_{}".format(di, t) for di in d]

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.BASE_TYPE".format(pio), all_se_types,
                lambda x: get_substs(iotype=x), False, assume_zero_base=True)

        # DRIVE: the design with DRIVE unset (Radiant's default, which the BASE_TYPE options were
        # fuzzed with) is an extra sample, so bits that every DRIVE value changes from that default
        # stay in the options (e.g. LVCMOS10H, whose 2 and 4 mA both clear F13B1 of the default);
        # the helper option is removed from the database afterwards (drop_default_drive)
        for drv, iot, vals in (("1V8", "OUTPUT_LVCMOS18H", ["2", "4", "8", "12", "50RS"]),
                               ("1V5", "OUTPUT_LVCMOS15H", ["2", "4", "8"]),
                               ("1V2", "OUTPUT_LVCMOS12H", ["2", "4", "8"]),
                               ("1V0", "OUTPUT_LVCMOS10H", ["2", "4"]),
                               ("HSUL12", "OUTPUT_HSUL12", ["4", "6", "8"])):
            nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.DRIVE_{}".format(pio, drv), [DEFAULT_DRIVE] + vals,
                    lambda x, iot=iot: get_substs(iotype=iot, kv=None if x == DEFAULT_DRIVE else ("DRIVE", x)), True)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.PULLMODE".format(pio), ["NONE", "UP", "DOWN", "KEEPER"],
                lambda x: get_substs(iotype="INPUT_LVCMOS18H", kv=("PULLMODE", x)), True)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.UNDERDRIVE_1V8".format(pio), ["ON", "OFF"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS18H" if x=="OFF" else "INPUT_LVCMOS15H", vcc="1.8"), True)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.SLEWRATE".format(pio), ["SLOW", "MED", "FAST"],
                lambda x: get_substs(iotype="OUTPUT_LVCMOS18H", kv=("SLEWRATE", x)), True)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.TERMINATION_1V8".format(pio), ["OFF", "40", "50", "60", "75", "150"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS18H", kv=("TERMINATION", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.TERMINATION_1V5".format(pio), ["OFF", "40", "50", "60", "75"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS15H", kv=("TERMINATION", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.TERMINATION_1V35".format(pio), ["OFF", "40", "50", "60", "75"],
                        lambda x: get_substs(iotype="INPUT_SSTL135_I", kv=("TERMINATION", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.TERMINATION_1V2".format(pio), ["OFF", "40", "50", "60", "75"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS12H", kv=("TERMINATION", x)), False)


        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.DFTDO2DI".format(pio), ["DISABLED", "ENABLED"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS18H", kv=("DFTDO2DI", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.LOOPBKCD2AB".format(pio), ["DISABLED", "ENABLED"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS18H", kv=("LOOPBKCD2AB", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.OPENDRAIN".format(pio), ["OFF", "ON"],
                        lambda x: get_substs(iotype="OUTPUT_LVCMOS18H", kv=("OPENDRAIN", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.SLEEPHIGHLEAKAGE".format(pio), ["DISABLED", "ENABLED"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS18H", kv=("SLEEPHIGHLEAKAGE", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.ENADC_IN".format(pio), ["DISABLED", "ENABLED"],
                        lambda x: get_substs(iotype="INPUT_LVCMOS18H", kv=("ENADC_IN", x)), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.INT_LPBK".format(pio), ["DISABLED", "ENABLED"],
                    lambda x: get_substs(iotype="INPUT_LVCMOS18H", kv=("INT_LPBK", x)), False)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.SEIO18.VREF".format(pio), ["OFF", "VREF1_LOAD", "VREF2_LOAD"],
            lambda x: get_substs(iotype="INPUT_SSTL135_I", kv=("VREF", x)), False)

        nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.TMUX".format(pio), ["T", "INV"],
                    lambda x: get_substs(iotype="BIDIR_LVCMOS18H", tmux=x), False)

        if pio == "A":
            nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DIFFIO18.BASE_TYPE".format(pio), all_di_types,
                            lambda x: get_substs(iotype=x), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DIFFIO18.PULLMODE".format(pio), ["NONE", "FAILSAFE"],
                            lambda x: get_substs(iotype="INPUT_LVDS", kv=("PULLMODE", x)), True)
            nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DIFFIO18.DIFFRESISTOR".format(pio), ["OFF", "100"],
                            lambda x: get_substs(iotype="INPUT_LVDS", kv=("DIFFRESISTOR", x)), True)
            nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DIFFIO18.DIFFDRIVE_MIPI_DPHY".format(pio), ["NA", "2P0"],
                            lambda x: get_substs(iotype="OUTPUT_MIPI_DPHY", kv=("DIFFDRIVE", x.replace("P", "."))), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DIFFIO18.DIFFDRIVE_SLVS".format(pio), ["NA", "2P0"],
                            lambda x: get_substs(iotype="OUTPUT_SLVS", kv=("DIFFDRIVE", x.replace("P", "."))), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DIFFIO18.DIFFDRIVE_LVDS".format(pio), ["NA", "3P5"],
                            lambda x: get_substs(iotype="OUTPUT_LVDS", kv=("DIFFDRIVE", x.replace("P", "."))), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DIFFIO18.DIFFRX_INV".format(pio), ["NORMAL", "INVERT"],
                            lambda x: get_substs(iotype="INPUT_LVDS", kv=("DIFFRX_INV", x)), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "PIO{}.DIFFIO18.DIFFTX_INV".format(pio), ["NORMAL", "INVERT"],
                            lambda x: get_substs(iotype="OUTPUT_LVDS", kv=("DIFFTX_INV", x)), False)
    fuzzloops.parallel_foreach(configs, per_config)
    drop_default_drive()
if __name__ == "__main__":
    main()
