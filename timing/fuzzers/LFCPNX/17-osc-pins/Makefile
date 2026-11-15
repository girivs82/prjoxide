NAME=oscpins
RUNS=1 2 3 4 5 6 7 8 9 10 11 12
GENERATOR=gen_osc_pins.py
ALLOW_FAIL=true
CLOCKS=clk

include ../../../tools/fuzzer_lfcpnx.mk

# the generator writes the pin constraints too (work/design_N.pdc, picked up by radiant.sh)
work/design_%.v: $(GENERATOR)
	mkdir -p work/
	python3 $(GENERATOR) work/design_$*
