NAME=adcpins
RUNS=1 2 3 4 5 6 7 8 9 10 11 12
GENERATOR=gen_adc_pins.py
ALLOW_FAIL=true
CLOCKS=clk
# Radiant places an ADC only at grade 8 / 9, industrial (radiant.sh OPER_COND -> postsyn -oc)
export SPEED_GRADE=9_High-Performance_1.0V
export OPER_COND=industrial

include ../../../tools/fuzzer_lfcpnx.mk

# the generator writes the pin constraints too (work/design_N.pdc, picked up by radiant.sh)
work/design_%.v: $(GENERATOR)
	mkdir -p work/
	python3 $(GENERATOR) work/design_$*
