# value discovery for LVSTL_I and HP-ref slew; one build per value, Radiant's errors captured
import os, re, string, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from fuzzconfig import FuzzConfig
import database
cfg = FuzzConfig(job="PROBE7", device="LFCPNX-100", sv="../shared/empty_100.v",
                 tiles=['CIB_R74C156:SYSIO_B3_0', 'CIB_R74C157:SYSIO_B3_1_V18_32'])
cfg.setup(); cfg.sv = "iob_100.v"
def s(site, iotype, vcc, extra="", d="input", prim="SEIO18A_CORE"):
    pintype, t = {"input": ("input", "1"), "output": ("output", "0"), "inout": ("inout", "#SIG")}[d]
    return dict(cmt="", pintype=pintype, primtype=prim, site=site, iotype=iotype, t=t, extra_config=extra, vcc=vcc,
                arcs_attr="", device=cfg.device)
runs = {}
site = "AA6"
for v in ("BOGUS", "VREF_EXT", "VREF_INT_50", "50", "VCCIO_HALF"):
    runs["vref_" + v] = s(site, "LVSTL_I", "1.1", ",VREF=" + v)
for p in ("VREF_LEVEL=50", "VREFLEVEL=50", "VREF_VALUE=0.55", "VREF_INT_LEVEL=50", "BOGUSPROP=1"):
    runs["prop_" + p.split("=")[0]] = s(site, "LVSTL_I", "1.1", "," + p)
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
    return n, ("BUILT" if os.path.exists(bit) else "FAIL"), (" || ".join(e[:400] for e in errs[:2]) if errs else "")
with ThreadPoolExecutor(3) as ex:
    for n, st, e in ex.map(build, sorted(runs.items())):
        print(st, n, e, flush=True)
