"""
IO logic (IOLOGIC on HP banks 3-5, SIOLOGIC elsewhere) settings for every LFCPNX SYSIO tile type
with pads: LIFCL's 070-iologic_mode settings (register, DDR, mux and delay-path modes), on
LFCPNX-100 sites and wire names, with the same pre-check / retry / skip handling as 031/032.
"""
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
    shutil.rmtree(os.path.join(config.workdir, prefix + "design.tmp"), ignore_errors=True)
    errors = [l for l in r.stdout.splitlines() if re.match(r"ERROR <\d+>", l)]
    # bitgen segfaults (deterministically) on some IO logic modes with the default settings,
    # e.g. IDDRXN; treat that as Radiant refusing the option
    errors += [l.strip() for l in r.stdout.splitlines() if "Segmentation fault" in l and "bitgen" in l]
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
        # Every option was rejected, each with an explicit Radiant error or a bitgen crash (a
        # missing bitstream without either raises above). For the IO logic this happens for the
        # DDR gearing modes (IDDRXN etc.), which crash bitgen in this structural template: record
        # and continue rather than stop the whole site.
        print("SKIP-ALL {}: every option rejected by Radiant (see SKIP lines)".format(name), flush=True)
        return
    if len(ok) < 2:
        print("SKIP {}: fewer than two legal values".format(name), flush=True)
        return
    return _fuzz_enum_setting(config, empty_bitfile, name, ok, get_sv_substs, *args, **kwargs)
nonrouting.fuzz_enum_setting = _robust_enum_setting

# Keep the work directory small: bitgen's crashes would otherwise leave a ~1 GB core file per
# rejected gearing option, and each build's .tmp directory (place-and-route intermediates, ~100 MB)
# is not needed once its bitstream has been copied out (the .bit/.v cache that the diffing reads is
# kept).
import resource, shutil
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
_build_design = FuzzConfig.build_design
def _build_design_and_clean(self, des_template, substitutions, prefix="", substitute=True):
    bit = _build_design(self, des_template, substitutions, prefix, substitute)
    shutil.rmtree(os.path.join(self.workdir, prefix + "design.tmp"), ignore_errors=True)
    return bit
FuzzConfig.build_design = _build_design_and_clean


# One A/B pad pair per LFCPNX SYSIO tile type with pads, plus extra B3/B4/B5 _0 instances whose
# _1 partner is each _1 variant (V18, DQS0, ECLK_R, MID); HP-bank IO logic also keeps bits in the
# _1 partner tile, as on LIFCL. Generated from the tile grid and the LFG672 pinout.
SITES = [
    [
    "IOL_T146A",
    [
    "CIB_R0C146:SYSIO_B0_0_EVEN"
    ]
    ],
    [
    "IOL_T146B",
    [
    "CIB_R0C146:SYSIO_B0_0_EVEN"
    ]
    ],
    [
    "IOL_T148A",
    [
    "CIB_R0C148:SYSIO_B0_0_ODD"
    ]
    ],
    [
    "IOL_T148B",
    [
    "CIB_R0C148:SYSIO_B0_0_ODD"
    ]
    ],
    [
    "IOL_R19A",
    [
    "CIB_R19C159:SYSIO_B1_0_C"
    ]
    ],
    [
    "IOL_R19B",
    [
    "CIB_R19C159:SYSIO_B1_0_C"
    ]
    ],
    [
    "IOL_R24A",
    [
    "CIB_R24C159:SYSIO_B1_0_EVEN"
    ]
    ],
    [
    "IOL_R24B",
    [
    "CIB_R24C159:SYSIO_B1_0_EVEN"
    ]
    ],
    [
    "IOL_R29A",
    [
    "CIB_R29C159:SYSIO_B1_0_ODD"
    ]
    ],
    [
    "IOL_R29B",
    [
    "CIB_R29C159:SYSIO_B1_0_ODD"
    ]
    ],
    [
    "IOL_R55A",
    [
    "CIB_R55C159:SYSIO_B2_0_C"
    ]
    ],
    [
    "IOL_R55B",
    [
    "CIB_R55C159:SYSIO_B2_0_C"
    ]
    ],
    [
    "IOL_R51A",
    [
    "CIB_R51C159:SYSIO_B2_0_EVEN"
    ]
    ],
    [
    "IOL_R51B",
    [
    "CIB_R51C159:SYSIO_B2_0_EVEN"
    ]
    ],
    [
    "IOL_R56A",
    [
    "CIB_R56C159:SYSIO_B2_0_ODD"
    ]
    ],
    [
    "IOL_R56B",
    [
    "CIB_R56C159:SYSIO_B2_0_ODD"
    ]
    ],
    [
    "IOL_B134A",
    [
    "CIB_R74C134:SYSIO_B3_0",
    "CIB_R74C135:SYSIO_B3_1"
    ]
    ],
    [
    "IOL_B134B",
    [
    "CIB_R74C134:SYSIO_B3_0",
    "CIB_R74C135:SYSIO_B3_1"
    ]
    ],
    [
    "IOL_B138A",
    [
    "CIB_R74C138:SYSIO_B3_0_DQS1",
    "CIB_R74C139:SYSIO_B3_1_DQS2"
    ]
    ],
    [
    "IOL_B138B",
    [
    "CIB_R74C138:SYSIO_B3_0_DQS1",
    "CIB_R74C139:SYSIO_B3_1_DQS2"
    ]
    ],
    [
    "IOL_B140A",
    [
    "CIB_R74C140:SYSIO_B3_0_DQS3",
    "CIB_R74C141:SYSIO_B3_1_DQS4"
    ]
    ],
    [
    "IOL_B140B",
    [
    "CIB_R74C140:SYSIO_B3_0_DQS3",
    "CIB_R74C141:SYSIO_B3_1_DQS4"
    ]
    ],
    [
    "IOL_B80A",
    [
    "CIB_R74C80:SYSIO_B4_0",
    "CIB_R74C81:SYSIO_B4_1"
    ]
    ],
    [
    "IOL_B80B",
    [
    "CIB_R74C80:SYSIO_B4_0",
    "CIB_R74C81:SYSIO_B4_1"
    ]
    ],
    [
    "IOL_B54A",
    [
    "CIB_R74C54:SYSIO_B4_0_DQS1",
    "CIB_R74C55:SYSIO_B4_1_DQS2"
    ]
    ],
    [
    "IOL_B54B",
    [
    "CIB_R74C54:SYSIO_B4_0_DQS1",
    "CIB_R74C55:SYSIO_B4_1_DQS2"
    ]
    ],
    [
    "IOL_B64A",
    [
    "CIB_R74C64:SYSIO_B4_0_DQS1_MID",
    "CIB_R74C65:SYSIO_B4_1_DQS2_MID"
    ]
    ],
    [
    "IOL_B64B",
    [
    "CIB_R74C64:SYSIO_B4_0_DQS1_MID",
    "CIB_R74C65:SYSIO_B4_1_DQS2_MID"
    ]
    ],
    [
    "IOL_B56A",
    [
    "CIB_R74C56:SYSIO_B4_0_DQS3",
    "CIB_R74C57:SYSIO_B4_1_DQS4"
    ]
    ],
    [
    "IOL_B56B",
    [
    "CIB_R74C56:SYSIO_B4_0_DQS3",
    "CIB_R74C57:SYSIO_B4_1_DQS4"
    ]
    ],
    [
    "IOL_B66A",
    [
    "CIB_R74C66:SYSIO_B4_0_DQS3_MID",
    "CIB_R74C67:SYSIO_B4_1_DQS4_MID"
    ]
    ],
    [
    "IOL_B66B",
    [
    "CIB_R74C66:SYSIO_B4_0_DQS3_MID",
    "CIB_R74C67:SYSIO_B4_1_DQS4_MID"
    ]
    ],
    [
    "IOL_B36A",
    [
    "CIB_R74C36:SYSIO_B5_0",
    "CIB_R74C37:SYSIO_B5_1"
    ]
    ],
    [
    "IOL_B36B",
    [
    "CIB_R74C36:SYSIO_B5_0",
    "CIB_R74C37:SYSIO_B5_1"
    ]
    ],
    [
    "IOL_B42A",
    [
    "CIB_R74C42:SYSIO_B5_0_DQS1",
    "CIB_R74C43:SYSIO_B5_1_DQS2"
    ]
    ],
    [
    "IOL_B42B",
    [
    "CIB_R74C42:SYSIO_B5_0_DQS1",
    "CIB_R74C43:SYSIO_B5_1_DQS2"
    ]
    ],
    [
    "IOL_B44A",
    [
    "CIB_R74C44:SYSIO_B5_0_DQS3",
    "CIB_R74C45:SYSIO_B5_1_DQS4"
    ]
    ],
    [
    "IOL_B44B",
    [
    "CIB_R74C44:SYSIO_B5_0_DQS3",
    "CIB_R74C45:SYSIO_B5_1_DQS4"
    ]
    ],
    [
    "IOL_L55A",
    [
    "CIB_R55C0:SYSIO_B6_0_C"
    ]
    ],
    [
    "IOL_L55B",
    [
    "CIB_R55C0:SYSIO_B6_0_C"
    ]
    ],
    [
    "IOL_L51A",
    [
    "CIB_R51C0:SYSIO_B6_0_EVEN"
    ]
    ],
    [
    "IOL_L51B",
    [
    "CIB_R51C0:SYSIO_B6_0_EVEN"
    ]
    ],
    [
    "IOL_L56A",
    [
    "CIB_R56C0:SYSIO_B6_0_ODD"
    ]
    ],
    [
    "IOL_L56B",
    [
    "CIB_R56C0:SYSIO_B6_0_ODD"
    ]
    ],
    [
    "IOL_L19A",
    [
    "CIB_R19C0:SYSIO_B7_0_C"
    ]
    ],
    [
    "IOL_L19B",
    [
    "CIB_R19C0:SYSIO_B7_0_C"
    ]
    ],
    [
    "IOL_L3A",
    [
    "CIB_R3C0:SYSIO_B7_0_EVEN"
    ]
    ],
    [
    "IOL_L3B",
    [
    "CIB_R3C0:SYSIO_B7_0_EVEN"
    ]
    ],
    [
    "IOL_L29A",
    [
    "CIB_R29C0:SYSIO_B7_0_ODD"
    ]
    ],
    [
    "IOL_L29B",
    [
    "CIB_R29C0:SYSIO_B7_0_ODD"
    ]
    ],
    [
    "IOL_B112A",
    [
    "CIB_R74C112:SYSIO_B3_0",
    "CIB_R74C113:SYSIO_B3_1_DQS0"
    ]
    ],
    [
    "IOL_B112B",
    [
    "CIB_R74C112:SYSIO_B3_0",
    "CIB_R74C113:SYSIO_B3_1_DQS0"
    ]
    ],
    [
    "IOL_B144A",
    [
    "CIB_R74C144:SYSIO_B3_0",
    "CIB_R74C145:SYSIO_B3_1_ECLK_R"
    ]
    ],
    [
    "IOL_B144B",
    [
    "CIB_R74C144:SYSIO_B3_0",
    "CIB_R74C145:SYSIO_B3_1_ECLK_R"
    ]
    ],
    [
    "IOL_B110A",
    [
    "CIB_R74C110:SYSIO_B3_0",
    "CIB_R74C111:SYSIO_B3_1_V18"
    ]
    ],
    [
    "IOL_B110B",
    [
    "CIB_R74C110:SYSIO_B3_0",
    "CIB_R74C111:SYSIO_B3_1_V18"
    ]
    ],
    [
    "IOL_B156A",
    [
    "CIB_R74C156:SYSIO_B3_0",
    "CIB_R74C157:SYSIO_B3_1_V18_32"
    ]
    ],
    [
    "IOL_B156B",
    [
    "CIB_R74C156:SYSIO_B3_0",
    "CIB_R74C157:SYSIO_B3_1_V18_32"
    ]
    ],
    [
    "IOL_B52A",
    [
    "CIB_R74C52:SYSIO_B4_0",
    "CIB_R74C53:SYSIO_B4_1_DQS0"
    ]
    ],
    [
    "IOL_B52B",
    [
    "CIB_R74C52:SYSIO_B4_0",
    "CIB_R74C53:SYSIO_B4_1_DQS0"
    ]
    ],
    [
    "IOL_B62A",
    [
    "CIB_R74C62:SYSIO_B4_0",
    "CIB_R74C63:SYSIO_B4_1_DQS0_MID"
    ]
    ],
    [
    "IOL_B62B",
    [
    "CIB_R74C62:SYSIO_B4_0",
    "CIB_R74C63:SYSIO_B4_1_DQS0_MID"
    ]
    ],
    [
    "IOL_B50A",
    [
    "CIB_R74C50:SYSIO_B4_0",
    "CIB_R74C51:SYSIO_B4_1_V18"
    ]
    ],
    [
    "IOL_B50B",
    [
    "CIB_R74C50:SYSIO_B4_0",
    "CIB_R74C51:SYSIO_B4_1_V18"
    ]
    ],
    [
    "IOL_B108A",
    [
    "CIB_R74C108:SYSIO_B4_0",
    "CIB_R74C109:SYSIO_B4_1_V18_42"
    ]
    ],
    [
    "IOL_B108B",
    [
    "CIB_R74C108:SYSIO_B4_0",
    "CIB_R74C109:SYSIO_B4_1_V18_42"
    ]
    ],
    [
    "IOL_B4A",
    [
    "CIB_R74C4:SYSIO_B5_0",
    "CIB_R74C5:SYSIO_B5_1_DQS0"
    ]
    ],
    [
    "IOL_B4B",
    [
    "CIB_R74C4:SYSIO_B5_0",
    "CIB_R74C5:SYSIO_B5_1_DQS0"
    ]
    ],
    [
    "IOL_B48A",
    [
    "CIB_R74C48:SYSIO_B5_0",
    "CIB_R74C49:SYSIO_B5_1_V18"
    ]
    ],
    [
    "IOL_B48B",
    [
    "CIB_R74C48:SYSIO_B5_0",
    "CIB_R74C49:SYSIO_B5_1_V18"
    ]
    ],
    [
    "IOL_B2A",
    [
    "CIB_R74C2:SYSIO_B5_0",
    "CIB_R74C3:SYSIO_B5_1_V18_51"
    ]
    ],
    [
    "IOL_B2B",
    [
    "CIB_R74C2:SYSIO_B5_0",
    "CIB_R74C3:SYSIO_B5_1_V18_51"
    ]
    ],
    [
    "IOL_R3B",
    [
    "CIB_R3C159:SYSIO_B1_DED"
    ]
    ]
    ]


def make_configs():
    out = []
    for site, tiles in SITES:
        prim = "IOLOGIC" if site[4] == "B" else "SIOLOGIC"
        out.append((site, prim + site[-1], FuzzConfig(job=site, device="LFCPNX-100", sv="../shared/empty_100.v",
                                                      tiles=tiles)))
    return out


configs = make_configs()

def main():
    def per_config(x):
        site, prim, cfg = x
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})

        cfg.sv = "iologic_100.v"

        s = (prim[0] == "S")

        side = site[4]
        pos = int(site[5:-1])
        ab = site[-1]

        rc = {"L": "R{}C0", "R": "R{}C159", "B": "R74C{}", "T": "R0C{}"}[side].format(pos)

        def get_substs(mode="NONE", default_cfg=False, scope=None, kv=None, mux=False, glb=False, dqs=False, pinconn=""):
            if default_cfg:
                # Radiant 2026.1: SRMODE takes a plain value (SRMODE:#ASYNC is a syntax error), and
                # SIOLOGIC_CORE has no LOAD_NMUX, DIRMUX or MOVEMUX
                config = "SCLKINMUX:#OFF GSR:ENABLED INMUX:#OFF OUTMUX:#OFF DELAYMUX:#OFF SRMODE:ASYNC " + \
                    ("" if s else "LOAD_NMUX:#OFF DIRMUX:#OFF MOVEMUX:#OFF ") + \
                    "CEOUTMUX:#OFF CEINMUX:#OFF LSRINMUX:#OFF LSROUTMUX:#OFF STOP_EN:DISABLED"
            elif kv is None:
                config = ""
            elif glb:
                config="{}:{}".format(kv[0], kv[1])
            elif dqs and "_" in kv[1]:
                val, dqsmode = kv[1].split("_")
                config = "{}:::{}={} WRCLKMUX:{}".format(mode if scope is None else scope, kv[0], val, dqsmode)
            elif mux:
                signame = kv[0].replace("MUX", "")
                val = "{}:::{}=#SIG".format(signame, signame)
                if kv[1] in ("0", "1"):
                    val = "CONST:::CONST={}".format(kv[1])
                if kv[1] == "INV":
                    val = "{}:::{}=#INV".format(signame, signame)
                config = "{}:{}".format(kv[0], val)
            else:
                config = "{}:::{}={}".format(mode if scope is None else scope, kv[0], kv[1])
            if pinconn != "":
                # Add routing so that pin is 'used'
                if "TOUT" in pinconn:
                    if side in ("L", "R", "T"):
                        first_wire = "{}_JTOUT_SIOLOGIC_CORE_IBASE_PIC_{}".format(rc, ab)
                        second_wire = "{}_JPADDT_SEIO33_CORE_IO{}".format(rc, ab)
                    else:
                        first_wire = "{}_JTOUT_IOLOGIC_CORE_I_GEARING_PIC_TOP_{}".format(rc, ab)
                        if ab == "A":
                            second_wire = "{}_JPADDT_DIFFIO18A_CORE_IO{}".format(rc, ab)
                        else:
                            second_wire = "{}_JPADDT_SEIO18A_CORE_IO{}".format(rc, ab)
                else:
                    if side in ("L", "R", "T"):
                        first_wire = "{}_JDOUT_SIOLOGIC_CORE_IBASE_PIC_{}".format(rc, ab)
                        second_wire = "{}_JPADDO_SEIO33_CORE_IO{}".format(rc, ab)
                    else:
                        first_wire = "{}_JDOUT_IOLOGIC_CORE_I_GEARING_PIC_TOP_{}".format(rc, ab)
                        if ab == "A":
                            second_wire = "{}_JPADDO_DIFFIO18A_CORE_IO{}".format(rc, ab)
                        else:
                            second_wire = "{}_JPADDO_SEIO18A_CORE_IO{}".format(rc, ab)
                route = '(* \\xref:LOG ="q_c@0@9", \\dm:arcs ="{}.{}" *) '.format(second_wire, first_wire)
                sig = route + "wire sig;"
            else:
                sig = ""
            return dict(mode=mode, cmt="//" if mode == "NONE" else "", config=config, site=site, s="S" if s else "", pinconn=pinconn, sig=sig)
        modes = ["NONE", "IREG_OREG", "IDDRX1_ODDRX1"]
        if not s:
            modes += ["IDDRXN", "ODDRXN", "MIDDRXN_MODDRXN"]
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.MODE".format(prim), modes,
            lambda x: get_substs(x, default_cfg=True), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.GSR".format(prim), ["ENABLED", "DISABLED"],
            lambda x: get_substs(mode="IREG_OREG", kv=("GSR", x), glb=True), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.SRMODE".format(prim), ["ASYNC", "LSR_OVER_CE"],
            lambda x: get_substs(mode="IREG_OREG", kv=("SRMODE", x), glb=True), False)
        if not s:
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.IDDRXN.DDRMODE".format(prim), ["NONE", "IDDRX2", "IDDR71", "IDDRX4", "IDDRX5"],
                lambda x: get_substs(mode="IDDRXN", kv=("DDRMODE", "#OFF" if x == "NONE" else x)), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.ODDRXN.DDRMODE".format(prim), ["NONE", "ODDRX2", "ODDR71", "ODDRX4", "ODDRX5"],
                lambda x: get_substs(mode="ODDRXN", kv=("DDRMODE", "#OFF" if x == "NONE" else x)), False)

        for sig in ("SCLKIN", "SCLKOUT", "CEIN", "CEOUT", "LSRIN", "LSROUT"):
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}MUX".format(prim, sig), ["1" if sig[0:2] == "CE" else "0", sig, "INV"],
                lambda x: get_substs(mode="IREG_OREG", kv=("{}MUX".format(sig), x), mux=True), False)

        nonrouting.fuzz_enum_setting(cfg, empty, "{}.IDDRX1_ODDRX1.OUTPUT".format(prim), ["DISABLED", "ENABLED"],
            lambda x: get_substs(mode="IDDRX1_ODDRX1", default_cfg=True, pinconn=(".DOUT(sig), .LSRIN(sig)" if x == "ENABLED" else "")), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.IREG_OREG.OUTPUT".format(prim), ["DISABLED", "ENABLED"],
            lambda x: get_substs(mode="IREG_OREG", default_cfg=True, pinconn=(".DOUT(sig), .LSRIN(sig)" if x == "ENABLED" else "")), False)

        if not s:
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.IDDRX1_ODDRX1.TRISTATE".format(prim), ["DISABLED", "ENABLED"],
                lambda x: get_substs(mode="IDDRX1_ODDRX1", kv=("TOUTMUX", "TSREG"), glb=True, pinconn=(".TOUT(sig), .LSRIN(sig)" if x == "ENABLED" else "")), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.IREG_OREG.TRISTATE".format(prim), ["DISABLED", "ENABLED"],
                lambda x: get_substs(mode="IREG_OREG", kv=("TOUTMUX", "TSREG"), glb=True, pinconn=(".TOUT(sig), .LSRIN(sig)" if x == "ENABLED" else "")), False)
        else:
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.IDDRX1_ODDRX1.TRISTATE".format(prim), ["DISABLED", "ENABLED"],
                lambda x: get_substs(mode="IDDRX1_ODDRX1", default_cfg=True, pinconn=(".TOUT(sig), .LSRIN(sig)" if x == "ENABLED" else "")), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.IREG_OREG.TRISTATE".format(prim), ["DISABLED", "ENABLED"],
                lambda x: get_substs(mode="IREG_OREG", default_cfg=True, pinconn=(".TOUT(sig), .LSRIN(sig)" if x == "ENABLED" else "")), False)

        nonrouting.fuzz_enum_setting(cfg, empty, "{}.INMUX".format(prim), ["BYPASS", "DELAY"],
            lambda x: get_substs(mode="IREG_OREG", kv=("INMUX", x), glb=True), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.OUTMUX".format(prim), ["BYPASS", "DELAY"],
            lambda x: get_substs(mode="IREG_OREG", kv=("OUTMUX", x), glb=True), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.DELAYMUX".format(prim), ["OUT_REG", "IN"],
            lambda x: get_substs(mode="IREG_OREG", kv=("DELAYMUX", x), glb=True), False)

        if not s:
          nonrouting.fuzz_enum_setting(cfg, empty, "{}.MOVEMUX".format(prim), ["0", "MOVE"],
            lambda x: get_substs(mode="IREG_OREG", kv=("MOVEMUX", x), glb=True), False)
          nonrouting.fuzz_enum_setting(cfg, empty, "{}.DIRMUX".format(prim), ["0", "DIR"],
            lambda x: get_substs(mode="IREG_OREG", kv=("DIRMUX", x), glb=True), False)
          nonrouting.fuzz_enum_setting(cfg, empty, "{}.LOAD_NMUX".format(prim), ["1", "LOAD_N"],
            lambda x: get_substs(mode="IREG_OREG", kv=("LOAD_NMUX", x), glb=True), False)

        nonrouting.fuzz_enum_setting(cfg, empty, "{}.INREG.REGSET".format(prim), ["SET", "RESET"],
            lambda x: get_substs(mode="IREG_OREG", kv=("REGSET", x), scope="INREG"), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.OUTREG.REGSET".format(prim), ["SET", "RESET"],
            lambda x: get_substs(mode="IREG_OREG", kv=("REGSET", x), scope="OUTREG"), False)
        nonrouting.fuzz_enum_setting(cfg, empty, "{}.TSREG.REGSET".format(prim), ["SET", "RESET"],
            lambda x: get_substs(mode="IREG_OREG", kv=("REGSET", x), scope="TSREG"), False)
        if not s:
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.MIDDRXN.DDRMODE".format(prim), ["NONE", "MIDDRX2", "MIDDRX4"],
                lambda x: get_substs(mode="MIDDRXN_MODDRXN", kv=("DDRMODE", "#OFF" if x == "NONE" else x), scope="MIDDRXN"), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.MODDRXN.DDRMODE".format(prim), ["NONE", "MOSHX2", "MOSHX4", "MODDRX2_DQSW", "MODDRX4_DQSW", "MODDRX2_DQSW270", "MODDRX4_DQSW270"],
                lambda x: get_substs(mode="MIDDRXN_MODDRXN", kv=("DDRMODE", "#OFF" if x == "NONE" else x), scope="MODDRXN", dqs=True, pinconn=(".DOUT(sig), .LSRIN(sig)" if x != "#OFF" else "")), False)
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.MTDDRXN.DDRMODE".format(prim), ["NONE", "MTSHX2", "MTSHX4"],
                lambda x: get_substs(mode="MIDDRXN_MODDRXN", kv=("DDRMODE", "#OFF" if x == "NONE" else x + " TOUTMUX:MTDDR"), scope="MTDDRXN"), False)
    import sys
    sel = [c for c in configs if not sys.argv[1:] or c[0] in sys.argv[1:]]
    fuzzloops.parallel_foreach(sel, per_config)

if __name__ == "__main__":
    main()
