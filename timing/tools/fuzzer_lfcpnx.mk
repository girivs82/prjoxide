# Timing fuzzer flow for LFCPNX (no lapie): build with LSE + par, read the routing back from the
# readback bitstream, and backannotate every speed grade.
#
# Per run:
#   work/design_N.v          generated design
#   work/design_N.bit        readback (RBK) bitstream (radiant.sh RBK_MODE=1, -ipeval)
#   work/design_N.fasm       prjoxide unpack of it (the routed pips)
#   work/design_N.twr        Radiant timing report (cell sites on reported paths)
#   $(OUT_DIR)/NAME_N_G.vo/.sdf   backannotated netlist + SDF per grade G (and M = -min)
#   $(OUT_DIR)/NAME_N_route.pickle  arc2pips/wire_fanout from timing/util/extract_route_cram.py
#
# Fuzzer Makefiles set NAME, RUNS, GENERATOR, ALLOW_FAIL and CLOCKS (top-level clock ports, used
# to constrain the timing report so it lists paths; may be empty).

SHELL=/bin/bash
DEVICE?=LFCPNX-100
GRADES?=4 5 6 7 8 9 10 11 12
ROUTE_GRADE?=9
CLOCKS?=

all: work/stamp

work/stamp: $(foreach run,$(RUNS),work/$(run).stamp)
	touch $@

BASE_DIR=../../../..
OUT_DIR=../../../output/LFCPNX
UTIL=$(BASE_DIR)/timing/util
PYPATH=$(BASE_DIR)/util/common:$(BASE_DIR)/util/fuzz:$(UTIL)
PRJOXIDE?=prjoxide

work/design_%.v: $(GENERATOR)
	mkdir -p work/
	python3 $(GENERATOR) > $@

work/design_%.bit: work/design_%.v
	# FORCE_REBUILD: the bitstream cache keeps only par.udb and the bitstream, and the
	# placement steps below also need par's .pad report
	FORCE_REBUILD=1 RBK_MODE=1 $(BASE_DIR)/radiant.sh $(DEVICE) $< || $(ALLOW_FAIL)

work/design_%.sdc:
	mkdir -p work/
	( for c in $(CLOCKS); do echo "create_clock -name $${c//[^A-Za-z0-9_]/_} -period 1 [get_ports {$$c}]"; done; \
	  c0="$(firstword $(CLOCKS))"; if [ -n "$$c0" ]; then \
	  echo "set_input_delay -clock $${c0//[^A-Za-z0-9_]/_} 0.1 [all_inputs]"; \
	  echo "set_output_delay -clock $${c0//[^A-Za-z0-9_]/_} 0.1 [all_outputs]"; fi ) > $@

work/%.stamp: work/design_%.bit work/design_%.sdc
	set -e -o pipefail; T=work/design_$*.tmp; \
	if [ ! -e work/design_$*.bit ]; then echo "design $* did not build"; touch $@; exit 0; fi; \
	mkdir -p $(OUT_DIR); \
	for g in $(GRADES); do \
		$(BASE_DIR)/radiant_cmd.sh backanno -sp $$g -w -o $(OUT_DIR)/$(NAME)_$*_$$g.vo $$T/par.udb > $$T/backanno_$$g.log 2>&1 || true; \
	done; \
	$(BASE_DIR)/radiant_cmd.sh backanno -min -w -o $(OUT_DIR)/$(NAME)_$*_M.vo $$T/par.udb > $$T/backanno_M.log 2>&1 || true; \
	$(PRJOXIDE) unpack work/design_$*.bit work/design_$*.fasm > /dev/null; \
	if [ -s work/design_$*.sdc ]; then SDC="-sdc-file work/design_$*.sdc"; else SDC=""; fi; \
	$(BASE_DIR)/radiant_cmd.sh timing -db-file $$T/par.udb $$SDC -sp $(ROUTE_GRADE) -sethld \
		-endpoints 1000000 -v 1000000 -nperend 4 -u 1000000 -o work/design_$*.twr > $$T/timing.log 2>&1 || true; \
	touch work/design_$*.twr; \
	PYTHONPATH=$(PYPATH) python3 $(UTIL)/extract_route_cram.py work/design_$*.fasm \
		$(OUT_DIR)/$(NAME)_$*_$(ROUTE_GRADE).vo $(OUT_DIR)/$(NAME)_$*_$(ROUTE_GRADE).sdf $$T/par.pad \
		$(OUT_DIR)/$(NAME)_$*_route.pickle work/design_$*.twr | tee work/route_$*.log; \
	touch $@

.PRECIOUS: work/design_%.v work/design_%.bit work/design_%.sdc work/%.stamp
