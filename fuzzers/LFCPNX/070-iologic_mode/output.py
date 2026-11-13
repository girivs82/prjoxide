"""
IOLOGIC / SIOLOGIC IREG_OREG.OUTPUT and IDDRX1_ODDRX1.OUTPUT: whether the IO logic's output (the
output register, or the ODDRX1) drives the pad.

fuzzer.py's structural template routes DOUT to the pad for ENABLED (as LIFCL's 070 does), but on
LFCPNX with Radiant 2026.1 that design sets the same bits as DISABLED, so these settings came out
empty. Here each pair of designs is synthesized on a bidir pad whose IO logic has its input
register (IFD1P3DX, or IDDRX1) and a tristate register in both designs, so the output-side clock and
CE are in use either way; ENABLED adds the output register (OFD1P3DX, or ODDRX1) where DISABLED
drives the pad from the fabric. The two designs differ only in the output enable bit.

Usage: output.py [site ...]   (run after fuzzer.py, in the same environment)
"""
import os
import sys

import fuzzer  # noqa: F401  (SITES; installs the robust enum wrapper and the work-dir cleanup)
import fuzzloops
import nonrouting

# site: (ball, bank) on LFG672
BALLS = {
    "IOL_T146A": ("J1", 0),
    "IOL_T146B": ("J2", 0),
    "IOL_T148A": ("J3", 0),
    "IOL_T148B": ("J5", 0),
    "IOL_R19A": ("N2", 1),
    "IOL_R19B": ("N3", 1),
    "IOL_R24A": ("N9", 1),
    "IOL_R24B": ("N8", 1),
    "IOL_R29A": ("R6", 1),
    "IOL_R29B": ("R7", 1),
    "IOL_R55A": ("W7", 2),
    "IOL_R55B": ("W6", 2),
    "IOL_R51A": ("V3", 2),
    "IOL_R51B": ("V4", 2),
    "IOL_R56A": ("W5", 2),
    "IOL_R56B": ("W4", 2),
    "IOL_B134A": ("AC7", 3),
    "IOL_B134B": ("AB7", 3),
    "IOL_B138A": ("AF6", 3),
    "IOL_B138B": ("AF5", 3),
    "IOL_B140A": ("AD6", 3),
    "IOL_B140B": ("AE6", 3),
    "IOL_B80A": ("AC18", 4),
    "IOL_B80B": ("AD18", 4),
    "IOL_B54A": ("AF22", 4),
    "IOL_B54B": ("AF23", 4),
    "IOL_B64A": ("AF19", 4),
    "IOL_B64B": ("AE19", 4),
    "IOL_B56A": ("AD20", 4),
    "IOL_B56B": ("AC19", 4),
    "IOL_B66A": ("AF21", 4),
    "IOL_B66B": ("AF20", 4),
    "IOL_B36A": ("AC25", 5),
    "IOL_B36B": ("AD26", 5),
    "IOL_B42A": ("AE26", 5),
    "IOL_B42B": ("AF25", 5),
    "IOL_B44A": ("AE24", 5),
    "IOL_B44B": ("AF24", 5),
    "IOL_L55A": ("T24", 6),
    "IOL_L55B": ("T23", 6),
    "IOL_L51A": ("R25", 6),
    "IOL_L51B": ("R26", 6),
    "IOL_L56A": ("T21", 6),
    "IOL_L56B": ("T20", 6),
    "IOL_L19A": ("K24", 7),
    "IOL_L19B": ("K25", 7),
    "IOL_L3A": ("H20", 7),
    "IOL_L3B": ("H21", 7),
    "IOL_L29A": ("N25", 7),
    "IOL_L29B": ("N24", 7),
    "IOL_B112A": ("AC12", 3),
    "IOL_B112B": ("AD12", 3),
    "IOL_B144A": ("AD5", 3),
    "IOL_B144B": ("AE5", 3),
    "IOL_B110A": ("AA12", 3),
    "IOL_B110B": ("AB12", 3),
    "IOL_B156A": ("AD3", 3),
    "IOL_B156B": ("AE3", 3),
    "IOL_B52A": ("AD21", 4),
    "IOL_B52B": ("AE21", 4),
    "IOL_B62A": ("W17", 4),
    "IOL_B62B": ("W18", 4),
    "IOL_B50A": ("AE22", 4),
    "IOL_B50B": ("AE23", 4),
    "IOL_B108A": ("Y12", 4),
    "IOL_B108B": ("W12", 4),
    "IOL_B4A": ("V23", 5),
    "IOL_B4B": ("V22", 5),
    "IOL_B48A": ("AC20", 5),
    "IOL_B48B": ("AB20", 5),
    "IOL_B2A": ("V24", 5),
    "IOL_B2B": ("V25", 5),
    "IOL_R3B": ("L1", 1),
}
HP_BANKS = (3, 4, 5)
CLK_BALL = "W24"    # PCLKT5_1
AUX = ["AA2", "AA4", "V1", "AA1", "V2", "Y4"]   # bank 2: t, i, i2, o, o2 (one spare)

BODY = {
    ("IREG_OREG", "DISABLED"): "IFD1P3DX ir (.D(pi), .CK(clk), .SP(1'b1), .CD(1'b0), .Q(o));\n"
                               "    assign po = i;\n    assign o2 = i2;",
    ("IREG_OREG", "ENABLED"): "IFD1P3DX ir (.D(pi), .CK(clk), .SP(1'b1), .CD(1'b0), .Q(o));\n"
                              "    OFD1P3DX orr (.D(i), .CK(clk), .SP(1'b1), .CD(1'b0), .Q(po));\n    assign o2 = i2;",
    ("IDDRX1_ODDRX1", "DISABLED"): "IDDRX1 id (.D(pi), .SCLK(clk), .RST(1'b0), .Q0(o), .Q1(o2));\n"
                                   "    assign po = i ^ i2;",
    ("IDDRX1_ODDRX1", "ENABLED"): "IDDRX1 id (.D(pi), .SCLK(clk), .RST(1'b0), .Q0(o), .Q1(o2));\n"
                                  "    ODDRX1 od (.D0(i), .D1(i2), .SCLK(clk), .RST(1'b0), .Q(po));",
}


def main():
    sel = [c for c in fuzzer.configs if not sys.argv[1:] or c[0] in sys.argv[1:]]

    def per_config(x):
        site, prim, cfg = x
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.struct_mode = False
        cfg.sv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output.v")
        ball, bank = BALLS[site]
        aux = [a for a in AUX if a != ball][:5]
        for mode in ("IREG_OREG", "IDDRX1_ODDRX1"):
            def substs(v, mode=mode):
                return dict(d_ball=ball, iostd="LVCMOS18H" if bank in HP_BANKS else "LVCMOS33",
                            clk_ball=CLK_BALL, t_ball=aux[0], i_ball=aux[1], i2_ball=aux[2], o_ball=aux[3],
                            o2_ball=aux[4], body=BODY[mode, v])
            nonrouting.fuzz_enum_setting(cfg, empty, "{}.{}.OUTPUT".format(prim, mode), ["DISABLED", "ENABLED"],
                                         substs, False)

    fuzzloops.parallel_foreach(sel, per_config)


if __name__ == "__main__":
    main()
