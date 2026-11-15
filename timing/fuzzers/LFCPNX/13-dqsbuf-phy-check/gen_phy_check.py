# LFCPNX: the bank-3 byte-lane PHY of fuzzers/LFCPNX/156-dqsw-iologic (phy1 and its lane-moved
# variants) through the timing flow, to check the DQSBUFA input connections in the database against
# routes Radiant made for a different design (tools/radiant-fuzz/infer_dqsbuf_conns.py --check).
#
# Usage: gen_phy_check.py <basename>   (run number N in work/design_N picks the variant)
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "..", "..", "..", "fuzzers", "LFCPNX", "156-dqsw-iologic"))
import gen_variants as G

VARIANTS = {1: "phy1", 2: "v_chb_hi", 3: "v_cha_hi", 4: "g_notsh", 5: "v_dm_af3"}
base = sys.argv[1]
n = int(re.search(r'(\d+)$', base).group(1))
v, p = G.variants[VARIANTS[n]]
open(base + ".v", "w").write(v.replace("module phy1(", "module top("))
open(base + ".pdc", "w").write(p)
