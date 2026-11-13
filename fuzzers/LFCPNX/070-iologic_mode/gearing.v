module top (
    (* LOC="${d_ball}", IO_TYPE="LVCMOS18H" *) input d,
    (* LOC="${eclk_ball}", IO_TYPE="LVCMOS18H" *) input eclk,
    (* LOC="${q_ball}", IO_TYPE="LVCMOS33" *) output q
);
    wire eclks, sclk;
    wire [${nq1}:0] qq;
    ECLKSYNC esync (.ECLKIN(eclk), .STOP(1'b0), .ECLKOUT(eclks));
    ECLKDIV_CORE #(.ECLK_DIV("${div}")) ediv (.ECLKIN(eclks), .DIVOUT(sclk));
    ${mode} iddr (.D(d), .ECLK(eclks), .SCLK(sclk), .RST(1'b0), .ALIGNWD(1'b0), ${qconn});
    assign q = ^qq;
endmodule
