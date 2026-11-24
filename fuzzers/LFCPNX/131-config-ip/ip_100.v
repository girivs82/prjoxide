// Configuration cores through their documented user primitives (synthesized flow). Every fabric
// input comes from a register, so map keeps and places the instance.
module top(input clk, input d, output q);
    reg [63:0] s; always @(posedge clk) s <= {s[62:0], d ^ s[63]};
    ${cmt}${body}
    assign q = s[63];
endmodule
