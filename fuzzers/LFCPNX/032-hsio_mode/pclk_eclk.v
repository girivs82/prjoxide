module top (
    (* LOC="${d_ball}", IO_TYPE="LVCMOS18H" *) input d,
    (* LOC="${eclk_ball}", IO_TYPE="LVCMOS18H" *) input eclk,
    (* LOC="${x_ball}", IO_TYPE="LVCMOS18H" *) input x,
    (* LOC="AA1", IO_TYPE="LVCMOS33" *) output q
);
    wire eclks, sclk;
    wire [3:0] qq;
    ECLKSYNC esync (.ECLKIN(eclk), .STOP(1'b0), .ECLKOUT(eclks));
    ECLKDIV_CORE #(.ECLK_DIV("2")) ediv (.ECLKIN(eclks), .DIVOUT(sclk));
    IDDRX2 iddr (.D(d), .ECLK(eclks), .SCLK(sclk), .RST(1'b0), .ALIGNWD(1'b0), .Q0(qq[0]), .Q1(qq[1]), .Q2(qq[2]), .Q3(qq[3]));
    assign q = ^qq ^ x;
endmodule
