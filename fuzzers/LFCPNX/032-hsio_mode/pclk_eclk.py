"""
PIOA.PCLK_ECLK on the HP-bank PCLK input pins: the pad-tile bit that Radiant 2026.1 sets when a
PCLKT pin drives an edge clock (through the bank's ECLKBANK mux to an ECLKSYNC), and not when the
same pin is an ordinary input. LIFCL has no such bit.

Each pair of designs has an IDDRX2 on a data pad of the bank, clocked through ECLKSYNC + ECLKDIV
from one PCLK pin, and another PCLK pin used as a plain input; ON drives the edge clock from the
fuzzed pin and OFF from the other one, so the fuzzed pad is an LVCMOS18H input in both.

Usage: pclk_eclk.py [pad ...]
"""
import os
import sys

from fuzzconfig import FuzzConfig
import fuzzloops
import nonrouting

# PCLK pad: (ball, tile, other PCLK ball of the bank, data pad ball of the bank)
PCLK = {
    "PB4A": ("V23", "CIB_R74C4:SYSIO_B5_0", "W24", "AC25"),
    "PB10A": ("W24", "CIB_R74C10:SYSIO_B5_0", "V23", "AC25"),
    "PB40A": ("AD25", "CIB_R74C40:SYSIO_B5_0", "W24", "AC25"),
    "PB46A": ("AC21", "CIB_R74C46:SYSIO_B5_0", "W24", "AC25"),
    "PB52A": ("AD21", "CIB_R74C52:SYSIO_B4_0", "AB19", "AF22"),
    "PB58A": ("AB19", "CIB_R74C58:SYSIO_B4_0", "AD21", "AF22"),
    "PB100A": ("AA13", "CIB_R74C100:SYSIO_B4_0", "AB19", "AF22"),
    "PB106A": ("AE13", "CIB_R74C106:SYSIO_B4_0", "AB19", "AF22"),
    "PB112A": ("AC12", "CIB_R74C112:SYSIO_B3_0", "AB11", "AA12"),
    "PB118A": ("AB11", "CIB_R74C118:SYSIO_B3_0", "AC12", "AA12"),
    "PB148A": ("Y5", "CIB_R74C148:SYSIO_B3_0", "AB11", "AA12"),
    "PB154A": ("AB4", "CIB_R74C154:SYSIO_B3_0", "AB11", "AA12"),
}


def main():
    sel = [p for p in PCLK if not sys.argv[1:] or p in sys.argv[1:]]

    def per_pad(pad):
        ball, tile, other, data = PCLK[pad]
        cfg = FuzzConfig(job="PCLK_" + pad, device="LFCPNX-100", sv="../shared/empty_100.v", tiles=[tile])
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.struct_mode = False
        cfg.sv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pclk_eclk.v")
        nonrouting.fuzz_enum_setting(cfg, empty, "PIOA.PCLK_ECLK", ["OFF", "ON"],
                                     lambda v: dict(d_ball=data, eclk_ball=ball if v == "ON" else other,
                                                    x_ball=other if v == "ON" else ball), False)

    fuzzloops.parallel_foreach(sel, per_pad)


if __name__ == "__main__":
    main()
