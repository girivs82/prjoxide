# The top mid mux's entry t1, which shares its CIB (R1C72, next to TMID) with t0 (t0 from CIBMUXOUT D6,
# t1 from D7): two fabric clocks with their sources in that tile's slices C and D, everything else
# that could take them (centre CMUX tiles, the other top entries' tiles, the other mid muxes' entry
# tiles) prohibited, so par has to use both t0 and t1.
NAME=fabclkt1
RUNS=1
GENERATOR=../20-fabric-clk/gen_fabclk.py
ALLOW_FAIL=true
CLOCKS=clk

include ../../../tools/fuzzer_lfcpnx.mk

work/design_1.v: $(GENERATOR)
	mkdir -p work/
	NCLK=2 ENTRY_LIST="T0 T1" PROHIBIT="36:40:70:77 70:72:66:81 33:41:2:5 33:41:154:157 2:4:73:81 3:4:66:72 2:2:66:71" \
		python3 $(GENERATOR) work/design_1
	sed -i -e '1s/{R2C72[A-D]}/{R2C72C}/' -e '2s/{R2C72[A-D]}/{R2C72D}/' work/design_1.pdc
