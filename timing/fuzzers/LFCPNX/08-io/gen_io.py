import random

# Some representative pins for each bank (LFCPNX-100, LFG672): ten user IO pins per bank, picked
# at random from those par placed in LSE builds (banks 3-5 are the 1.8V HP banks; there only
# A pads, all of which take differential types, so the B pad of a differential pair stays free)

bank_pins = {
    0: ("G7", "H2", "H3", "H4", "H7", "J1", "J6", "K2", "K3", "K5"),
    1: ("L2", "M4", "M9", "N4", "N5", "N7", "R6", "R7", "T6", "U8"),
    2: ("T3", "U2", "U7", "V1", "V2", "V7", "W1", "W4", "W5", "Y4"),
    3: ("AA12", "AB6", "AB9", "AC12", "AC7", "AD10", "AD3", "W11", "Y5", "Y6"),
    4: ("AA13", "AA17", "AC18", "AD14", "AE22", "AF15", "AF19", "AF22", "Y12", "Y18"),
    5: ("AA23", "AB23", "AC21", "AC25", "AC26", "AD25", "U26", "V24", "W24", "W25"),
    6: ("P24", "P25", "P26", "R18", "R21", "T22", "U19", "V18", "V19", "V20"),
    7: ("J19", "J20", "J21", "J22", "J24", "K26", "L23", "N22", "N23", "N26"),
}

io33_types = [
    ("LVCMOS12", 1.2, None),
    ("LVCMOS15", 1.5, None),
    ("LVCMOS18", 1.8, None),
    ("LVCMOS25", 2.5, None),
    ("LVCMOS33", 3.3, None),
]

# LFCPNX: only the standards that par places together in one HP bank without VREF or other
# banking conflicts (the referenced SSTL/HSTL/HSUL types and SLVS are rejected with
# ERROR 61211145 when mixed as gen_io mixes them; LVCMOS10R and SUBLVDS likewise)
io18_types = [
    ("LVCMOS18H", 1.8, None),
    ("LVCMOS15H", 1.5, None),
    ("LVCMOS12H", 1.2, None),
    ("LVCMOS10H", 1.0, None),
    ("LVDS", 1.8, None),
]

io33_vcc = [3.3, 2.5, 1.8, 1.5, 1.2]
io18_vcc = [1.8, 1.5, 1.2, 1.0]

slew_settings = ["SLOW", "MED", "FAST"]

drive_settings = {
    "LVCMOS33": ["2", "4", "8", "12"],
    "LVCMOS25": ["2", "4", "8", "10"],
    "LVCMOS18": ["2", "4", "8"],
    "LVCMOS15": ["2", "4"],
    "LVCMOS12": ["2", "4"],
    "LVCMOS18H": ["2", "4", "8", "12"],
    "LVCMOS15H": ["2", "4", "8"],
    "LVCMOS12H": ["2", "4", "8"],
    "LVSMOS10H": ["2", "4"],
    "HSUL12": ["4", "8"],
}

diff_types = ("LVDS", "SUBLVDS", "SUBLVDSEH", "SLVS", "MIPI_DPHY", "SSTL15D_I", "SSTL15D_II", "SSTL135D_I", "SSTL135D_II", "HSTL15D_I", "HSUL12D")

def main():
    # Pick a random Vcc for each bank
    bank_vcc = {}
    for bank in sorted(bank_pins.keys()):
        if bank in (3, 4, 5):
            bank_vcc[bank] = random.choice(io18_vcc)
        else:
            bank_vcc[bank] = random.choice(io33_vcc)
    # Pick settings for each pin
    pin_settings = {}
    pin2bank = {}

    def get_iotype(bank, force_output=False):
        while True:
            iotype, vcc, iodirs = random.choice(io18_types if bank in (3, 4, 5) else io33_types)
            if force_output and iodirs is not None and "OUTPUT" not in iodirs:
                continue
            if vcc == bank_vcc[bank]:
                return (iotype, vcc, iodirs) 

    for bank, pins in sorted(bank_pins.items()):
        for pin in pins:
            pin2bank[pin] = bank
            # Pick a compatible type
            iotype, vcc, iodirs = get_iotype(bank)
            # Pick a compatible direction
            iodir = random.choice(iodirs if iodirs is not None else ["INPUT", "OUTPUT", "INOUT"])
            # Pick extra settings (drive and slew rate)
            extra_cfg = []
            if iodir in ("OUTPUT", "INOUT"):
                if iotype in drive_settings:
                    extra_cfg.append(("DRIVE", random.choice(drive_settings[iotype])))
                if iotype in diff_types:
                    pass
                elif "SSTL" in iotype or "HSUL" in iotype or "HSTL" in iotype:
                    extra_cfg.append(("SLEWRATE", random.choice(slew_settings[1:])))
                else:
                    extra_cfg.append(("SLEWRATE", random.choice(slew_settings)))
            pin_settings[pin] = (iotype, iodir, extra_cfg)
    io_names = {}
    print("module top (")
    for pin, setting in sorted(pin_settings.items()):
        # Encode config in pin name so we can parse it later on
        io_name = "{}__{}__{}{}".format(
            pin, setting[0], setting[1], "".join("__{}_{}".format(k, v) for k, v in setting[2])
        )
        print('    (* LOC="{}", IO_TYPE="{}"{} *)'.format(
            pin, setting[0], "".join(', {}="{}"'.format(k, v) for k, v in setting[2])
        ))
        print('    {} {},'.format(setting[1].lower(), io_name))
        io_names[pin] = io_name
    print('    (* IO_TYPE="{}" *) input [6:0] d,'.format(get_iotype(6)[0]))
    print('    (* IO_TYPE="{}" *) input sclk,'.format(get_iotype(2)[0]))
    for b in (3, 4, 5):
        print('    (* IO_TYPE="{}" *) input eclk{},'.format(get_iotype(b)[0], b))
    print('    (* IO_TYPE="{}" *) output q'.format(get_iotype(2, force_output=True)[0]))
    print(");")

    output_count = 0

    def i():
        return "d[{}]".format(random.randint(0, 3))
    def o():
        nonlocal output_count
        sig = "o[{}]".format(output_count)
        output_count += 1
        return sig

    # Edge clock dividers
    print("    wire sclk3, sclk4, sclk5;")
    bank_rates = {}
    for bank in (3, 4, 5):
        # TODO: 3.5
        rate = random.choice([2, 4, 5])
        bank_rates[bank] = rate
        # LFCPNX's map requires DDR edge clocks to come from an ECLKSYNC (ERROR 52281052)
        print('    wire eclks{};'.format(bank))
        print('    ECLKSYNC esync_{b} (.ECLKIN(eclk{b}), .STOP(1\'b0), .ECLKOUT(eclks{b}));'.format(b=bank))
        print('    ECLKDIV_CORE #(')
        print('        .ECLK_DIV("{}")'.format(rate))
        print('    ) ediv_{} ('.format(bank))
        print('         .ECLKIN(eclks{}),'.format(bank))
        print('         .DIVOUT(sclk{})'.format(bank))
        print('    );')

    # IO buffer, delay and IOLOGIC
    for pin, setting in sorted(pin_settings.items()):
        sig_i = "{}_i".format(pin)
        sig_t = "{}_t".format(pin)
        sig_o = "{}_o".format(pin)
        iotye, d, extra_args = setting
        print("    wire {};".format(", ".join((sig_i, sig_o, sig_t))))

        bank = pin2bank[pin]
        # Encode in name for the IOLOGIC cell timing fuzzer
        iobt = "__IOB_" if bank in (3, 4, 5) else "_S_IOB"

        # IO buffer
        if d == "INPUT":
            print("    IB {p}{s}_b (.I({n}), .O({p}_o));".format(p=pin, s=iobt, n=io_names[pin]))
            sig_t = None
            sig_i = None
        elif d == "OUTPUT":
            print("    OB {p}{s}_b (.O({n}), .I({p}_i));".format(p=pin, s=iobt, n=io_names[pin]))
            sig_o = None
        elif d == "INOUT":
            print("    BB {p}{s}_b (.B({n}), .I({p}_i), .T({p}_t), .O({p}_o));".format(p=pin, s=iobt, n=io_names[pin]))

        # Delay
        def delaya_common():
            print("         .LOAD_N(!d[4]),")
            print("         .MOVE(!d[5]),")
            print("         .DIRECTION(!d[6]),")
            print("         .CFLAG({}),".format(o()))

        od_used = False

        if d in ("INPUT", "INOUT") and random.random() < 0.15:
            print("    wire {}_od;".format(pin))
            if pin2bank[pin] in (3, 4, 5):
                print("    DELAYA {}_del (".format(pin))
                print("         .A({}_o),".format(pin))
                delaya_common()
                print("         .Z({}_od)".format(pin))
                print("    );")
            else:
                print("    DELAYB {}_del (".format(pin))
                print("         .A({}_o),".format(pin))
                print("         .Z({}_od)".format(pin))
                print("    );")
            sig_o = "{}_od".format(pin)
        elif d in ("OUTPUT", "INOUT") and random.random() < 0.15:
            od_used = True
            print("    wire {}_id;".format(pin))
            if pin2bank[pin] in (3, 4, 5):
                print("    DELAYA {}_del (".format(pin))
                print("         .A({}_id),".format(pin))
                delaya_common()
                print("         .Z({}_i)".format(pin))
                print("    );")
            else:
                print("    DELAYB {}_del (".format(pin))
                print("         .A({}_id),".format(pin))
                print("         .Z({}_i)".format(pin))
                print("    );")
            sig_i = "{}_id".format(pin)

        # IOLOGIC
        rate = bank_rates.get(bank, 0)
        iol_types = []
        # LFCPNX: par cannot meet the GDDR delay rule for IDDRX1/ODDRX1 on the top-edge bank 0
        # pins (ERROR 61213332), so bank 0 gets registers only
        gddr = bank != 0
        if d in ("INPUT", "INOUT"):
            iol_types.append("IREG")
            if gddr: iol_types.append("IDDR")
        if d in ("INOUT", "OUTPUT"):
            iol_types.append("OREG")
            if gddr: iol_types.append("ODDR")
        if d == "INPUT" and rate != 0: iol_types.append("IDDRN")
        if d == "OUTPUT" and rate != 0: iol_types.append("ODDRN")

        if random.random() > 0.5:
            iol = random.choice(iol_types)
            if iol == "IREG":
                print("    {prim} {p}_ireg (.CK(sclk), .D({io_o}), .SP({sp}), .CD({cd}), .Q({q}));".format(
                    prim=random.choice(["IFD1P3DX", "IFD1P3IX"]),
                    p=pin, io_o=sig_o, sp=i(), cd=i(), q=o(),
                ))
                sig_o = None
            elif iol == "OREG":
                prim = random.choice(["OFD1P3DX", "OFD1P3IX"])
                sp = i()
                cd = i()
                print("    {prim} {p}_oreg (.CK(sclk), .D({d}), .SP({sp}), .CD({cd}), .Q({io_i}));".format(
                    prim=prim, p=pin, d=i(), sp=sp, cd=cd, io_i=sig_i,
                ))
                sig_i = None
                if sig_t is not None and random.random() > 0.5:
                    print("    {prim} {p}_treg (.CK(sclk), .D({t}), .SP({sp}), .CD({cd}), .Q({io_t}));".format(
                        prim=prim, p=pin, t=i(), sp=sp, cd=cd, io_t=sig_t,
                    ))
                    sig_t = None
            elif iol == "IDDR":
                print("    IDDRX1 {p}_iddr (.SCLK(sclk), .D({io_o}), .RST({rst}), .Q0({q0}), .Q1({q1}));".format(
                    p=pin, io_o=sig_o, rst=i(), q0=o(), q1=o(),
                ))
                sig_o=None
            elif iol == "ODDR":
                print("    ODDRX1 {p}_oddr (.SCLK(sclk), .D0({d0}), .D1({d1}), .RST({rst}), .Q({io_i}));".format(
                    p=pin, d0=i(), d1=i(), rst=i(), io_i=sig_i,
                ))
                sig_i=None
            elif iol == "IDDRN":
                print("    IDDRX{n} {p}_iddr (.SCLK(sclk{b}), .ECLK(eclks{b}), .D({io_o}), .RST({rst}), .ALIGNWD({aw}), {q});".format(
                    n=rate, p=pin, b=bank, io_o=sig_o, rst=i(), aw=i(),
                    q=", ".join(".Q{}({})".format(j, o()) for j in range(2*rate))
                ))
                sig_o=None
            elif iol == "ODDRN":
                print("    ODDRX{n} {p}_iddr (.SCLK(sclk{b}), .ECLK(eclks{b}), .Q({io_i}), .RST({rst}), {d});".format(
                    n=rate, p=pin, b=bank, io_i=sig_i, rst=i(),
                    d=", ".join(".D{}({})".format(j, i()) for j in range(2*rate))
                ))
                sig_i=None
            else:
                assert False
        if sig_i is not None:
            print("    assign {} = {}{};".format(sig_i, "!" if od_used else "", i()))
        if sig_t is not None:
            print("    assign {} = {};".format(sig_t, i()))
        if sig_o is not None:
            print("    assign {} = {};".format(o(), sig_o))
        print()

    print("    wire [{}:0] o;".format(output_count-1))
    print("    assign q = ^o;")
    print("endmodule")

if __name__ == '__main__':
    main()
