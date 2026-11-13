module top (
    (* LOC="${d_ball}", IO_TYPE="${iostd}" *) inout p,
    (* LOC="${t_ball}", IO_TYPE="LVCMOS33" *) input t,
    (* LOC="${i_ball}", IO_TYPE="LVCMOS33" *) input i,
    (* LOC="${i2_ball}", IO_TYPE="LVCMOS33" *) input i2,
    (* LOC="${o_ball}", IO_TYPE="LVCMOS33" *) output o,
    (* LOC="${o2_ball}", IO_TYPE="LVCMOS33" *) output o2,
    (* LOC="${clk_ball}", IO_TYPE="LVCMOS18H" *) input clk
);
    wire pi, po, pt;
    BB b (.B(p), .I(po), .T(pt), .O(pi));
    OFD1P3DX tr (.D(t), .CK(clk), .SP(1'b1), .CD(1'b0), .Q(pt));
    ${body}
endmodule
