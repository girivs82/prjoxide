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
#   FABCLK=clk|dcc|lut|eclk also uses DQSR90 / DQSW / DQSW270 in fabric (a register clock, a DCC, a
#   LUT input, an ECLKSYNC); map refuses all of them (see fuzzers/LFCPNX/037-ivref/README.md).
#   GEAR=X2 builds X2 gearing instead of X4 (ODDRX2DQ / ODDRX2DQS / TSHX2DQ / TSHX2DQS / IDDRX2DQ,
#   ECLKDIV 2, DQSBUF MODX=MDDRX2); for the X2 DDRMODE / DQSW_CLK bits of 156-dqsw-iologic.
#   DQS_SE=1 makes every DQS pad single-ended (LVSTL_I), so a DQ can go on its complement pad.
#   ECLK_IDX=0..3 pins the ECLKSYNC and the ECLKDIV to bank 4's edge clock of that index
#   (ECLKSYNC_CORE_R73C73<A-D>, ECLKDIV_CORE_R73C73<A-D>); banks 3 / 5 get it through their cascade
#   inputs. For the DQSBUF edge-clock input select (fuzzers/LFCPNX/153-dqsbuf/README.md).
#   ECLK_COL=74|73|72 puts them in bank 3 / 4 / 5's edge-clock column instead of bank 4's.
#   DQ_DELAY=1 puts a DELAYA with its dynamic pins (LOAD_N / MOVE / DIRECTION from registers, CFLAG
#   captured) between each DQ pad and its IDDRX4DQ (timing/fuzzers/LFCPNX/25-iologic-delay).
#   For fuzzers/LFCPNX/157-dqsbuf-ivref:
#   DQS_PARAMS='.NAME("VALUE"), ...' adds parameters to every DQSBUF / DQSBUF_IVREF.
#   OUTDLY=ENABLED|DISABLED puts an OUTDELAYA (MARGIN_TEST_ENABLE = that value) between the output /
#   tristate gearing and the pad, on the DQS and every DQ, as Lattice's LPDDR4 module does.
#   DQ_IO=<IO type> sets the DQ pads' IO type (default LVSTL_I); DQ_ATTR='VREF=VREF_INT ...' adds
#   attributes. DQ_IN=1 makes the DQ pads inputs (IDDRX4DQ only, no output gearing).
#   OUTDLY_PATH=d|t sends only the data (d) or only the tristate (t) through the OUTDELAYA;
#   OUTDLY_CTL=const ties its LOAD_N / DIRECTION / MOVE to constants and leaves COUT open.
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
OUTDLY = os.environ.get("OUTDLY")
DQ_IN = os.environ.get("DQ_IN") == "1"


def outdly(o, t, name):
    """Pass an output / tristate pair through an OUTDELAYA (OUTDLY set); return the pad-side pair."""
    if not OUTDLY:
        return o, t
    path = os.environ.get("OUTDLY_PATH", "both")     # both | d (data only) | t (tristate only)
    const = os.environ.get("OUTDLY_CTL") == "const"   # LOAD_N / DIRECTION / MOVE tied, COUT unused
    body.append("    wire {0}_do, {0}_to, {0}_co;".format(name))
    ctl = ("1'b1", "1'b0", "1'b0") if const else (sreg(1), sreg(1), sreg(1))
    body.append('    OUTDELAYA #(.MARGIN_TEST_ENABLE("{}")) u_{n}_odla (.DOUTI({di}), .TOUTI({ti}), .DOUT({n}_do), .TOUT({n}_to), '
                '.LOAD_N_LPDDR4_WT({}), .DIRECTION_LPDDR4_WT({}), .MOVE_LPDDR4_WT({}), .COUT_LPDDR4_WT({n}_co));'
                .format(OUTDLY, *ctl, n=name, di=o if path != "t" else "1'b0", ti=t if path != "d" else "1'b0"))
    if not const:
        cap.append("{}_co".format(name))
    return (name + "_do" if path != "t" else o), (name + "_to" if path != "d" else t)
X2 = os.environ.get("GEAR") == "X2"
NW = 4 if X2 else 8          # data bits per output gearing cell
NT = 2 if X2 else 4          # tristate bits
GX = "X2" if X2 else "X4"
DQS_IO = "LVSTL_I" if os.environ.get("DQS_SE") == "1" else "LVSTLD_I"
v, pdc = [], []
src = 0
cap = []


def sreg(n):
    global src
    r = "s[{}:{}]".format(src + n - 1, src) if n > 1 else "s[{}]".format(src)
    src += n
    return r


ports = ["input refclk", "input d", "output q"]
if os.environ.get("ECLK_IDX"):
    _l = "ABCD"[int(os.environ["ECLK_IDX"])]
    _c = os.environ.get("ECLK_COL", "73")
    pdc += ["ldc_set_location -site {{ECLKSYNC_CORE_R73C{}{}}} [get_cells u_es.ECLKSYNC_inst]".format(_c, _l),
            "ldc_set_location -site {{ECLKDIV_CORE_R73C{}{}}} [get_cells u_ed.ECLKDIV_inst]".format(_c, _l)]
pdc += ["ldc_set_location -site {AB19} [get_ports refclk]",
        "ldc_set_port -iobuf {IO_TYPE=LVSTLD_I} [get_ports refclk]",
        "ldc_set_location -site {R5} [get_ports d]", "ldc_set_port -iobuf {IO_TYPE=LVCMOS33} [get_ports d]",
        "ldc_set_location -site {M9} [get_ports q]", "ldc_set_port -iobuf {IO_TYPE=LVCMOS33} [get_ports q]"]
body = ["    wire eclk, sclk; wire [8:0] code; wire lock;",
        '    ECLKSYNC #(.STOP_EN("DISABLE")) u_es (.ECLKIN(refclk), .STOP(1\'b0), .ECLKOUT(eclk));',
        '    ECLKDIV #(.ECLK_DIV("{}"), .GSR("DISABLED")) u_ed (.ECLKIN(eclk), .DIVRST(1\'b0), .SLIP(1\'b0), .DIVOUT(sclk));'.format("2" if X2 else "4")]
body.append('    DDRDLL #(.GSR("DISABLED")) u_dll (.CLKIN(eclk), .RST({}), .FREEZE({}), .UDDCNTL_N({}), .CODE(code), .LOCK(lock), .DCNTL());'
            .format(sreg(1), sreg(1), sreg(1)))
cap.append("lock")
for g, grp in enumerate(GROUPS):
    dqs, dqs_dq = grp[0], grp[1]
    ivref = grp[2] if len(grp) > 2 else True
    ports += ["inout dqs{}".format(g), "{} [{}:0] dq{}".format("input" if DQ_IN else "inout", len(dqs_dq) - 1, g)]
    pdc += ["ldc_set_location -site {{{}}} [get_ports dqs{}]".format(dqs, g),
            "ldc_set_port -iobuf {{IO_TYPE={}}} [get_ports dqs{}]".format(DQS_IO, g)]
    for i, p in enumerate(dqs_dq):
        pdc += ["ldc_set_location -site {{{}}} [get_ports {{dq{}[{}]}}]".format(p, g, i),
                "ldc_set_port -iobuf {{IO_TYPE={}{}}} [get_ports {{dq{}[{}]}}]".format(
                    os.environ.get("DQ_IO", "LVSTL_I"), (" " + os.environ["DQ_ATTR"]) if os.environ.get("DQ_ATTR") else "", g, i)]
    w = "g{}_".format(g)
    body.append("    wire {0}dqsi, {0}r90, {0}w, {0}w270, {0}dqso, {0}dqst; wire [2:0] {0}rdp, {0}wrp;".format(w))
    conns = [".DQSI({}dqsi)".format(w), ".ECLKIN(eclk)", ".SCLK(sclk)", ".DLLCODE(code)"]
    for name, n in IN_PINS:
        if name == "IVREFI" and not ivref:
            continue
        conns.append(".{}({})".format(name, sreg(max(n, 1))))
    conns += [".DQSR90({}r90)".format(w), ".DQSW({}w)".format(w), ".DQSW270({}w270)".format(w),
              ".RDPNTR({}rdp)".format(w), ".WRPNTR({}wrp)".format(w)]
    if os.environ.get("FABCLK"):
        # also use the DQS clocks in fabric, so they leave through the CIB (SR90CIB / SW270CIB /
        # DQSWCIB): as the clock of a register (FABCLK=clk), or through a DCC (FABCLK=dcc)
        for ck in ("r90", "w", "w270"):
            ckn = "{}{}".format(w, ck)
            mode = os.environ["FABCLK"]
            if mode == "lut":
                # a LUT input: the clock XORed with a register, captured
                body.append("    reg {0}_q; always @(posedge sclk) {0}_q <= {1} ^ {2};".format(w + ck, ckn, sreg(1)))
                cap.append("{}_q".format(w + ck))
                continue
            if mode == "eclk":
                body.append("    wire {0}_e; ECLKSYNC #(.STOP_EN(\"DISABLE\")) u_{0}_es (.ECLKIN({0}), .STOP(1'b0), .ECLKOUT({0}_e));".format(ckn))
                ckn = ckn + "_e"
            if mode == "dcc":
                body.append("    wire {0}_g; DCC u_{0}_dcc (.CLKI({0}), .CE(1'b1), .CLKO({0}_g));".format(ckn))
                ckn = ckn + "_g"
            body.append("    reg {0}_q; always @(posedge {1}) {0}_q <= {2};".format(w + ck, ckn, sreg(1)))
            cap.append("{}_q".format(w + ck))
    for name, n in OUT_PINS:
        o = "{}{}".format(w, name.lower())
        body.append("    wire {};".format(o))
        conns.append(".{}({})".format(name, o))
        cap.append(o)
    body.append('    ' + ('DQSBUF_IVREF' if ivref else 'DQSBUF') + ' #(.GSR("DISABLED"), .ENABLE_FIFO("ENABLED"), .MODX("MDDR{}"), .READ_ENABLE("ENABLED"), '
                '.WRITE_ENABLE("ENABLED"){}) u_dqs{} ({});'.format(GX, (", " + os.environ["DQS_PARAMS"]) if os.environ.get("DQS_PARAMS") else "", g, ", ".join(conns)))
    rst = sreg(1)
    def dpins(p, n):
        return ",".join(".{}{}({})".format(p, k, sreg(1)) for k in range(n))
    body.append('    ODDR{}DQS #(.GSR("DISABLED")) u_dqso{} ({}, .DQSW({w}w), .ECLK(eclk), .SCLK(sclk), .RST({}), '
                '.Q({w}dqso));'.format(GX, g, dpins("D", NW), rst, w=w))
    body.append('    TSH{}DQS #(.GSR("DISABLED")) u_dqst{} ({}, .DQSW({w}w), .ECLK(eclk), .SCLK(sclk), .RST({}), '
                '.Q({w}dqst));'.format(GX, g, dpins("T", NT), rst, w=w))
    _o, _t = outdly(w + "dqso", w + "dqst", w + "dqs")
    body.append("    assign dqs{0} = {2} ? 1'bz : {1}; assign {3}dqsi = dqs{0};".format(g, _o, _t, w))
    for i in range(len(dqs_dq)):
        x = "{}d{}_".format(w, i)
        body.append("    wire {0}o, {0}t; wire [{1}:0] {0}q;".format(x, NW - 1))
        if not DQ_IN:
            body.append('    ODDR{}DQ #(.GSR("DISABLED")) u_{x}o ({}, .DQSW270({w}w270), .ECLK(eclk), .SCLK(sclk), .RST({}), '
                        '.Q({x}o));'.format(GX, dpins("D", NW), rst, w=w, x=x))
            body.append('    TSH{}DQ #(.GSR("DISABLED")) u_{x}t ({}, .DQSW270({w}w270), .ECLK(eclk), .SCLK(sclk), .RST({}), '
                        '.Q({x}t));'.format(GX, dpins("T", NT), rst, w=w, x=x))
            _o, _t = outdly(x + "o", x + "t", x + "pad")
            body.append("    assign dq{g}[{i}] = {t} ? 1'bz : {o};".format(g=g, i=i, o=_o, t=_t))
        din = "dq{}[{}]".format(g, i)
        if os.environ.get("DQ_DELAY") == "1":
            body.append("    wire {0}pd, {0}cf;".format(x))
            body.append('    DELAYA #(.DEL_MODE("USER_DEFINED"), .DEL_VALUE("0")) u_{x}dl (.A({a}), .LOAD_N({}), .MOVE({}), '
                        ".DIRECTION({}), .COARSE0(1'b0), .COARSE1(1'b0), .RANKSELECT(1'b0), .RANKENABLE(1'b0), "
                        ".RANK0UPDATE(1'b0), .RANK1UPDATE(1'b0), .Z({x}pd), .EDETERR(), .CFLAG({x}cf));".format(
                            sreg(1), sreg(1), sreg(1), x=x, a=din))
            cap.append("{}cf".format(x))
            din = x + "pd"
        body.append('    IDDR{gx}DQ #(.GSR("DISABLED")) u_{x}i (.D({din}), .DQSR90({w}r90), .ECLK(eclk), .SCLK(sclk), .RST({r}), '
                    '.RDPNTR0({w}rdp[0]), .RDPNTR1({w}rdp[1]), .RDPNTR2({w}rdp[2]), .WRPNTR0({w}wrp[0]), .WRPNTR1({w}wrp[1]), '
                    '.WRPNTR2({w}wrp[2]), {q});'.format(g=g, i=i, x=x, w=w, r=rst, gx=GX, din=din,
                                                       q=",".join(".Q{0}({1}q[{0}])".format(k, x) for k in range(NW))))
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
