# 040-speed: CHIP.SPEED (LFCPNX-100)

LIFCL's 040-speed: the empty design built for speed grade 7_High-Performance_1.0V and for
7_Low-Power_1.0V (the netlist header's `db:speed`), diffed over every tile. The only difference is
PMU F11B0: set for SLOW_1V0 (Low-Power), clear for FAST_1V0 (High-Performance). This is the same bit
as on LIFCL-40.
