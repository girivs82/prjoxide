# LFCPNX: every edge-clock block of HP banks 3 / 4 / 5 in one design, for verifying their connections
# against Radiant's routing (tools/radiant-fuzz/infer_edge_block_conns.py eclksync / eclkdiv, and
# check_eclk_routing.py). Per bank:
# - the 4 ECLKSYNCs, pinned to sites ECLKSYNC_CORE_R73C<col><A-D> (edge clock 0-3), each fed from a
#   different PCLK pin of the bank (random permutation), STOP from its own register;
# - the 4 ECLKDIVs (ECLK_DIV 2), pinned to ECLKDIV_CORE_R73C<col><A-D>, DIVRST and SLIP from their
#   own registers;
# - per index j an ODDRX2 on its own pad (ECLK = the edge clock j of the bank, SCLK from ECLKDIV j)
#   and a fabric register clocked by ECLKDIV j's output.
# A bank's edge clock j (its ECLKCASMUX output j) can only carry an index-j ECLKSYNC: its own, or one
# of another bank through the cascade inputs; and an ECLKSYNC always occupies its own bank's edge clock
# j, and an edge clock may drive only one ECLKDIV (par refuses anything else). So runs 1-12 use every
# bank's own ECLKSYNCs; runs 13+ (cascade runs), for each j, leave one random bank's ECLKSYNC j out
# and clock that bank's ECLKDIV j and ODDRX2 j from another random bank's ECLKSYNC j through the
# cascade input; the source bank then has no ECLKDIV j, and its ODDRX2 j takes SCLK from the
# destination bank's ECLKDIV j (the same edge clock, divided).
# Bank -> site column: 3 -> 74, 4 -> 73, 5 -> 72.
#
# Usage: gen_eclk_pins.py <basename>   (writes <basename>.v and <basename>.pdc)
import random
import sys

COL = {3: 74, 4: 73, 5: 72}
PCLK = {3: ["AC12", "AB11", "Y5", "AB4"], 4: ["AD21", "AB19", "AA13", "AE13"], 5: ["V23", "W24", "AD25", "AC21"]}
OPADS = {3: ["Y6", "AA6", "AD5", "AE5"], 4: ["AF22", "AF23", "AD20", "AC19"], 5: ["V24", "V25", "U26", "V26"]}
IO = "LVCMOS12H"

base = sys.argv[1]
ports, pdc, body = ["input clk", "input d", "output q"], [], []
src = 0
caps = []


def reg():
    global src
    src += 1
    return "s[{}]".format(src - 1)


for p, s_ in (("clk", "P24"), ("d", "R5"), ("q", "M9")):
    pdc += ["ldc_set_location -site {{{}}} [get_ports {}]".format(s_, p),
            "ldc_set_port -iobuf {{IO_TYPE=LVCMOS33}} [get_ports {}]".format(p)]
import re
run = int(re.search(r'(\d+)$', base).group(1))
# src[(b, j)]: the bank whose ECLKSYNC j clocks bank b's ECLKDIV j and ODDRX2 j
src_bank = {(b, j): b for b in (3, 4, 5) for j in range(4)}
sclk_from = {(b, j): (b, j) for b in (3, 4, 5) for j in range(4)}   # ODDRX2 (b, j) SCLK: ECLKDIV
no_div = set()
if run > 12:
    for j in range(4):
        dst, sb = random.sample([3, 4, 5], 2)
        src_bank[(dst, j)] = sb
        no_div.add((sb, j))
        sclk_from[(sb, j)] = (dst, j)
used = set(src_bank.values()) and {(sb, j) for (b, j), sb in src_bank.items()}
for b in (3, 4, 5):
    pcl = random.sample(PCLK[b], 4)
    for k in range(4):
        if (b, k) not in used:
            continue
        pn = "pclk{}_{}".format(b, k)
        ports.append("input " + pn)
        pdc += ["ldc_set_location -site {{{}}} [get_ports {}]".format(pcl[k], pn),
                "ldc_set_port -iobuf {{IO_TYPE={}}} [get_ports {}]".format(IO, pn)]
        body.append("    wire e{0}_{1}; ECLKSYNC #(.STOP_EN(\"ENABLE\")) u_es{0}_{1} (.ECLKIN({2}), .STOP({3}), .ECLKOUT(e{0}_{1}));"
                    .format(b, k, pn, reg()))
        pdc.append("ldc_set_location -site {{ECLKSYNC_CORE_R73C{}{}}} [get_cells u_es{}_{}.ECLKSYNC_inst]".format(
            COL[b], "ABCD"[k], b, k))
for b in (3, 4, 5):
    for j in range(4):
        eck = "e{}_{}".format(src_bank[(b, j)], j)
        if (b, j) not in no_div:
            body.append("    wire c{0}_{1}; ECLKDIV #(.ECLK_DIV(\"2\"), .GSR(\"DISABLED\")) u_ed{0}_{1} (.ECLKIN({2}), .DIVRST({3}), .SLIP({4}), .DIVOUT(c{0}_{1}));"
                    .format(b, j, eck, reg(), reg()))
            pdc.append("ldc_set_location -site {{ECLKDIV_CORE_R73C{}{}}} [get_cells u_ed{}_{}.ECLKDIV_inst]".format(
                COL[b], "ABCD"[j], b, j))
        on = "o{}_{}".format(b, j)
        ports.append("output " + on)
        pdc += ["ldc_set_location -site {{{}}} [get_ports {}]".format(OPADS[b][j], on),
                "ldc_set_port -iobuf {{IO_TYPE={}}} [get_ports {}]".format(IO, on)]
        body.append('    ODDRX2 #(.GSR("DISABLED")) u_od{0}_{1} (.D0({2}),.D1({3}),.D2({4}),.D3({5}), .ECLK({6}), .SCLK(c{9}_{10}), .RST({7}), .Q({8}));'
                    .format(b, j, reg(), reg(), reg(), reg(), eck, reg(), on, *sclk_from[(b, j)]))
        if (b, j) not in no_div:
            body.append("    reg r{0}_{1}; always @(posedge c{0}_{1}) r{0}_{1} <= d ^ r{0}_{1};".format(b, j))
            caps.append("r{}_{}".format(b, j))
v = ["module top({});".format(", ".join(ports)), "    reg [{}:0] s;".format(src - 1)] + body
order = list(range(1, src))
random.shuffle(order)
v.append("    always @(posedge clk) begin")
v.append("        s[0] <= d ^ s[{}];".format(src - 1))
prev = 0
for k in order:
    v.append("        s[{}] <= s[{}] ^ d;".format(k, prev))
    prev = k
v.append("    end")
v.append("    reg [{}:0] c; always @(posedge clk) c <= {{{}}};".format(len(caps) - 1, ", ".join(caps)))
v.append("    assign q = ^c;")
v.append("endmodule")
open(base + ".v", "w").write("\n".join(v) + "\n")
open(base + ".pdc", "w").write("\n".join(pdc) + "\n")
