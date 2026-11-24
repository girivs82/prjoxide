"""
Give SYSCONFIG.JTAG_PORT DISABLE its bit (see README.md).

On LFCPNX-100, JTAG_PORT lands in PMU: ENABLE = F38B0. F38B0 is also an always_on bit of PMU, set by
every design including the empty one, so JTAG is enabled by default. The fuzzer (assume_zero_base)
leaves DISABLE with no bits, and since the packer sets always_on bits before applying the FASM,
DISABLE could not clear it. This writes DISABLE as F38B0 cleared (inverted), and a description that
warns DISABLE locks JTAG out of the configured device. It first checks that ENABLE is exactly F38B0
and that F38B0 is always_on. Re-running is a no-op.

Usage: fix_jtag_port.py [database root]
"""
import os
import re
import sys

DESC = ("status of JTAG port after configuration. ENABLE (F38B0, also always_on) is the default: every "
        "bitstream has it. WARNING: DISABLE clears F38B0 and locks JTAG out of the configured device; never "
        "set it unless that is intended")
root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")


def main():
    fn = os.path.join(root, "LFCPNX", "tiletypes", "PMU.ron")
    t = open(fn).read()
    i = t.index('    "SYSCONFIG.JTAG_PORT": (\n')
    j = t.index("\n    ),\n", i)
    body = t[i:j]
    if '"ENABLE": [(frame:38,bit:0,invert:false,),]' not in body:
        raise SystemExit("JTAG_PORT ENABLE is not exactly F38B0")
    aon = t[t.index("  always_on: ["):]
    if not re.search(r'frame: 38,\s*bit: 0,\s*invert: false', aon):
        raise SystemExit("F38B0 is not an always_on bit of PMU")
    new = body.replace('"DISABLE": [],', '"DISABLE": [(frame:38,bit:0,invert:true,),],')
    new = re.sub(r'desc: "[^"]*"', 'desc: "%s"' % DESC, new)
    if new == body:
        print("JTAG_PORT DISABLE present")
        return
    open(fn, "w").write(t[:i] + new + t[j:])
    print("JTAG_PORT DISABLE = F38B0 cleared, with the lock-out warning")


if __name__ == "__main__":
    main()
