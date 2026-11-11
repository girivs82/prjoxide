"""
Cheap alternative to the full 20k-build EBR_INIT word fuzz.

Hypothesis: LFCPNX EBR init uses the same IP layout as LIFCL (EBR_INIT.ron).
Copy database/LIFCL/iptypes/EBR_INIT.ron to database/LFCPNX/iptypes/ first,
run 100-ip-base so EBR_WID0/1 exist, then run this. For N random INITVAL
patterns it builds the design with Radiant and packs the same settings with
prjoxide, and compares the IP bytes inside the EBR_WID0 region.
All match -> the copy is right. Any mismatch -> run fuzzer.py (full fuzz).
"""
import fuzzconfig
import database
import libpyprjoxide
import json, random, subprocess, sys
from os import path

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8
cfg = fuzzconfig.FuzzConfig(job="EBRINITCHECK", device="LFCPNX-100", sv="ebr.v", tiles=[])

def ip_bytes(bitfile, lo, hi):
    chip = libpyprjoxide.Chip.from_bitstream(fuzzconfig.db, bitfile)
    return {a: d for a, d in chip.get_ip_values() if lo <= a < hi}

def main():
    cfg.setup(skip_specimen=True)
    regions = json.load(open(path.join(database.get_db_root(), "LFCPNX", cfg.device, "baseaddr.json")))["regions"]
    lo = regions["EBR_WID0"]["addr"]; hi = lo + (1 << regions["EBR_WID0"]["abits"])
    rng = random.Random(1234)
    bad = 0
    for i in range(N):
        word = rng.randrange(0x40)
        val = rng.getrandbits(320)
        bit = cfg.build_design(cfg.sv, dict(a="{:02X}".format(word), v="0x{:080x}".format(val)), prefix="r{}_".format(i))
        fasm = path.join(cfg.workdir, "r{}_expect.fasm".format(i))
        with open(fasm, "w") as f:
            print('{{ oxide.device="{}" }}'.format(cfg.device), file=f)
            print("IP_EBR_WID0.INITVAL_{:02X}[319:0] = 320'h{:080x};".format(word, val), file=f)
        exp_bit = fasm.replace(".fasm", ".bit")
        subprocess.check_call(["prjoxide", "pack", fasm, exp_bit])
        got, exp = ip_bytes(bit, lo, hi), ip_bytes(exp_bit, lo, hi)
        # Radiant writes zero bytes explicitly; compare non-zero content
        got = {a: d for a, d in got.items() if d}; exp = {a: d for a, d in exp.items() if d}
        ok = got == exp
        bad += not ok
        print("pattern {} INITVAL_{:02X}: {}".format(i, word, "MATCH" if ok else "MISMATCH"))
        if not ok:
            for a in sorted(set(got) | set(exp)):
                if got.get(a) != exp.get(a):
                    print("   0x{:08x}: radiant {:02x} prjoxide {:02x}".format(a, got.get(a, 0), exp.get(a, 0)))
    print("RESULT:", "LIFCL EBR_INIT layout holds" if bad == 0 else "{} mismatches, run full fuzz".format(bad))

if __name__ == "__main__":
    main()
