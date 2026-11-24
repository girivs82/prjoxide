NAME=dlldel
RUNS=1 2
GENERATOR=gen_dlldel.py
ALLOW_FAIL=true
CLOCKS=clk

include ../../../tools/fuzzer_lfcpnx.mk

# the clock pad: LVCMOS33, placed by par on a PCLK pin that has a DLLDEL
work/design_%.v: $(GENERATOR)
	mkdir -p work/
	python3 $(GENERATOR) > $@
	printf 'ldc_set_port -iobuf {IO_TYPE=LVCMOS33} [get_ports clk_io]\n' > work/design_$*.pdc
