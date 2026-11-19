# LFCPNX: many EBRs, with every input pin driven by its own fabric register and every output captured
# by its own register, so that each EBR pin's SDF arc starts or ends at a register whose route is
# traceable (tools/radiant-fuzz/infer_ebr_conns.py). Per instance, the primitive is chosen at random
# among DP16K (both ports x18: DIA/DIB, DOA/DOB, ADA/ADB, CSA/CSB, CEA/CEB, WEA/WEB, RSTA/RSTB) and
# PDP16K / PDPSC16K (x36: DI0-17 on DIA, DI18-35 on DIB, DO split over DOA / DOB); the clocks are
# the one clock input (EBR clock pins come from the global network, not a CIB wire).
import os
import random

N = int(os.environ.get("N_EBR", "48"))
PRIMS = {
    "DP16K": dict(params='.DATA_WIDTH_A("X18"), .DATA_WIDTH_B("X18")', clk=["CLKA", "CLKB"],
                  ins=[("CEA", 1), ("CEB", 1), ("WEA", 1), ("WEB", 1), ("RSTA", 1), ("RSTB", 1),
                       ("CSA", 3), ("CSB", 3), ("ADA", 14), ("ADB", 14), ("DIA", 18), ("DIB", 18)],
                  outs=[("DOA", 18), ("DOB", 18)]),
    "PDP16K": dict(params='.DATA_WIDTH_W("X36"), .DATA_WIDTH_R("X36")', clk=["CLKW", "CLKR"],
                   ins=[("CEW", 1), ("CER", 1), ("RST", 1), ("CSW", 3), ("CSR", 3), ("ADW", 14), ("ADR", 14),
                        ("DI", 36)],
                   outs=[("DO", 36)]),
    "PDPSC16K": dict(params='.DATA_WIDTH_W("X36"), .DATA_WIDTH_R("X36")', clk=["CLK"],
                     ins=[("CEW", 1), ("CER", 1), ("RST", 1), ("CSW", 3), ("CSR", 3), ("ADW", 14), ("ADR", 14),
                          ("DI", 36)],
                     outs=[("DO", 36)]),
}

print("module top(input clk, input [7:0] d, output q);")
src = 0
cap = []
body = []
for i in range(N):
    prim = random.choice(["DP16K", "DP16K", "PDP16K", "PDPSC16K"])
    p = PRIMS[prim]
    conns = [".{}(clk)".format(c) for c in p["clk"]]
    for name, n in p["ins"]:
        bits = []
        for b in range(n):
            bits.append("s[{}]".format(src))
            src += 1
        conns.append(".{}({{{}}})".format(name, ", ".join(reversed(bits))))
    for name, n in p["outs"]:
        body.append("    wire [{}:0] o{}_{};".format(n - 1, i, name))
        conns.append(".{}(o{}_{})".format(name, i, name))
        cap += ["o{}_{}[{}]".format(i, name, b) for b in range(n)]
    body.append("    {} #({}) ram_{} ({});".format(prim, p["params"], i, ", ".join(conns)))
print("    reg [{}:0] s;".format(src - 1))
print("    reg [{}:0] c;".format(len(cap) - 1))
print("    always @(posedge clk) begin")
print("        s[0] <= d[0] ^ s[{}];".format(src - 1))
for k in range(1, src):
    print("        s[{}] <= s[{}] ^ d[{}];".format(k, k - 1, random.randint(0, 7)))
print("    end")
print("\n".join(body))
print("    always @(posedge clk) c <= {{{}}};".format(", ".join(reversed(cap))))
print("    assign q = ^c;")
print("endmodule")
