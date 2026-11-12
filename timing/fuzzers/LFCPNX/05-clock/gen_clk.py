import random

# LFG672: the PCLKT (primary clock) pins, from par's .pad report (bank 0's are configuration
# dual-function pins and are left out)
clk_pins = "R4 R6 R8 T1 U2 U6 AB11 AB4 AC12 Y5 AA13 AB19 AD21 AE13 AC21 AD25 V23 W24 P22 P24 R20 M26 N23 N25".split(" ")
banks = "1 1 1 2 2 2 3 3 3 3 4 4 4 4 5 5 5 5 6 6 6 7 7 7".split(" ")
plls = ["PLL_LLC", "PLL_LRC", "PLL_ULC", "PLL_URC"]

pll_pins = ["CLKOP", "CLKOS", "CLKOS2", "CLKOS3", "CLKOS4", "CLKOS5"]

# Twelve edge clock dividers, left for Radiant to place (no LFCPNX site names are known here)
eclkdiv = ["ECLKDIV_{}".format(i) for i in range(12)]

central_dcc = [
    "DCC_C0",
    "DCC_C1",
    "DCC_C2",
    "DCC_C3",
]

central_dcs = [
    "DCS0",
]

N = 20

print("module top(")
for pin, bank in zip(clk_pins, banks):
    print('    (* LOC="{p}", IO_TYPE="{t}" *) input pin_{p},'.format(p=pin, t=("LVCMOS18H" if bank in ("3", "4", "5") else "LVCMOS33")))
for pll in plls:
    print('    input pllin_{},'.format(pll))
print("    input d,")
print("    output q")
print(");")

print("    reg [{}:0] r;".format(N+4))
print("    always @* r[0] = d;")
print("    assign q = r[{}];".format(N))

print("    wire [3:0] ctrl = r[24:21];")


clock_sources = []
for pin in clk_pins:
    clock_sources.append(("pin", pin))
for pll in plls:
    for pll_pin in pll_pins:
        clock_sources.append(("pll", (pll, pll_pin)))
for div in eclkdiv:
    clock_sources.append(("eclkdiv", div))
for dcc in central_dcc:
    clock_sources.append(("dcc", dcc))
for dcs in central_dcs:
    clock_sources.append(("dcs", dcs))

random.shuffle(clock_sources)

for i in range(18, 20):
    if clock_sources[i][0] == "dcs":
        clock_sources[i], clock_sources[17] = clock_sources[17], clock_sources[i]

used_plls = set()

j = 0
clkwire_final = None

def get_source():
    global j
    global clkwire_final
    if j == N:
        return clkwire_final
    srctype, src = clock_sources.pop()
    clkwire = None
    if srctype == "pin":
        clkwire = "pin_{}".format(src)
    elif srctype == "pll":
        used_plls.add(src[0])
        clkwire = "{}_{}".format(src[0], src[1])
    elif srctype == "eclkdiv":
        print('    wire eclkdivo_{};'.format(src))
        # LFCPNX's map requires an edge clock divider's input to come from an ECLKSYNC
        # (ERROR 52281052)
        print('    wire eclks_{};'.format(src))
        print('    ECLKSYNC esync_{s} (.ECLKIN(r[{r}]), .STOP(1\'b0), .ECLKOUT(eclks_{s}));'.format(s=src, r=j + 1))
        print('    ECLKDIV_CORE #(')
        print('        .ECLK_DIV("{}")'.format(random.choice(["DISABLE", "2", "3P5", "4", "5"])))
        print('    ) div_{} ('.format(src))
        print('         .ECLKIN(eclks_{}),'.format(src))
        print('         .SLIP(ctrl[1]),')
        print('         .DIVRST(ctrl[2]),')
        print('         .DIVOUT(eclkdivo_{})'.format(src))
        print('    );')
        clkwire = "eclkdivo_{}".format(src)
    elif srctype == "dcc":
        print('    wire dcco_{};'.format(src))
        print('    (* LOC="{}" *)'.format(src))
        print('    DCC cdcc_{d} (.CLKI(r[{r}]), .CE(ctrl[1]), .CLKO(dcco_{d}));'.format(r=j+1, d=src))
        clkwire = "dcco_{}".format(src)
    elif srctype == "dcs":
        print('    wire dcso;')
        clka = get_source()
        clkb = get_source()

        print('   DCS dcs_{} ('.format(src))
        print('       .CLK0({}),'.format(clka))
        print('       .CLK1({}),'.format(clkb))
        print('       .SEL(ctrl[0]),')
        print('       .SELFORCE(ctrl[1]),')
        print('       .DCSOUT(dcso)')
        print('   );')

        clkwire = "dcso"

    if srctype not in ("dcc", "dcs") and random.randint(0, 1) == 1:
        dccwire = "gclk_{}".format(j)
        print('    wire {};'.format(dccwire))
        print('    DCC #(.DCCEN("1")) dcc_{i} (.CLKI({clki}), .CE(ctrl[{ctrl}]), .CLKO({clko}));'.format(
            i=j, clki=clkwire, ctrl=random.randint(0, 3), clko=dccwire
        ))
        clkwire = dccwire
    j += 1
    if j == N:
        clkwire_final = clkwire
    return clkwire

last_clkwire = None
for i in range(N):
    clkwire = get_source()
    print('    always @(posedge {clk}) r[{i} + 1] <= r[{i}];'.format(clk=clkwire, i=i))
    last_clkwire = clkwire

print('    always @(posedge {clk}) r[21] <= r[20];'.format(clk=last_clkwire))
print('    always @(posedge {clk}) r[22] <= r[21];'.format(clk=last_clkwire))
print('    always @(posedge {clk}) r[23] <= r[22];'.format(clk=last_clkwire))
print('    always @(posedge {clk}) r[24] <= r[23];'.format(clk=last_clkwire))

for pll in used_plls:
    print("")
    for sig in pll_pins:
        print('    wire {}_{};'.format(pll, sig))
    print('    (* LOC="{}" *)'.format(pll))
    print('    PLL_CORE pll_{} ('.format(pll))
    print('        .REFCK(pllin_{}),'.format(pll))
    for sig in pll_pins:
           print('        .{}({}_{}),'.format(sig, pll, sig))
    print('        .FBKCK({}_CLKOP)'.format(pll))
    print('    );')
print('endmodule')
