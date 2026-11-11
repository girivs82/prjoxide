# Radiant fuzzing setup (LFCPNX)

Runs Lattice Radiant 2026.1 (Linux) in a single amd64 Docker container, so the
LFCPNX fuzzers in `fuzzers/LFCPNX/` can run on any host, including Apple
Silicon (via Colima + Rosetta). See `fuzzers/LFCPNX/README.md` for what each
fuzzer produces and where each piece of data comes from.

## Ground rules

- Use the free node-locked Radiant licence on **one** container only.
  `docker/run-radiant.sh` always uses the container name `radiant-fuzz` and
  refuses to start while another container carries the licence MAC.
- The licence host ID goes in `docker/licence-mac` (git-ignored). Never commit it.
- No Synplify: the fuzzers feed structural netlists to `sv2udb`
  (`STRUCT_VER=1`); no synthesis runs.
- Only vary inputs and diff bitstreams; do not inspect Radiant internals.
- Commit only the derived database. Radiant outputs (bitstreams, udb, IP
  generator output, logs, `.bitstreamcache/`) stay local.

## Setup

```sh
# container runtime on macOS (Linux: plain Docker works)
brew install colima docker docker-buildx
colima start --vm-type vz --vz-rosetta --cpu 8 --memory 16 --disk 100 --mount ~:w

echo 02:xx:xx:xx:xx:xx > tools/radiant-fuzz/docker/licence-mac   # your licence host ID
tools/radiant-fuzz/docker/run-radiant.sh build                     # Ubuntu 22.04 amd64 image, no Lattice files
tools/radiant-fuzz/docker/run-radiant.sh shell
#   inside, with the Linux installer in $WORK (host ~/src/radiant-work, mounted at /work):
#     ./<version>_Radiant_lin.run --console --prefix /opt/lscc/radiant/2026.1
#   (Lattice disabled the usual Qt-IFW options; --console installs the default
#   set, ~49 GB. Device families you don't need, e.g. Avant ispfpga/ap6a00*,
#   can be deleted afterwards while no Radiant process is running.)
#   licence on the host at ~/lscc/radiant/2026.1/license/license.dat
#   then: /work/prjoxide/tools/radiant-fuzz/docker/container-setup.sh
```

Mounts: `~/lscc` -> `/opt/lscc`, `~/src/radiant-work` -> `/work` (amd64 cargo
target, installers, scratch), this checkout -> `/work/prjoxide`.

The smoke test builds `fuzzers/LFCPNX/shared/empty_100.v` and unpacks it:
about 13 s per build (sv2udb 1 s, bitgen 7 s). `radiant.sh` passes `-ipeval`
to bitgen for LFCPNX; bitgen then prints a "Hardware Evaluation ... about 4
hours" warning even for an empty design, and full bitstreams are encrypted,
which is why LFCPNX-100 fuzzing uses readback (RBK) bitstreams.

Run a fuzzer:
`cd /work/prjoxide && set +u && source environment.sh && cd fuzzers/LFCPNX/<dir> && OXIDE_JOBS=6 python3 fuzzer.py`
(about 1.6 GB of RAM per concurrent bitgen).

## Tools

- `filter_route_bits.py <db>`: after the IO fuzzes, removes pip bits that
  could leak into PIO enums (the IO templates drive PADDO from a VHI because
  Radiant 2026.1 bitgen refuses undriven nets).
- `compare_with_lifcl.py <db> 'SYSIO_*'`: per tile, which fuzzed LFCPNX
  settings match the LIFCL tile of the same name.
- `derive_gpll_tiles.py`: builds GPLL_LLC / GPLL_URC pips and conns from the
  LIFCL tiles, with the LFCPNX offsets observed in Radiant-routed PLL designs.
- `smoke-test.sh`, `docker/` (image, single-container launcher, in-container setup).
