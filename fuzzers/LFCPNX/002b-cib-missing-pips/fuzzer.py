"""
Fuzz the CIB pips that LIFCL's database has and LFCPNX's lacks, without lapie.

Candidates are regenerated from the two databases: for each CIB tile type, every
(from, to) pip in LIFCL/tiletypes/<type>.ron that is missing from
LFCPNX/tiletypes/<type>.ron, translated to Lattice absolute wire names at one
representative LFCPNX instance (prjoxide's own normalize_wire is the oracle).
Each arc is then forced in a separate design with util/fuzz/interconnect.py's
fuzz_pip_list; arcs Radiant rejects are reported as ABSENT.

CIBMUXIN -> CIBMUXOUT pips are fuzzed as LIFCL's 050-cib-special does: full-mux
style, with the other CIBMUXOUT letters tied to CIBMUXIN A so Radiant does not
tie unused outputs itself. Other pips use the plain routing template.

Usage: python3 fuzzer.py [tile type ...]   (default: CIB CIB_T CIB_LR CIB_LR_A)
"""
import re
import sys
from os import path

import database
import libpyprjoxide
from fuzzconfig import FuzzConfig
from interconnect import fuzz_pip_list
from pip_candidates import tile_pips, denormalize, conns_to_zero_bit_pips

# tile type -> (row, col, extra fuzz tiles, ignore tiles)
INSTANCES = {
    "CIB": (28, 17, [], {"TAP_CIB_R28C14:TAP_CIB"}),
    "CIB_T": (1, 18, [], {"TAP_CIBT_R1C14:TAP_CIBT"}),
    "CIB_LR": (18, 1, [], {"TAP_PLC_R18C14:TAP_PLC"}),
    "CIB_LR_A": (28, 1, ["CIB_R29C1:CIB_LR_B"], {"TAP_CIB_R28C14:TAP_CIB"}),
}


def main():
    types = sys.argv[1:] or ["CIB", "CIB_T", "CIB_LR", "CIB_LR_A"]
    chip = libpyprjoxide.Chip(libpyprjoxide.Database(database.get_db_root()), "LFCPNX-100")
    for tt in types:
        r, c, extra_tiles, ignore = INSTANCES[tt]
        tile = "CIB_R{}C{}:{}".format(r, c, tt)
        missing = sorted(tile_pips("LIFCL", tt) - tile_pips("LFCPNX", tt))
        cibmux, other = {}, []
        for frm, to in missing:
            af, at = denormalize(chip, tile, r, c, frm), denormalize(chip, tile, r, c, to)
            if len(af) != 1 or len(at) != 1:
                print("UNMAPPED {} {} -> {}: {} -> {}".format(tt, frm, to, af, at), flush=True)
                continue
            m = re.match(r'^JCIBMUXOUT([ABCD])\d$', to)
            if m:
                cibmux.setdefault(m.group(1), []).append((af[0], at[0]))
            else:
                other.append((af[0], at[0]))
        print("{}: {} candidates ({} CIBMUX, {} other)".format(
            tt, len(missing), sum(len(v) for v in cibmux.values()), len(other)), flush=True)

        if other:
            cfg = FuzzConfig(job="{}_OTHER".format(tt), device="LFCPNX-100", sv="../shared/route_100.v",
                             tiles=[tile] + extra_tiles)
            cfg.setup(skip_specimen=True)
            fuzz_pip_list(cfg, other, ignore_tiles=ignore)

        for x in sorted(cibmux):
            # Tie every other letter's outputs to CIBMUXIN A (as LIFCL's 050-cib-special).
            extra_arcs = ["R{r}C{c}_JCIBMUXOUT{x}{i}.R{r}C{c}_JCIBMUXINA{i}".format(r=r, c=c, x=x2, i=i)
                          for i in range(8) for x2 in "ABCD" if x2 != x]
            cfg = FuzzConfig(job="{}_CIBMUX{}".format(tt, x), device="LFCPNX-100", sv="cib_iomux_100.v",
                             tiles=[tile] + extra_tiles)
            cfg.setup(skip_specimen=True)
            fuzz_pip_list(cfg, cibmux[x], full_mux_style=True, ignore_tiles=ignore,
                          extra_substs=dict(extra_arc=" ".join(extra_arcs)))

    for tt in types:
        conns_to_zero_bit_pips(tt)



if __name__ == "__main__":
    main()
