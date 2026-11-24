"""
PLL_LLC's dedicated CLKOP feedback mux, ECLKLOGICMUXPLLFB_CORE_ECLKPLLFBL (LFCPNX-100).

The two bottom PLLs can take their feedback from a PLL output through a mux in the bottom-middle
clock tiles into FBKMUX input JFBKCLK10: ECLKPLLFBR (at R73C75) for PLL_LRC, already fuzzed by
002c from LIFCL's BMID_1_ECLK_2 arcs, and ECLKPLLFBL for PLL_LLC, which LIFCL-40 has no arcs for.
Radiant uses it when FBKCK = CLKOP and CLKOP drives an edge clock (157-dqsbuf-ivref named its
bits as BMID.LLC_PLL_FBK before the mux was known).

ECLKPLLFBL sits at R73C71: forcing one of its arcs with sv2udb at each R/C of R70-74 C66-79 was
accepted only there (the same scan accepted R73C75 for ECLKPLLFBR). Each of its 12 inputs (the
CLKOP / CLKOS..CLKOS5 of PLL_LLC and PLL_LRC) is forced in a separate design.

The two top PLLs have no such input (their FBKMUX has no JFBKCLK10), and par refuses an edge
clock from them: "PLL driving ECLK must be placed at the bottom".
"""
import fuzzconfig
from fuzzconfig import FuzzConfig
from interconnect import fuzz_pip_list

R, C = 73, 71
OUTS = ["CLKOP", "CLKOS", "CLKOS2", "CLKOS3", "CLKOS4", "CLKOS5"]
GROUP = ["CIB_R74C73:BMID_0_ECLK_1", "CIB_R74C72:ECLK_0", "CIB_R74C74:BMID_1_ECLK_2", "CIB_R74C75:ECLK_3"]


def main():
    to = "R{}C{}_JECLKOUT_ECLKLOGICMUXPLLFB_CORE_ECLKPLLFBL".format(R, C)
    pips = [("R{}C{}_J{}{}_ECLKLOGICMUXPLLFB_CORE_ECLKPLLFBL".format(R, C, pll, o), to)
            for pll in ("LL", "LR") for o in OUTS]
    cfg = FuzzConfig(job="ECLKPLLFBL", device="LFCPNX-100", sv="../shared/route_100.v", tiles=GROUP)
    cfg.setup(skip_specimen=True)
    fuzz_pip_list(cfg, pips)


if __name__ == "__main__":
    main()
