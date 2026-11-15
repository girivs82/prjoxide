# LFCPNX: DQSBUF_IVREF (the DQSBUF with the internal LVSTL input reference, IVREFI[6:0]), one per
# HP bank (par places at most one per bank): a random bank-3 DQS group, and the bank-4 / bank-5 groups
# at PB54 / PB6. Every DQSBUF input, IVREFI included, is driven by its own fabric register and every
# output is captured, so each pin's SDF arc starts or ends at a register whose route is traceable.
# For inferring the IVREF_CORE connections (tools/radiant-fuzz/infer_dqsbuf_conns.py; see
# fuzzers/LFCPNX/037-ivref).
#
# Each group: DQS bidir (LVSTLD_I) on ODDRX4DQS / TSHX4DQS, two DQ bidirs (LVSTL_I) on ODDRX4DQ /
# TSHX4DQ / IDDRX4DQ; shared ECLKSYNC / ECLKDIV / DDRDLL from a 100 MHz LVSTLD_I reference clock
# (the Versa board's DDR reference clock pins).
#
# Usage: gen_dqsbuf_ivref.py <basename>   (writes <basename>.v and <basename>.pdc)
#   GROUPS="[(dqs pad, [dq pads], use_ivref), ...]" overrides the groups (single-bank probes).
import random
import sys

# (DQS t pad, DQ pads[, use DQSBUF_IVREF])
import os
# one DQSBUF_IVREF per bank (par places at most one per bank): a random bank-3 group, and the
# bank-4 and bank-5 groups at PB54 / PB6
B3 = [("AF4", ["AA6", "Y6"]), ("AF6", ["AD6", "AE6"]), ("AF10", ["W10", "W11"]), ("AF12", ["AD12", "AE11"])]
GROUPS = eval(os.environ["GROUPS"]) if "GROUPS" in os.environ else \
    [random.choice(B3), ("AF22", ["AD21", "AE21"]), ("U26", ["V24", "V25"])]
IN_PINS = [("RDCLKSEL", 4), ("RDDIR", 0), ("RDLOADN", 0), ("READ", 4), ("READMOVE", 0), ("SELCLK", 0),
           ("WRDIR", 0), ("WRLOAD_N", 0), ("WRLVDIR", 0), ("WRLVLOAD_N", 0), ("WRLVMOVE", 0), ("WRMOVE", 0),
           ("PAUSE", 0), ("RST", 0), ("RSTSMCNT", 0), ("IVREFI", 7)]
OUT_PINS = [("BTDETECT", 0), ("BURSTDETECT", 0), ("DATAVALID", 0), ("READCOUT", 0), ("WRCOUT", 0),
            ("WRLVCOUT", 0), ("DQSWRD", 0)]

base = sys.argv[1]
v, pdc = [], []
src = 0
cap = []


def sreg(n):
    global src
    r = "s[{}:{}]".format(src + n - 1, src) if n > 1 else "s[{}]".format(src)
    src += n
    return r


ports = ["input refclk", "input d", "output q"]
pdc += ["ldc_set_location -site {AB19} [get_ports refclk]",
        "ldc_set_port -iobuf {IO_TYPE=LVSTLD_I} [get_ports refclk]",
        "ldc_set_location -site {R5} [get_ports d]", "ldc_set_port -iobuf {IO_TYPE=LVCMOS33} [get_ports d]",
        "ldc_set_location -site {M9} [get_ports q]", "ldc_set_port -iobuf {IO_TYPE=LVCMOS33} [get_ports q]"]
body = ["    wire eclk, sclk; wire [8:0] code; wire lock;",
        '    ECLKSYNC #(.STOP_EN("DISABLE")) u_es (.ECLKIN(refclk), .STOP(1\'b0), .ECLKOUT(eclk));',
        '    ECLKDIV #(.ECLK_DIV("4"), .GSR("DISABLED")) u_ed (.ECLKIN(eclk), .DIVRST(1\'b0), .SLIP(1\'b0), .DIVOUT(sclk));']
body.append('    DDRDLL #(.GSR("DISABLED")) u_dll (.CLKIN(eclk), .RST({}), .FREEZE({}), .UDDCNTL_N({}), .CODE(code), .LOCK(lock), .DCNTL());'
            .format(sreg(1), sreg(1), sreg(1)))
cap.append("lock")
for g, grp in enumerate(GROUPS):
    dqs, dqs_dq = grp[0], grp[1]
    ivref = grp[2] if len(grp) > 2 else True
    ports += ["inout dqs{}".format(g), "inout [{}:0] dq{}".format(len(dqs_dq) - 1, g)]
    pdc += ["ldc_set_location -site {{{}}} [get_ports dqs{}]".format(dqs, g),
            "ldc_set_port -iobuf {{IO_TYPE=LVSTLD_I}} [get_ports dqs{}]".format(g)]
    for i, p in enumerate(dqs_dq):
        pdc += ["ldc_set_location -site {{{}}} [get_ports {{dq{}[{}]}}]".format(p, g, i),
                "ldc_set_port -iobuf {{IO_TYPE=LVSTL_I}} [get_ports {{dq{}[{}]}}]".format(g, i)]
    w = "g{}_".format(g)
    body.append("    wire {0}dqsi, {0}r90, {0}w, {0}w270, {0}dqso, {0}dqst; wire [2:0] {0}rdp, {0}wrp;".format(w))
    conns = [".DQSI({}dqsi)".format(w), ".ECLKIN(eclk)", ".SCLK(sclk)", ".DLLCODE(code)"]
    for name, n in IN_PINS:
        if name == "IVREFI" and not ivref:
            continue
        conns.append(".{}({})".format(name, sreg(max(n, 1))))
    conns += [".DQSR90({}r90)".format(w), ".DQSW({}w)".format(w), ".DQSW270({}w270)".format(w),
              ".RDPNTR({}rdp)".format(w), ".WRPNTR({}wrp)".format(w)]
    for name, n in OUT_PINS:
        o = "{}{}".format(w, name.lower())
        body.append("    wire {};".format(o))
        conns.append(".{}({})".format(name, o))
        cap.append(o)
    body.append('    ' + ('DQSBUF_IVREF' if ivref else 'DQSBUF') + ' #(.GSR("DISABLED"), .ENABLE_FIFO("ENABLED"), .MODX("MDDRX4"), .READ_ENABLE("ENABLED"), '
                '.WRITE_ENABLE("ENABLED")) u_dqs{} ({});'.format(g, ", ".join(conns)))
    rst = sreg(1)
    body.append('    ODDRX4DQS #(.GSR("DISABLED")) u_dqso{} (.D0({}),.D1({}),.D2({}),.D3({}),.D4({}),.D5({}),.D6({}),.D7({}), '
                '.DQSW({w}w), .ECLK(eclk), .SCLK(sclk), .RST({}), .Q({w}dqso));'.format(
                    g, *[sreg(1) for _ in range(8)], rst, w=w))
    body.append('    TSHX4DQS #(.GSR("DISABLED")) u_dqst{} (.T0({}),.T1({}),.T2({}),.T3({}), .DQSW({w}w), .ECLK(eclk), '
                '.SCLK(sclk), .RST({}), .Q({w}dqst));'.format(g, *[sreg(1) for _ in range(4)], rst, w=w))
    body.append("    assign dqs{0} = {1}dqst ? 1'bz : {1}dqso; assign {1}dqsi = dqs{0};".format(g, w))
    for i in range(len(dqs_dq)):
        x = "{}d{}_".format(w, i)
        body.append("    wire {0}o, {0}t; wire [7:0] {0}q;".format(x))
        body.append('    ODDRX4DQ #(.GSR("DISABLED")) u_{x}o (.D0({}),.D1({}),.D2({}),.D3({}),.D4({}),.D5({}),.D6({}),.D7({}), '
                    '.DQSW270({w}w270), .ECLK(eclk), .SCLK(sclk), .RST({}), .Q({x}o));'.format(
                        *[sreg(1) for _ in range(8)], rst, w=w, x=x))
        body.append('    TSHX4DQ #(.GSR("DISABLED")) u_{x}t (.T0({}),.T1({}),.T2({}),.T3({}), .DQSW270({w}w270), .ECLK(eclk), '
                    '.SCLK(sclk), .RST({}), .Q({x}t));'.format(*[sreg(1) for _ in range(4)], rst, w=w, x=x))
        body.append("    assign dq{g}[{i}] = {x}t ? 1'bz : {x}o;".format(g=g, i=i, x=x))
        body.append('    IDDRX4DQ #(.GSR("DISABLED")) u_{x}i (.D(dq{g}[{i}]), .DQSR90({w}r90), .ECLK(eclk), .SCLK(sclk), .RST({r}), '
                    '.RDPNTR0({w}rdp[0]), .RDPNTR1({w}rdp[1]), .RDPNTR2({w}rdp[2]), .WRPNTR0({w}wrp[0]), .WRPNTR1({w}wrp[1]), '
                    '.WRPNTR2({w}wrp[2]), .Q0({x}q[0]),.Q1({x}q[1]),.Q2({x}q[2]),.Q3({x}q[3]),.Q4({x}q[4]),.Q5({x}q[5]),'
                    '.Q6({x}q[6]),.Q7({x}q[7]));'.format(g=g, i=i, x=x, w=w, r=rst))
        cap.append("^{}q".format(x))

v.append("module top({});".format(", ".join(ports)))
v.append("    reg [{}:0] s;".format(src - 1))
v.append("    reg [{}:0] c;".format(len(cap) - 1))
v += body
# a chain through the source registers, each XORed with the input (no plain shift register)
v.append("    always @(posedge sclk) begin")
v.append("        s[0] <= d ^ s[{}];".format(src - 1))
order = list(range(1, src))
random.shuffle(order)
prev = 0
for k in order:
    v.append("        s[{}] <= s[{}] ^ d;".format(k, prev))
    prev = k
v.append("    end")
v.append("    always @(posedge sclk) c <= {{{}}};".format(", ".join(reversed(cap))))
v.append("    assign q = ^c;")
v.append("endmodule")
open(base + ".v", "w").write("\n".join(v) + "\n")
open(base + ".pdc", "w").write("\n".join(pdc) + "\n")
