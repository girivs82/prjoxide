# value discovery for LVSTL_I and HP-ref slew; one build per value, Radiant's errors captured
import os, re, string, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from fuzzconfig import FuzzConfig
import database
cfg = FuzzConfig(job="PROBE2", device="LFCPNX-100", sv="../shared/empty_100.v",
                 tiles=['CIB_R74C156:SYSIO_B3_0', 'CIB_R74C157:SYSIO_B3_1_V18_32'])
cfg.setup(); cfg.sv = "iob_100.v"
def s(site, iotype, vcc, extra="", d="input", prim="SEIO18A_CORE"):
    pintype, t = {"input": ("input", "1"), "output": ("output", "0"), "inout": ("inout", "#SIG")}[d]
    return dict(cmt="", pintype=pintype, primtype=prim, site=site, iotype=iotype, t=t, extra_config=extra, vcc=vcc,
                arcs_attr="", device=cfg.device)
runs = {}
for site in ("AE3", "AD3"):
    for v in ["2","4","6","8","10","12","16","34","40","48","60","80"]:
        runs[f"{site}_drv{v}"] = s(site, "LVSTL_I", "1.1", f",DRIVE={v}", "output")
    for v in ["30","34","40","48","50","60","75","80","120","150","240"]:
        runs[f"{site}_term{v}"] = s(site, "LVSTL_I", "1.1", f",TERMINATION={v}")
    for std, vcc in (("HSUL12","1.2"), ("SSTL15_I","1.5"), ("LVSTL_I","1.1"), ("LVCMOS12H","1.2")):
        for sr in ("SLOW","MED","FAST"):
            runs[f"{site}_slew_{std}_{sr}"] = s(site, std, vcc, f",SLEWRATE={sr}", "output")
    runs[f"{site}_lvstl_vref2"] = s(site, "LVSTL_I", "1.1", ",VREF=VREF2_LOAD")
    runs[f"{site}_out_hsul12"] = s(site, "HSUL12", "1.2", "", "output")
    runs[f"{site}_out_sstl15i"] = s(site, "SSTL15_I", "1.5", "", "output")
    runs[f"{site}_out_lvstl"] = s(site, "LVSTL_I", "1.1", "", "output")
    runs[f"{site}_in_lvstl"] = s(site, "LVSTL_I", "1.1", "", "input")
    runs[f"{site}_bidir_lvstl"] = s(site, "LVSTL_I", "1.1", "", "inout")
for std in ("LVSTLD_I", "LVSTL_II", "LVSTLD_II"):
    prim = "DIFFIO18A_CORE" if "D_" in std else "SEIO18A_CORE"
    for d in ("input", "output"):
        runs[f"AD3_{std}_{d}"] = s("AD3", std, "1.1", "", d, prim)
def build(item):
    n, sub = item
    desfile = os.path.join(cfg.workdir, n + "_design.v"); bit = os.path.join(cfg.workdir, n + "_design.bit")
    if os.path.exists(bit):
        return n, "BUILT", ""
    with open(cfg.sv) as inf, open(desfile, "w") as ouf:
        ouf.write(string.Template(inf.read()).substitute(**sub))
    env = os.environ.copy(); env["STRUCT_VER"] = "1"; env["RBK_MODE"] = "1"
    r = subprocess.run(["bash", os.path.join(database.get_oxide_root(), "radiant.sh"), cfg.device, desfile],
                       env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    subprocess.run(["rm", "-rf", os.path.join(cfg.workdir, n + "_design.tmp")])
    errs = [l for l in r.stdout.splitlines() if re.match(r"ERROR <\d+>", l)]
    return n, ("BUILT" if os.path.exists(bit) else "FAIL"), (errs[0][:220] if errs else "")
with ThreadPoolExecutor(3) as ex:
    for n, st, e in ex.map(build, sorted(runs.items())):
        print(st, n, e, flush=True)
