# LFCPNX: all seven LRAMs (every LRAM site is used), with every input pin driven by its own fabric
# register and every output captured by its own register, so that each LRAM pin's SDF arc starts
# or ends at a register whose route is traceable. (09-lram chains the LRAMs, output to input; an
# LRAM output's route start is what is being inferred, so those arcs say nothing about the
# connections of the pins they drive.) The port mode of each LRAM is chosen at random.
import random

PRIMS = {
    "DPSC512K": dict(
        clk=["CLK"],
        ins=[("CEA", 1), ("CEB", 1), ("WEA", 1), ("WEB", 1), ("CSA", 1), ("CSB", 1), ("CEOUTA", 1),
             ("CEOUTB", 1), ("RSTA", 1), ("RSTB", 1), ("BENA_N", 4), ("BENB_N", 4), ("ADA", 14), ("ADB", 14),
             ("DIA", 32), ("DIB", 32)],
        outs=[("DOA", 32), ("DOB", 32), ("ERRDECA", 2), ("ERRDECB", 2)]),
    "PDPSC512K": dict(
        clk=["CLK"],
        ins=[("CEW", 1), ("CER", 1), ("WE", 1), ("CSW", 1), ("CSR", 1), ("RSTR", 1), ("BYTEEN_N", 4),
             ("ADW", 14), ("ADR", 14), ("DI", 32)],
        outs=[("DO", 32), ("ERRDECA", 2), ("ERRDECB", 2)]),
    "SP512K": dict(
        clk=["CLK"],
        ins=[("CE", 1), ("WE", 1), ("CS", 1), ("CEOUT", 1), ("RSTOUT", 1), ("BYTEEN_N", 4), ("AD", 14),
             ("DI", 32)],
        outs=[("DO", 32), ("ERRDECA", 2), ("ERRDECB", 2)]),
}

print("module top(input clk, input [7:0] d, output q);")
src = 0      # input source registers
cap = []     # output capture registers
body = []
for i in range(7):
    # mostly the dual-port mode, which has the most pins
    prim = random.choice(["DPSC512K", "DPSC512K", "PDPSC512K", "SP512K"])
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
    body.append("    {} lram_{} ({});".format(prim, i, ", ".join(conns)))
print("    reg [{}:0] s;".format(src - 1))
print("    reg [{}:0] c;".format(len(cap) - 1))
# a chain through the source registers, each XORed with an input (no plain shift register, which
# synthesis could map to a memory)
print("    always @(posedge clk) begin")
print("        s[0] <= d[0] ^ s[{}];".format(src - 1))
for k in range(1, src):
    print("        s[{}] <= s[{}] ^ d[{}];".format(k, k - 1, random.randint(0, 7)))
print("    end")
print("\n".join(body))
print("    always @(posedge clk) c <= {{{}}};".format(", ".join(reversed(cap))))
print("    assign q = ^c;")
print("endmodule")
