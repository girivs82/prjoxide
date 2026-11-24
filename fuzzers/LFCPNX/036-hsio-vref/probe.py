# probe: structural IO builds on PB156B (AE3, tiles C156/C157), to see which settings carry the
# input-class / VREF bits and what LVSTL_I sets
import os, sys
from fuzzconfig import FuzzConfig
import database
cfg = FuzzConfig(job="PROBE", device="LFCPNX-100", sv="../shared/empty_100.v",
                 tiles=['CIB_R74C156:SYSIO_B3_0', 'CIB_R74C157:SYSIO_B3_1_V18_32'])
cfg.setup()
empty = cfg.build_design(cfg.sv, {})
cfg.sv = "iob_100.v"
def s(iotype, vcc, extra="", pintype="input", t="1", prim="SEIO18A_CORE"):
    return dict(cmt="", pintype=pintype, primtype=prim, site="AE3", iotype=iotype, t=t, extra_config=extra, vcc=vcc)
runs = {
  "in_hsul12": s("HSUL12", "1.2"), "in_hsul12_vref": s("HSUL12", "1.2", ",VREF=VREF1_LOAD"),
  "in_sstl15i_vref": s("SSTL15_I", "1.5", ",VREF=VREF1_LOAD"), "in_lvcmos12h": s("LVCMOS12H", "1.2"),
  "in_lvstl": s("LVSTL_I", "1.1"), "in_lvstl_vref": s("LVSTL_I", "1.1", ",VREF=VREF1_LOAD"),
  "out_lvstl": s("LVSTL_I", "1.1", pintype="output", t="0"), "bidir_lvstl": s("LVSTL_I", "1.1", pintype="inout", t="#SIG"),
  "in_lvstl_t40": s("LVSTL_I", "1.1", ",TERMINATION=40"), "in_lvstl_t60": s("LVSTL_I", "1.1", ",TERMINATION=60"),
}
for n, sub in runs.items():
    try:
        b = cfg.build_design(cfg.sv, sub, n + "_")
        print("BUILT", n, b, flush=True)
    except Exception as e:
        print("FAIL", n, e, flush=True)
print("EMPTY", empty)
