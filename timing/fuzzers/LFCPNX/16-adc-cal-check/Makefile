NAME=adccal
RUNS=1
GENERATOR=gen_adc_cal.py
ALLOW_FAIL=true
CLOCKS=clk
export SPEED_GRADE=9_High-Performance_1.0V
export OPER_COND=industrial

include ../../../tools/fuzzer_lfcpnx.mk

work/design_%.v: $(GENERATOR)
	mkdir -p work/
	python3 $(GENERATOR) work/design_$*
