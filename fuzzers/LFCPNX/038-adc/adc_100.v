// ADC (ADC_CORE) on LFCPNX-100, synthesized flow: every fabric input from a register, every output
// captured. CLKDCLK left open (map and par accept CLKFAB alone).
module top(input clk, input d, output q);
    reg [31:0] s; always @(posedge clk) s <= {s[30:0], d ^ s[31]};
    wire [11:0] da, db; wire calrdy, cog, eoc, c1o, c2o, c3o, c1l, c2l, c3l;
    ${cmt}ADC #(${params}) u_adc (.ADCEN(s[0]), .CAL(s[1]), .CHAEN(s[2]), .CHASEL(s[6:3]), .CHBEN(s[7]), .CHBSEL(s[11:8]),
    ${cmt}    .CLKFAB(clk), .CONVSTOP(s[15]), .RESETN(s[16]), .RSTN(s[17]), .SOC(s[18]),
    ${cmt}    .CALRDY(calrdy), .COG(cog), .DA(da), .DB(db), .EOC(eoc), .COMP1O(c1o), .COMP2O(c2o), .COMP3O(c3o),
    ${cmt}    .COMP1OL(c1l), .COMP2OL(c2l), .COMP3OL(c3l));
    reg [31:0] c; always @(posedge clk) c <= {da, db, calrdy, cog, eoc, c1o, c2o, c3o, c1l, c2l};
    assign q = ^c ^ s[20];
endmodule
