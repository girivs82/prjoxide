# LFCPNX: the internal oscillator (OSCA -> OSC_CORE_R1C137) with its fabric inputs (HFOUTEN,
# HFSDSCEN) driven by their own registers and its clock outputs (HFCLKOUT, LFCLKOUT) each clocking a
# register, so the input pins' SDF arcs start at a register whose route is traceable and the outputs'
# routes show in the decoded routing. For inferring the oscillator's connections
# (tools/radiant-fuzz/infer_edge_block_conns.py osc; see fuzzers/LFCPNX/091-osc/README.md).
#
# Usage: gen_osc_pins.py <basename>   (writes <basename>.v and <basename>.pdc)
import random
import sys

base = sys.argv[1]
div = random.choice([2, 4, 8, 16, 32, 64, 128])
order = [0, 1]
random.shuffle(order)
v = ["module top(input clk, input d, output q);",
     "    reg [1:0] s; wire hf, lf;",
     '    OSCA #(.HF_CLK_DIV("{}")) u_osc (.HFOUTEN(s[{}]), .HFSDSCEN(s[{}]), .HFCLKOUT(hf), .LFCLKOUT(lf));'.format(
         div, order[0], order[1]),
     "    always @(posedge clk) begin s[0] <= d ^ s[1]; s[1] <= s[0] ^ d; end",
     "    reg h, l; always @(posedge hf) h <= d ^ h; always @(posedge lf) l <= d ^ l;",
     "    reg r; always @(posedge clk) r <= h ^ l;",
     "    assign q = r;",
     "endmodule"]
open(base + ".v", "w").write("\n".join(v) + "\n")
open(base + ".pdc", "w").write("".join("ldc_set_location -site {{{}}} [get_ports {}]\nldc_set_port -iobuf {{IO_TYPE=LVCMOS33}} [get_ports {}]\n"
                                       .format(s, p, p) for p, s in (("clk", "P24"), ("d", "R5"), ("q", "M9"))))
