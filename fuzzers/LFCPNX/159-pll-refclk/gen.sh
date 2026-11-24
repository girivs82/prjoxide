#!/bin/bash
# gen.sh <PllCore wrapper .v> <LLC|LRC|ULC|URC> <package pin> <bank>
# Writes <PLL>_<pin>.v / .pdc: a PLL_CORE wrapper (module PllCore: REFCK, PLLRESET, CLKOP, LOCK; FBKCK
# = CLKOP) pinned at PLL_<PLL>, REFCK from the given pin, CLKOP clocking a counter. Build each with
# radiant.sh LFCPNX-100 <name> in the Radiant container.
wrapper=$1; pll=$2; pin=$3; bank=$4; n=${pll}_${pin}
cat "$wrapper" > $n.v
cat >> $n.v <<V
module top(input refin, output led0, output led1);
    wire op, lock; reg [7:0] c = 0;
    PllCore u_pll (.REFCK(refin), .PLLRESET(1'b0), .CLKOP(op), .LOCK(lock));
    always @(posedge op) c <= c + 1;
    assign led0 = c[7]; assign led1 = lock;
endmodule
V
case $bank in 3|4|5) io=LVCMOS18H;; *) io=LVCMOS33;; esac
cat > $n.pdc <<P
ldc_set_location -site {$pin} [get_ports refin]
ldc_set_port -iobuf {IO_TYPE=$io} [get_ports refin]
ldc_set_location -site {PLL_$pll} [get_cells {u_pll/PllCore_inst}]
P
echo $n
