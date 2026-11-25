"""
Designs for oversampling a DQS pad with plain edge-clocked input gearing (see README.md).
Usage: gen.py <outdir>. Writes <name>.v / <name>.pdc for each variant; build each with
radiant.sh LFCPNX-100 <name> in the Radiant container and decode with prjoxide.

Base: 156-dqsw-iologic's phy1 byte lane (DQS at AF4 = PB150A), as built by
timing/fuzzers/LFCPNX/24-dqsbuf-pins run 2 (DQSBUF_IVREF, LVSTL IO types).
"""
import os, re, sys

here = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
src = os.path.join(here, "..", "156-dqsw-iologic")
v = open(os.path.join(src, "phy1.v")).read().replace("module phy1(", "module top(")
p = open(os.path.join(src, "phy1.pdc")).read()
# DQSBUF_IVREF and LVSTL IO types, as 24-dqsbuf-pins run 2
v = v.replace('DQSBUF #(.GSR("DISABLED"),', 'DQSBUF_IVREF #(.GSR("DISABLED"), .LPDDR4_BL16_EN("ENABLED"),')
v = v.replace(".DLLCODE(code),", ".DLLCODE(code), .IVREFI(7'd49),")
p = p.replace("IO_TYPE=HSUL12D} [get_ports dqs]", "IO_TYPE=LVSTLD_I} [get_ports dqs]")
p = re.sub(r"IO_TYPE=HSUL12\}", "IO_TYPE=LVSTL_I}", p).replace("IO_TYPE=HSUL12D}", "IO_TYPE=LVSTLD_I}") \
    .replace("IO_TYPE=LVDS}", "IO_TYPE=LVSTLD_I}")

IDDR = '''    wire [7:0] dqsov;
    IDDRX4 #(.GSR("DISABLED")) u_dqsi (.D({d}), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .ALIGNWD(r[60]),
             .Q0(dqsov[0]),.Q1(dqsov[1]),.Q2(dqsov[2]),.Q3(dqsov[3]),.Q4(dqsov[4]),.Q5(dqsov[5]),.Q6(dqsov[6]),.Q7(dqsov[7]));
'''
DELAY = '''    wire {o};
    DELAYA #(.DEL_MODE("USER_DEFINED"), .DEL_VALUE("16"), .COARSE_DELAY_MODE("DYNAMIC")) u_dqsdl (.A({i}), .LOAD_N(r[61]), .MOVE(r[62]), .DIRECTION(r[63]),
             .COARSE0(r[59]), .COARSE1(r[58]), .RANKSELECT(1'b0), .RANKENABLE(1'b0), .RANK0UPDATE(1'b0), .RANK1UPDATE(1'b0), .Z({o}), .EDETERR(), .CFLAG());
'''


def with_iddr(s, d, delay_from=None):
    add = (DELAY.format(o=d, i=delay_from) if delay_from else "") + IDDR.format(d=d)
    s = s.replace("    // DQ\n", add + "    // DQ\n", 1)
    return s.replace("always @(posedge sclk) q <= ^{qd,", "always @(posedge sclk) q <= ^{qd, dqsov,")


def input_only(s):
    s = s.replace("inout dqs,", "input dqs,")
    s = re.sub(r"    ODDRX4DQS #\(.*?\n.*?\);\n", "", s, flags=re.S)
    s = re.sub(r"    TSHX4DQS #\(.*?\);\n", "", s)
    return s.replace("assign dqs = dqs_t ? 1'bz : dqs_o; assign dqs_in = dqs;", "assign dqs_in = dqs;")


def split_pair(s, pp):
    """single-ended DQS on AF4 into a plain DQSBUF, a separate input dqsc on AF3"""
    s = s.replace('DQSBUF_IVREF #(.GSR("DISABLED"), .LPDDR4_BL16_EN("ENABLED"),', 'DQSBUF #(.GSR("DISABLED"),')
    s = s.replace(", .IVREFI(7'd49)", "").replace("inout dqs,", "inout dqs, input dqsc,")
    pp = pp.replace("IO_TYPE=LVSTLD_I} [get_ports dqs]", "IO_TYPE=LVSTL_I} [get_ports dqs]")
    return s, pp + "ldc_set_location -site {AF3} [get_ports dqsc]\nldc_set_port -iobuf {IO_TYPE=LVSTL_I} [get_ports dqsc]\n"


ALONE = '''module top(input refclk, input d, output reg q, input dqs);
    wire eclk, sclk;
    ECLKSYNC #(.STOP_EN("DISABLE")) u_es (.ECLKIN(refclk), .STOP(1'b0), .ECLKOUT(eclk));
    ECLKDIV #(.ECLK_DIV("{div}"), .GSR("DISABLED")) u_ed (.ECLKIN(eclk), .DIVRST(1'b0), .SLIP(1'b0), .DIVOUT(sclk));
    reg [7:0] r; always @(posedge sclk) r <= {{r[6:0], d}};
{body}    always @(posedge sclk) q <= ^dqsov;
endmodule
'''
ALONE_PDC = '''ldc_set_location -site {AB19} [get_ports refclk]
ldc_set_location -site {R5} [get_ports d]
ldc_set_location -site {M9} [get_ports q]
ldc_set_location -site {AF4} [get_ports dqs]
ldc_set_port -iobuf {IO_TYPE=LVCMOS33} [get_ports d]
ldc_set_port -iobuf {IO_TYPE=LVCMOS33} [get_ports q]
ldc_set_port -iobuf {IO_TYPE=LVSTLD_I} [get_ports refclk]
ldc_set_port -iobuf {IO_TYPE=LVSTLD_I} [get_ports dqs]
'''
X4 = ('    wire [7:0] dqsov;\n    IDDRX4 #(.GSR("DISABLED")) u_dqsi (.D({d}), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .ALIGNWD(r[6]),\n'
      '             .Q0(dqsov[0]),.Q1(dqsov[1]),.Q2(dqsov[2]),.Q3(dqsov[3]),.Q4(dqsov[4]),.Q5(dqsov[5]),.Q6(dqsov[6]),.Q7(dqsov[7]));\n')
X2 = ('    wire [3:0] dqsov;\n    IDDRX2 #(.GSR("DISABLED")) u_dqsi (.D(dqs), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .ALIGNWD(r[6]),\n'
      '             .Q0(dqsov[0]),.Q1(dqsov[1]),.Q2(dqsov[2]),.Q3(dqsov[3]));\n')
DL_ALONE = ('    wire dqs_d;\n    DELAYA #(.DEL_MODE("USER_DEFINED"), .DEL_VALUE("16"), .COARSE_DELAY_MODE("DYNAMIC")) u_dqsdl (.A(dqs), .LOAD_N(r[0]), .MOVE(r[1]), .DIRECTION(r[2]),\n'
            "             .COARSE0(r[4]), .COARSE1(r[5]), .RANKSELECT(1'b0), .RANKENABLE(1'b0), .RANK0UPDATE(1'b0), .RANK1UPDATE(1'b0), .Z(dqs_d), .EDETERR(), .CFLAG());\n")

designs = {}
designs["base"] = (v, p)
designs["a"] = (with_iddr(v, "dqs_in"), p)                                    # bidir DQS + write gearing
designs["a2"] = (with_iddr(input_only(v), "dqs_in"), p)                       # input-only DQS
s = re.sub(r"    TSHX4DQS #\(.*?\);\n", "", with_iddr(v, "dqs_in"))
designs["a4"] = (s.replace("assign dqs = dqs_t ? 1'bz : dqs_o;", "assign dqs = r[33] ? 1'bz : dqs_o;"), p)  # ODDRX4DQS only
designs["a2d"] = (with_iddr(input_only(v), "dqs_d", "dqs_in"), p)             # DELAYA -> IDDRX4, pad -> DQSI
designs["a2d2"] = (designs["a2d"][0].replace(".DQSI(dqs_in)", ".DQSI(dqs_d)"), p)  # DELAYA -> DQSI too
designs["a3"] = (ALONE.format(div="4", body=X4.format(d="dqs")), ALONE_PDC)  # IDDRX4 alone on AF4
designs["a3d"] = (ALONE.format(div="4", body=DL_ALONE + X4.format(d="dqs_d")), ALONE_PDC)
designs["x2"] = (ALONE.format(div="2", body=X2), ALONE_PDC)                  # IDDRX2 alone on AF4
bv, bp = split_pair(v, p)
designs["b"] = (with_iddr(bv, "dqsc"), bp)                                    # IDDRX4 on the complement AF3
designs["b2"] = (with_iddr(bv, "dqsc_d", "dqsc"), bp)
for n, (vv, pp) in designs.items():
    open(os.path.join(out, n + ".v"), "w").write(vv)
    open(os.path.join(out, n + ".pdc"), "w").write(pp)
    print(n)
