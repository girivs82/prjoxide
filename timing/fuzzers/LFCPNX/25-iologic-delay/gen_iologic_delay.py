# LFCPNX: the IO logic delay cells' dynamic pins, for their fabric connections.
#   OUTDELAYA (LPDDR4 write delay): LOAD_N_LPDDR4_WT / MOVE_LPDDR4_WT / DIRECTION_LPDDR4_WT from
#   registers, COUT_LPDDR4_WT captured; DELAYA (input delay): LOAD_N / MOVE / DIRECTION from registers,
#   CFLAG captured. Every pin then has an SDF arc from or to a register whose route can be traced
#   (tools/radiant-fuzz/infer_iologic_conns.py).
#
# Runs 1-2: four DQS groups covering every bank 3 / 4 / 5 SYSIO_B<n>_0* tile type (the tile types
#   that hold both pads' IO logic pins): bank 3 PB150, bank 4 PB54 and PB66 (the MID group), bank 5
#   PB6. Each group: single-ended DQS (so the complement pad can be a DQ) with a DQSBUF, and every
#   other pad of the group a DQ, through 12-dqsbuf-ivref/gen_dqsbuf_ivref.py with OUTDLY=ENABLED
#   (OUTDELAYA, MARGIN_TEST_ENABLE ENABLED, on every DQ and DQS output) and DQ_DELAY=1.
# Run 3: the DQS pads themselves cannot take an input DELAYA next to their DQSBUF (map: the pad's
#   input cannot drive both a delay and other logic), so each group's DQS pad gets DELAYA + IDDRX4
#   (edge-clocked) on its own, with no DQSBUF.
#
# Usage: gen_iologic_delay.py <basename>   (run number N in work/design_N picks the variant)
import json, os, re, subprocess, sys

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.join(here, "..", "..", "..", "..")
base = sys.argv[1]
n = int(re.search(r'(\d+)$', base).group(1))
iodb = json.load(open(os.path.join(root, "database", "LFCPNX", "LFCPNX-100", "iodb.json")))
pk = iodb["packages"].index("LFG672")
GROUPS = [(3, 150), (4, 54), (4, 66), (5, 6)]


def group(bank, g):
    # AB19 / AB18 (PB58A / B, in group PB54) carry the reference clock
    pads = [p for p in iodb["pads"] if p["bank"] == bank and p["dqs"] and p["dqs"][1] == g and p["pins"][pk]
            and p["pins"][pk] not in ("AB19", "AB18")]
    dqs = next(p["pins"][pk] for p in pads if p["dqs"][0] == 1)
    dq = [p["pins"][pk] for p in sorted(pads, key=lambda p: p["offset"] * 2 + (p["name"][-1] == "B")) if p["dqs"][0] != 1]
    return dqs, dq


if n in (1, 2):
    env = dict(os.environ, GROUPS=repr([(dqs, dq, False) for dqs, dq in (group(b, g) for b, g in GROUPS)]),
               DQS_SE="1", OUTDLY="ENABLED", DQ_DELAY="1")
    subprocess.run([sys.executable, os.path.join(here, "..", "12-dqsbuf-ivref", "gen_dqsbuf_ivref.py"), base],
                   env=env, check=True)
else:
    pads = [group(b, g)[0] for b, g in GROUPS]
    v = ["module top(input refclk, input d, output q, {});".format(", ".join("input p{}".format(i) for i in range(len(pads)))),
         "    wire eclk, sclk;",
         "    ECLKSYNC #(.STOP_EN(\"DISABLE\")) u_es (.ECLKIN(refclk), .STOP(1'b0), .ECLKOUT(eclk));",
         "    ECLKDIV #(.ECLK_DIV(\"4\"), .GSR(\"DISABLED\")) u_ed (.ECLKIN(eclk), .DIVRST(1'b0), .SLIP(1'b0), .DIVOUT(sclk));",
         "    reg [{}:0] s; always @(posedge sclk) s <= {{s[{}:0], d ^ s[{}]}};".format(5 * len(pads) - 1, 5 * len(pads) - 2, 5 * len(pads) - 1),
         "    wire [{}:0] c;".format(9 * len(pads) - 1)]
    for i in range(len(pads)):
        k = 5 * i
        v.append("    wire p{0}_d; wire [7:0] p{0}_q;".format(i))
        v.append('    DELAYA #(.DEL_MODE("USER_DEFINED"), .DEL_VALUE("0")) u_p{0}_dl (.A(p{0}), .LOAD_N(s[{1}]), .MOVE(s[{2}]), .DIRECTION(s[{3}]), '
                 ".COARSE0(1'b0), .COARSE1(1'b0), .RANKSELECT(1'b0), .RANKENABLE(1'b0), .RANK0UPDATE(1'b0), .RANK1UPDATE(1'b0), "
                 ".Z(p{0}_d), .EDETERR(), .CFLAG(c[{4}]));".format(i, k, k + 1, k + 2, 9 * i + 8))
        v.append('    IDDRX4 #(.GSR("DISABLED")) u_p{0}_i (.D(p{0}_d), .ECLK(eclk), .SCLK(sclk), .RST(s[{1}]), .ALIGNWD(s[{2}]), {3});'.format(
            i, k + 3, k + 4, ", ".join(".Q{0}(c[{1}])".format(j, 9 * i + j) for j in range(8))))
    v.append("    reg qq; always @(posedge sclk) qq <= ^c; assign q = qq;")
    v.append("endmodule")
    open(base + ".v", "w").write("\n".join(v) + "\n")
    p = ["ldc_set_location -site {AB19} [get_ports refclk]", "ldc_set_port -iobuf {IO_TYPE=LVSTLD_I} [get_ports refclk]",
         "ldc_set_location -site {R5} [get_ports d]", "ldc_set_port -iobuf {IO_TYPE=LVCMOS33} [get_ports d]",
         "ldc_set_location -site {M9} [get_ports q]", "ldc_set_port -iobuf {IO_TYPE=LVCMOS33} [get_ports q]"]
    for i, pad in enumerate(pads):
        p += ["ldc_set_location -site {%s} [get_ports p%d]" % (pad, i), "ldc_set_port -iobuf {IO_TYPE=LVSTL_I} [get_ports p%d]" % i]
    open(base + ".pdc", "w").write("\n".join(p) + "\n")
