# LFCPNX: a clock from an input pad through a DLLDEL (the clock-input delay cell beside a PCLK pad)
# to registers, plus a fabric-driven DLLDEL control, for the io33 -> dlldel / dlldel_internal hops
# and the DLLDEL cell arcs. The pad is a bank-1 PCLK pin (SEIO33), as in the design that showed them.
print("module top(input clk_io, input clk, input [7:0] d, output q);")
print("    wire cz;")
print("    DLLDEL #(.ADJUST(\"0\"), .DEL_ADJUST(\"PLUS\"), .ENABLE(\"ENABLED\")) u_dd (.CLKIN(clk_io), .LOAD_N(d[0]), .MOVE(d[1]), .DIR(d[2]), .CODE(9'b0), .COUT(), .CLKOUT(cz));")
print("    reg [31:0] s;")
print("    always @(posedge cz) s <= {s[30:0] ^ {31{d[3]}}, d[4]};")
print("    reg qq; always @(posedge clk) qq <= ^s;")
print("    assign q = qq;")
print("endmodule")
