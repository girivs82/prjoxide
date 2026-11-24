# LFCPNX: an ADC (ADC_CORE) with external references (1P6_TO_1P8), unipolar, CLK_DIV 2, clocked from
# PLL_LRC (pll_params.txt: CLKOP 100 MHz, CLKOS 25 MHz to CLKFAB, CLKOS4 50 MHz to CLKDCLK, from the
# 125 MHz P24 clock), every ADC control from a fabric FF and every output captured, and the analog
# pads Y6 / AA6 (ADC_CP14 / CN14) as LVSTL_I inputs with ENADC_IN. Through the timing flow, to check
# every ADC pin's connection against Radiant's routing (tools/radiant-fuzz/infer_adc_conns.py).
#
# Usage: gen_adc_cal.py <basename>
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
pll = open(os.path.join(here, "pll_params.txt")).read().strip()
base = sys.argv[1]
INS = [("ADCEN", 0), ("CAL", 0), ("CHAEN", 0), ("CHASEL", 4), ("CHBEN", 0), ("CHBSEL", 4), ("CONVSTOP", 0),
       ("RESETN", 0), ("RSTN", 0), ("SOC", 0)]
OUTS = [("CALRDY", 0), ("COG", 0), ("DA", 12), ("DB", 12), ("EOC", 0), ("COMP1O", 0), ("COMP2O", 0),
        ("COMP3O", 0), ("COMP1OL", 0), ("COMP2OL", 0), ("COMP3OL", 0)]
conns, src, body, cap = [".CLKFAB(fab)", ".CLKDCLK(conv)"], 0, [], []
for name, n in INS:
    w = max(n, 1)
    conns.append(".{}(s[{}:{}])".format(name, src + w - 1, src) if n else ".{}(s[{}])".format(name, src))
    src += w
for name, n in OUTS:
    o = "o_" + name.lower()
    body.append("    wire [{}:0] {};".format(max(n, 1) - 1, o))
    conns.append(".{}({})".format(name, o))
    cap.append(o)
v = ["module top(input clk, input d, input ainp, input ainn, output q);",
     "    wire clkop, fab, conv;",
     '    (* LOC="PLL_LRC" *)',
     "    PLL_CORE #({}) u_pll (.REFCK(clk), .CLKOP(clkop), .CLKOS(fab), .CLKOS4(conv), .FBKCK(clkop));".format(pll),
     "    reg [{}:0] s;".format(src - 1)]
v += body
v.append('    ADC #(.VREFASEL("EXTERNAL"), .VREFACFG("1P6_TO_1P8"), .VREFBSEL("EXTERNAL"), .VREFBCFG("1P6_TO_1P8"), '
         '.OMA("UNIPOLAR"), .OMB("UNIPOLAR"), .CLK_DIV("2")) u_adc ({});'.format(", ".join(conns)))
v.append("    always @(posedge fab) begin")
v.append("        s[0] <= d ^ s[{}];".format(src - 1))
for k in range(1, src):
    v.append("        s[{}] <= s[{}] ^ d;".format(k, k - 1))
v.append("    end")
v.append("    reg [{}:0] c; always @(posedge fab) c <= {{{}}};".format(sum(max(n, 1) for _, n in OUTS) - 1, ", ".join(reversed(cap))))
v.append("    assign q = ^c ^ ainp ^ ainn;")
v.append("endmodule")
open(base + ".v", "w").write("\n".join(v) + "\n")
pins = [("clk", "P24", "LVCMOS33"), ("d", "R5", "LVCMOS33"), ("q", "M9", "LVCMOS33")]
pdc = "".join("ldc_set_location -site {{{}}} [get_ports {}]\nldc_set_port -iobuf {{IO_TYPE={}}} [get_ports {}]\n".format(s, p, t, p) for p, s, t in pins)
pdc += "ldc_set_location -site {Y6} [get_ports ainp]\nldc_set_port -iobuf {IO_TYPE=LVSTL_I ENADC_IN=ENABLED} [get_ports ainp]\n"
pdc += "ldc_set_location -site {AA6} [get_ports ainn]\nldc_set_port -iobuf {IO_TYPE=LVSTL_I ENADC_IN=ENABLED} [get_ports ainn]\n"
open(base + ".pdc", "w").write(pdc)
