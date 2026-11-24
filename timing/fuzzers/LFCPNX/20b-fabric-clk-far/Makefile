# The far PCLKCIB entries (r4-r8 / l4-l8), which par uses only when the near entries are taken and
# the centre / other mid-mux tiles are prohibited: nine fabric clocks, their sources pinned to
# entries 0-8 of one side (design r: right, design l: left), from 20-fabric-clk's generator:
#   NCLK=9 ENTRY_LIST="R0 R1 R2 R3 R4 R5 R6 R7 R8" \
#       PROHIBIT="36:40:70:77 70:72:66:81 2:4:66:81 33:41:2:5" python3 $(GENERATOR) work/design_r
#   NCLK=9 ENTRY_LIST="L0 L1 L2 L3 L4 L5 L6 L7 L8" \
#       PROHIBIT="36:40:70:77 70:72:66:81 2:4:66:81 33:41:154:157" python3 $(GENERATOR) work/design_l
NAME=fabclkfar
RUNS=r l
GENERATOR=../20-fabric-clk/gen_fabclk.py
ALLOW_FAIL=true
CLOCKS=clk

include ../../../tools/fuzzer_lfcpnx.mk

work/design_r.v: $(GENERATOR)
	mkdir -p work/
	NCLK=9 ENTRY_LIST="R0 R1 R2 R3 R4 R5 R6 R7 R8" PROHIBIT="36:40:70:77 70:72:66:81 2:4:66:81 33:41:2:5" python3 $(GENERATOR) work/design_r

work/design_l.v: $(GENERATOR)
	mkdir -p work/
	NCLK=9 ENTRY_LIST="L0 L1 L2 L3 L4 L5 L6 L7 L8" PROHIBIT="36:40:70:77 70:72:66:81 2:4:66:81 33:41:154:157" python3 $(GENERATOR) work/design_l
