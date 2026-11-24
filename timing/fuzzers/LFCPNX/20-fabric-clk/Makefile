NAME=fabclk
RUNS=1 2 3 4 5 6 7 8
GENERATOR=gen_fabclk.py
ALLOW_FAIL=true
CLOCKS=clk

include ../../../tools/fuzzer_lfcpnx.mk

# the generator writes the placement constraints too (work/design_N.pdc, picked up by radiant.sh)
work/design_%.v: $(GENERATOR)
	mkdir -p work/
	python3 $(GENERATOR) work/design_$*
