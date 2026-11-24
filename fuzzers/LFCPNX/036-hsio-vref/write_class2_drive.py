"""
Write the class-II output drive code of SSTL15_II / SSTL135_II into the bank 3 / 4 / 5 SYSIO tile
types (see README.md, "SSTL15_II / SSTL135_II drive"):

- option "10" of PIO<x>.SEIO18.DRIVE_1V5;
- a new enum PIO<x>.SEIO18.DRIVE_1V35 with the same option.

Radiant accepts only DRIVE=10 for these IO types ("change DRIVE to 10") and sets it in its
synthesized flow; a structural build of BASE_TYPE OUTPUT_SSTL15_II / OUTPUT_SSTL135_II leaves the
drive code at 0. Seen on a pad of every one of these 33 tile types (gen_class2.py designs, one per IO
type), the same in each:
- PIOA (first-tile types SYSIO_B<k>_0*): F12B1 + F13B1 of the drive code F9B1-F13B1;
- PIOB (second-tile types SYSIO_B<k>_1*): F89B0 + F90B0 of the drive code F89B0-F93B0. F89B0 alone
  is also set with PIOB unused, so only F90B0 showed as unknown; that both are set (and F91B0-F93B0
  clear) was read by decoding with each candidate. It matches PIOA bit for bit, by the correspondence
  of the existing 2 / 4 / 8 options (F13B1 - F89B0, F12B1 - F90B0, F10B1 - F92B0, F9B1 / F11B1 -
  F91B0 / F93B0).

The option lists all five bits of the code (set and clear), like the enum's other options, so it
only decodes when the whole code matches. Before writing, the existing DRIVE_1V5 enum of each tile
type is checked to use exactly those five bits. Only options and an enum are added, so FASM that
packed before packs to the same bitstream. Re-running is a no-op.

Usage: write_class2_drive.py [database root]
"""
import os
import re
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                            "..", "..", "..", "database")
# PIO -> (the drive code bits as (frame, bit), the ones set for DRIVE=10)
CODE = {
    "PIOA": ([(9, 1), (10, 1), (11, 1), (12, 1), (13, 1)], {(12, 1), (13, 1)}),
    "PIOB": ([(89, 0), (90, 0), (91, 0), (92, 0), (93, 0)], {(89, 0), (90, 0)}),
}
# the description describe.py gives every DRIVE_<v> enum (so re-running it changes nothing)
DESC_1V35 = ("drive strength for 1.35 V IO types. DRIVE_<v> enums share bits; the decoder keeps only the "
             "one for the BASE_TYPE of the PIO")


def tiletypes():
    d = os.path.join(root, "LFCPNX", "tiletypes")
    return sorted(f[:-4] for f in os.listdir(d) if re.match(r'SYSIO_B[345]_[01]', f) and f.endswith(".ron"))


def option_block(bits, on):
    return "[" + "".join("(frame:%d,bit:%d,invert:%s,)," % (f, b, "false" if (f, b) in on else "true")
                         for f, b in bits) + "]"


def enum_span(t, name):
    i = t.index('    "%s": (\n' % name)
    return i, t.index("\n    ),\n", i) + len("\n    ),\n")


def check_layout(t, name, bits):
    i, j = enum_span(t, name)
    used = set((int(f), int(b)) for f, b in re.findall(r'frame:(\d+),bit:(\d+)', t[i:j]))
    if used != set(bits):
        raise SystemExit("{}: bits {} are not the expected drive code {}".format(name, sorted(used), bits))


def add_option(t, name, opt, block):
    i, j = enum_span(t, name)
    body = t[i:j]
    if '        "%s": [' % opt in body:
        return t, False
    o = body.index("      options: {\n") + len("      options: {\n")
    e = body.index("      },\n", o)
    lines = body[o:e].splitlines(keepends=True)
    lines.append('        "%s": %s,\n' % (opt, block))
    lines.sort(key=lambda l: re.match(r'        "([^"]+)"', l).group(1))
    return t[:i] + body[:o] + "".join(lines) + body[e:] + t[j:], True


def add_enum(t, name, opt, block, desc):
    if '    "%s": (\n' % name in t:
        return t, False
    i = t.index("  enums: {\n") + len("  enums: {\n")
    end = t.index("\n  },\n", i)
    body = t[i:end]
    pos = len(body) + 1
    for m in re.finditer(r'^    "([^"]+)": \(', body, re.M):
        if m[1] > name:
            pos = m.start()
            break
    new = '    "%s": (\n      options: {\n        "%s": %s,\n      },\n      desc: "%s",\n    ),\n' % (
        name, opt, block, desc)
    body = body[:pos] + new + body[pos:] if pos <= len(body) else body + "\n" + new.rstrip("\n")
    return t[:i] + body + t[end:], True


def main():
    for tt in tiletypes():
        pio = "PIOA" if re.match(r'SYSIO_B\d_0', tt) else "PIOB"
        bits, on = CODE[pio]
        fn = os.path.join(root, "LFCPNX", "tiletypes", tt + ".ron")
        t = open(fn).read()
        check_layout(t, pio + ".SEIO18.DRIVE_1V5", bits)
        block = option_block(bits, on)
        t, a = add_option(t, pio + ".SEIO18.DRIVE_1V5", "10", block)
        t, b = add_enum(t, pio + ".SEIO18.DRIVE_1V35", "10", block, DESC_1V35)
        if a or b:
            open(fn, "w").write(t)
        print(tt, pio, "DRIVE_1V5.10", "added" if a else "present", "DRIVE_1V35.10", "added" if b else "present")


if __name__ == "__main__":
    main()
