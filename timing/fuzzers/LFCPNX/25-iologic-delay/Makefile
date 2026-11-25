NAME=iologicdelay
RUNS=1 2 3
GENERATOR=gen_iologic_delay.py
ALLOW_FAIL=true
CLOCKS=refclk

include ../../../tools/fuzzer_lfcpnx.mk

# the generator writes the pin constraints too (work/design_N.pdc, picked up by radiant.sh)
work/design_%.v: $(GENERATOR)
	mkdir -p work/
	python3 $(GENERATOR) work/design_$*
