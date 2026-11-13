module top (
    (* LOC="${d_ball}", IO_TYPE="LVCMOS18H" *) input d,
    (* LOC="AA2", IO_TYPE="LVCMOS33" *) input c,
    (* LOC="AA4", IO_TYPE="LVCMOS33" *) input c2,
    (* LOC="AA1", IO_TYPE="LVCMOS33" *) output q
);
    wire z;
    DELAYA #(.DEL_MODE("USER_DEFINED"), .DEL_VALUE("0")) del (.A(d), .LOAD_N(${load_n}), .MOVE(${move}),
        .DIRECTION(${direction}), .COARSE0(1'b0), .COARSE1(1'b0), .RANKSELECT(1'b0), .RANKENABLE(1'b0),
        .RANK0UPDATE(1'b0), .RANK1UPDATE(1'b0), .Z(z));
    assign q = z ^ c2;
endmodule
