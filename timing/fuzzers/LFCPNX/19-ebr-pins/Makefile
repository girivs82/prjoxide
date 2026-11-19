NAME=ebrpins
RUNS=1 2 3 4 5 6
GENERATOR=gen_ebr_pins.py
ALLOW_FAIL=true
CLOCKS=clk
# only the routing is needed (tools/radiant-fuzz/infer_ebr_conns.py), not the timing of every grade
GRADES=9

include ../../../tools/fuzzer_lfcpnx.mk
