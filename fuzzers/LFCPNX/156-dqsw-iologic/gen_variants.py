"""
Generate the PHY variants used to find IOLOGIC<x>.MODDRXN.DQSW_CLK (see README.md).

Each variant is <out>/<name>/b/<name>.{v,pdc,sdc}, built with Radiant's CLI flow (radiant.sh:
LSE, map, par, bitgen -ipeval -d -w) and decoded with prjoxide unpack.

Usage: gen_variants.py <out dir>
"""
import os
import re
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "phy1.v")).read()
pdc = open(os.path.join(here, "phy1.pdc")).read()
sdc = open(os.path.join(here, "phy1.sdc")).read()

DM = '''ODDRX4DQ #(.GSR("DISABLED")) u_dm (.D0(r[50]),.D1(r[51]),.D2(r[52]),.D3(r[53]),.D4(r[54]),.D5(r[55]),.D6(r[56]),.D7(r[57]),
             .DQSW270(dqsw270), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(dm));'''
ODQ = '''ODDRX4DQ #(.GSR("DISABLED")) u_o (.D0(r[i]),.D1(r[i+1]),.D2(r[i+2]),.D3(r[i+3]),.D4(r[i+4]),.D5(r[i+5]),.D6(r[i+6]),.D7(r[i+7]),
             .DQSW270(dqsw270), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(o));'''
TDQ = '''TSHX4DQ #(.GSR("DISABLED")) u_t (.T0(r[i+8]),.T1(r[i+9]),.T2(r[i+10]),.T3(r[i+11]), .DQSW270(dqsw270), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(t));'''
for s in (DM, ODQ, TDQ):
    assert s in src
DQSO = re.search(r'ODDRX4DQS #\(\.GSR\("DISABLED"\)\) u_dqso \(.*?\.Q\(dqs_o\)\);', src, re.S)[0]


def loc(p, port, site):
    return re.sub(r'(ldc_set_location -site \{)[A-Z0-9]+(\} \[get_ports %s\])' % re.escape(port),
                  r'\g<1>%s\2' % site, p)


def lane(p, dqs, dm, dqs_sites):
    p = loc(loc(p, "dqs", dqs), "dm", dm)
    for i, s in enumerate(dqs_sites):
        p = loc(p, "{dq[%d]}" % i, s)
    return p


variants = {
    # gearing on the bank-3 byte lane of phy1 (DQS AF4/AF3)
    "phy1": (src, pdc),
    "g_notsh": (src.replace(TDQ, "assign t = r[i+8];"), pdc),
    "p_dm_plain": (src.replace(DM, DM.replace("ODDRX4DQ", "ODDRX4").replace(".DQSW270(dqsw270), ", "")), pdc),
    "p_dm_dqsw": (src.replace(DM, DM.replace("ODDRX4DQ", "ODDRX4DQS").replace(".DQSW270(dqsw270)", ".DQSW(dqsw)")), pdc),
    "p_dq_tshonly": (src.replace(ODQ, "assign o = r[i];"), pdc),
    "p_dqs_tshonly": (src.replace(DQSO, "assign dqs_o = r[24];"), pdc),
    # tile-type coverage: DM on the DQS complement pad (SYSIO_B3_1_DQS2), single-ended DQS
    "v_dm_af3": (src, loc(pdc, "dm", "AF3").replace("{IO_TYPE=HSUL12D} [get_ports dqs]",
                                                     "{IO_TYPE=HSUL12} [get_ports dqs]")),
    # channel B upper byte (SYSIO_B3_1_V18 at PB110B) and channel A upper byte (SYSIO_B3_1_ECLK_R)
    "v_chb_hi": (src, lane(pdc, "AF12", "AC12", ["AC11", "AD12", "AD11", "AE11", "AB12", "AA11", "Y11", "AA12"])),
    "v_cha_hi": (src, lane(pdc, "AF6", "AE5", ["AD6", "AE6", "AC7", "AB7", "AA7", "Y7", "AB6", "AC6"])),
}


def main():
    out = sys.argv[1]
    for name, (v, p) in variants.items():
        d = os.path.join(out, name, "b")
        os.makedirs(d, exist_ok=True)
        for ext, text in (("v", v), ("pdc", p), ("sdc", sdc)):
            with open(os.path.join(d, "{}.{}".format(name, ext)), "w") as f:
                f.write(text)
        print(name)


if __name__ == "__main__":
    main()
