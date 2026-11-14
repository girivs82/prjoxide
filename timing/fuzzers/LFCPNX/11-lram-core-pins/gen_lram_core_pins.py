# LFCPNX: all seven LRAMs as bare LRAM_CORE primitives, so that the pins the DPSC512K/PDPSC512K/
# SP512K wrappers tie off (DPS, IGN, INITN, STDBYN, TBISTN, SCANRST, SCANCLK, OPCGLOADCLK) and
# the outputs they leave open (OEA, OEB, ERRDET, LRAMREADY) are connected too. Every input pin
# is driven by its own fabric register and every output is captured by its own register, so each
# pin's SDF arc starts or ends at a register whose route is traceable (10-lram-pins does the same
# for the wrapper pins). Only LRAM_CORE's public parameters are set, at random.
import random

INS = [("ADA", 14), ("ADB", 14), ("BENA_N", 4), ("BENB_N", 4), ("DIA", 32), ("DIB", 32),
       ("CEA", 0), ("CEB", 0), ("CSA", 0), ("CSB", 0), ("WEA", 0), ("WEB", 0), ("OCEA", 0),
       ("OCEB", 0), ("RSTA", 0), ("RSTB", 0),
       # the pins this fuzzer is for
       ("DPS", 0), ("IGN", 0), ("INITN", 0), ("STDBYN", 0), ("TBISTN", 0), ("SCANRST", 0),
       ("SCANCLK", 0), ("OPCGLOADCLK", 0)]
OUTS = [("DOA", 32), ("DOB", 32), ("ERRDECA", 2), ("ERRDECB", 2),
        ("ERRDET", 0), ("LRAMREADY", 0), ("OEA", 0), ("OEB", 0)]


def pins(name, n):
    # n == 0: a scalar pin; otherwise LRAM_CORE's bit-numbered pins name0..name<n-1>
    return [name] if n == 0 else ["{}{}".format(name, b) for b in range(n)]


print("module top(input clk, input [7:0] d, output q);")
src = 0      # input source registers
cap = []     # output capture registers
body = []
for i in range(7):
    conns = [".CLK(clk)"]
    for name, n in INS:
        for p in pins(name, n):
            conns.append(".{}(s[{}])".format(p, src))
            src += 1
    for name, n in OUTS:
        for p in pins(name, n):
            w = "o{}_{}".format(i, p)
            body.append("    wire {};".format(w))
            conns.append(".{}({})".format(p, w))
            cap.append(w)
    params = [
        '.ECC_BYTE_SEL("{}")'.format(random.choice(["ECC_EN", "BYTE_EN"])),
        '.OUT_REGMODE_A("{}")'.format(random.choice(["NO_REG", "OUT_REG"])),
        '.OUT_REGMODE_B("{}")'.format(random.choice(["NO_REG", "OUT_REG"])),
        '.RESETMODE("{}")'.format(random.choice(["SYNC", "ASYNC"])),
        '.GSR("DISABLED")',
    ]
    body.append("    LRAM_CORE #({}) lram_{} ({});".format(", ".join(params), i, ", ".join(conns)))
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
