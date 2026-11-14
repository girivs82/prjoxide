"""
DQSBUF settings on LFCPNX-100 (DQSBUFA_CORE): LIFCL's 153-dqsbuf settings, on one DQS group per HP
bank (3, 4, 5), written into that group's five SYSIO_B<n>_*_DQS<k> tile types. The DQSBUFA site of
each group is found by building the primitive at candidate sites (Radiant accepts only the real one).

Usage: fuzzer.py
"""
import importlib.util
import json
import os
import string
import subprocess

from fuzzconfig import FuzzConfig
import database
import fuzzloops
import nonrouting

_spec = importlib.util.spec_from_file_location(
    "iol070", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "070-iologic_mode", "fuzzer.py"))
_spec.loader.exec_module(importlib.util.module_from_spec(_spec))   # robust enum wrapper, work-dir cleanup

GROUPS = [("DQSB3", 149), ("DQSB4", 53), ("DQSB5", 5)]   # (job, column of the group's DQS0 tile), row 74


def group_tiles(c0):
    grid = json.load(open(os.path.join(database.get_db_root(), "LFCPNX", "LFCPNX-100", "tilegrid.json")))["tiles"]
    out = []
    for k in range(5):
        out += [n for n in grid if n.startswith("CIB_R74C%d:" % (c0 + k)) and "_DQS%d" % k in n]
    return out


def main():
    def per_group(x):
        job, c0 = x
        cfg = FuzzConfig(job=job, device="LFCPNX-100", sv="../shared/empty_100.v", tiles=group_tiles(c0))
        cfg.setup()
        empty = cfg.build_design(cfg.sv, {})
        cfg.sv = "dqsbuf_100.v"
        # Site: row 73, three columns left of the group's DQS0 tile (DQSBUFA_CORE_R73C146 for the bank-3
        # group at C149, from Radiant's timing report of a placed DQSBUFA). Radiant only warns about an
        # invalid site and leaves the instance unplaced, so check its log for that.
        site = "DQSBUFA_CORE_R73C{}".format(c0 - 3)
        desfile = os.path.join(cfg.workdir, "probe_design.v")
        with open(cfg.sv) as inf, open(desfile, "w") as ouf:
            ouf.write(string.Template(inf.read()).substitute(mode="DQSBUFA_CORE", cmt="", config="", site=site,
                                                              arcs_attr="", device=cfg.device))
        env = os.environ.copy()
        env["STRUCT_VER"] = "1"
        env["RBK_MODE"] = "1"
        r = subprocess.run(["bash", os.path.join(database.get_oxide_root(), "radiant.sh"), cfg.device, desfile],
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        if "Invalid site" in r.stdout or not os.path.exists(os.path.join(cfg.workdir, "probe_design.bit")):
            print("{}: site {} rejected".format(job, site), flush=True)
            return
        print("{}: tiles {} site {}".format(job, cfg.tiles, site), flush=True)
        if site is None:
            return

        def get_substs(mode="DQSBUFA_CORE", kv=None, mux=False):
            if kv is None:
                config = ""
            elif mux:
                val = "#INV" if kv[1] == "INV" else (kv[1] if kv[1] in ("0", "1") else "#SIG")
                config = "{}::::{}={}".format(mode, kv[0], val)
            else:
                config = "{}:::{}={}".format(mode, kv[0], kv[1])
            return dict(mode=mode, cmt="//" if mode == "NONE" else "", config=config, site=site)

        def intval(vec):
            return sum(1 << i for i, b in enumerate(vec) if b)

        E = nonrouting.fuzz_enum_setting
        E(cfg, empty, "DQSBUF.MODE", ["NONE", "DQSBUFA_CORE"], lambda v: get_substs(mode=v), False, desc="DQSBUF primitive mode")
        for name, vals in [("GSR", ["ENABLED", "DISABLED"]), ("ENABLE_FIFO", ["ENABLED", "DISABLED"]),
                           ("FORCE_READ", ["ENABLED", "DISABLED"]), ("FREE_WHEEL", ["DDR", "GDDR"]),
                           ("MODX", ["NOT_USED", "MDDRX2", "MDDRX4"]), ("MT_EN_READ", ["ENABLED", "DISABLED"]),
                           ("MT_EN_WRITE", ["ENABLED", "DISABLED"]), ("MT_EN_WRITE_LEVELING", ["ENABLED", "DISABLED"]),
                           ("READ_ENABLE", ["ENABLED", "DISABLED"]), ("RX_CENTERED", ["ENABLED", "DISABLED"]),
                           ("WRITE_ENABLE", ["ENABLED", "DISABLED"]), ("SIGN_READ", ["POSITIVE", "COMPLEMENT"]),
                           ("SIGN_WRITE", ["POSITIVE", "COMPLEMENT"]), ("UPDATE_QU", ["UP1_AND_UP0_SAME", "UP1_AHEAD_OF_UP0"]),
                           ("SEL_READ_BIT_ENABLE_CYCLES", ["NORMAL", "DELAYED_0P5_ECLK"]),
                           ("BYPASS_WR_LEVEL_SMTH_LATCH", ["SMOOTHING_PATH", "BYPASS_PATH"]),
                           ("BYPASS_WR_SMTH_LATCH", ["SMOOTHING_PATH", "BYPASS_PATH"]),
                           ("BYPASS_READ_SMTH_LATCH", ["SMOOTHING_PATH", "BYPASS_PATH"])]:
            E(cfg, empty, "DQSBUF." + name, vals, lambda v, n=name: get_substs(kv=(n, v)), False)
        nonrouting.fuzz_word_setting(cfg, "DQSBUF.RD_PNTR", 3,
            lambda v: get_substs(kv=("RD_PNTR", "0b" + "".join(reversed(["1" if b else "0" for b in v])))))
        nonrouting.fuzz_word_setting(cfg, "DQSBUF.S_READ", 9, lambda v: get_substs(kv=("S_READ", str(intval(v)))))
        nonrouting.fuzz_word_setting(cfg, "DQSBUF.S_WRITE", 9, lambda v: get_substs(kv=("S_WRITE", str(intval(v)))))
        for name, pin, vals in [("PAUSEMUX", "PAUSE", ["0", "PAUSE"]), ("RSTMUX", "RST", ["RST", "INV"]),
                                ("SCLKMUX", "SCLK", ["SCLK", "INV"]), ("RSTSMCNTMUX", "RSTSMCNT", ["RSTSMCNT", "INV"])]:
            E(cfg, empty, "DQSBUF." + name, vals, lambda v, p=pin: get_substs(kv=(p, v), mux=True), False)

    fuzzloops.parallel_foreach(GROUPS, per_group)


if __name__ == "__main__":
    main()
