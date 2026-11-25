# LFCPNX: setup / hold of the DQSBUF fabric inputs against SCLK. The bank-3 byte-lane PHY of
# fuzzers/LFCPNX/156-dqsw-iologic (phy1: DQSBUF at the AF4 DQS group, ECLKSYNC / ECLKDIV / DDRDLL,
# every DQSBUF input from its own SCLK register), through the timing flow.
# Run 1: DQSBUF. Run 2: DQSBUF_IVREF (LVSTL IO types, IVREFI tied to 49, LPDDR4_BL16_EN enabled).
#
# Usage: gen_dqsbuf_pins.py <basename>   (run number N in work/design_N picks the variant)
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(here, "..", "..", "..", "..", "fuzzers", "LFCPNX", "156-dqsw-iologic")
base = sys.argv[1]
n = int(re.search(r'(\d+)$', base).group(1))
v = open(os.path.join(src, "phy1.v")).read().replace("module phy1(", "module top(")
p = open(os.path.join(src, "phy1.pdc")).read()
if n == 2:
    v = v.replace('DQSBUF #(.GSR("DISABLED"),', 'DQSBUF_IVREF #(.GSR("DISABLED"), .LPDDR4_BL16_EN("ENABLED"),')
    v = v.replace(".DLLCODE(code),", ".DLLCODE(code), .IVREFI(7'd49),")
    p = p.replace("IO_TYPE=HSUL12D} [get_ports dqs]", "IO_TYPE=LVSTLD_I} [get_ports dqs]")
    p = p.replace("IO_TYPE=HSUL12} [get_ports {dq[0]}]", "IO_TYPE=LVSTL_I} [get_ports {dq[0]}]")
    p = re.sub(r"IO_TYPE=HSUL12\}", "IO_TYPE=LVSTL_I}", p).replace("IO_TYPE=HSUL12D}", "IO_TYPE=LVSTLD_I}").replace("IO_TYPE=LVDS}", "IO_TYPE=LVSTLD_I}")
open(base + ".v", "w").write(v)
open(base + ".pdc", "w").write(p)
