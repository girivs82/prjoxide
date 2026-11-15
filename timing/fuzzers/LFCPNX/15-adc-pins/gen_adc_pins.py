# LFCPNX: the ADC (ADC_CORE) with every fabric input driven by its own register and every output
# captured, so each pin's SDF arc starts or ends at a register whose route is traceable; for
# inferring the ADC pin connections (tools/radiant-fuzz/infer_adc_conns.py). Radiant places an ADC
# only at grade 8 / 9 in the industrial operating condition (see the Makefile). CLKDCLK can only be
# driven by a PLL CLKOS4 and is left open; CLKFAB comes from the clock pin.
#
# Usage: gen_adc_pins.py <basename>   (writes <basename>.v and <basename>.pdc)
import random
import sys

INS = [("ADCEN", 0), ("CAL", 0), ("CHAEN", 0), ("CHASEL", 4), ("CHBEN", 0), ("CHBSEL", 4), ("CONVSTOP", 0),
       ("RESETN", 0), ("RSTN", 0), ("SOC", 0)]
OUTS = [("CALRDY", 0), ("COG", 0), ("DA", 12), ("DB", 12), ("EOC", 0), ("COMP1O", 0), ("COMP2O", 0),
        ("COMP3O", 0), ("COMP1OL", 0), ("COMP2OL", 0), ("COMP3OL", 0)]
base = sys.argv[1]
conns, cap, src = [".CLKFAB(clk)"], [], 0
for name, n in INS:
    w = max(n, 1)
    conns.append(".{}(s[{}:{}])".format(name, src + w - 1, src) if n else ".{}(s[{}])".format(name, src))
    src += w
body = []
for name, n in OUTS:
    o = "o_" + name.lower()
    body.append("    wire [{}:0] {};".format(max(n, 1) - 1, o))
    conns.append(".{}({})".format(name, o))
    cap.append(o)
v = ["module top(input clk, input d, output q);", "    reg [{}:0] s;".format(src - 1)]
v += body
v.append("    ADC u_adc ({});".format(", ".join(conns)))
order = list(range(1, src))
random.shuffle(order)
v.append("    always @(posedge clk) begin")
v.append("        s[0] <= d ^ s[{}];".format(src - 1))
prev = 0
for k in order:
    v.append("        s[{}] <= s[{}] ^ d;".format(k, prev))
    prev = k
v.append("    end")
v.append("    reg [{}:0] c; always @(posedge clk) c <= {{{}}};".format(
    sum(max(n, 1) for _, n in OUTS) - 1, ", ".join(reversed(cap))))
v.append("    assign q = ^c;")
v.append("endmodule")
open(base + ".v", "w").write("\n".join(v) + "\n")
open(base + ".pdc", "w").write("".join("ldc_set_location -site {{{}}} [get_ports {}]\nldc_set_port -iobuf {{IO_TYPE=LVCMOS33}} [get_ports {}]\n"
                                       .format(s, p, p) for p, s in (("clk", "P24"), ("d", "R5"), ("q", "M9"))))
