// Structural LPDDR4-style PHY test (decode-only): one byte lane + CA/CK, base primitives only.
module phy1(input refclk, input d, output reg q,
            inout [7:0] dq, inout dqs, output dqs_n_unused_dummy, output dm,
            output [5:0] ca, output cke, output cs, output ck);
    wire eclk, sclk;
    ECLKSYNC #(.STOP_EN("DISABLE")) u_es (.ECLKIN(refclk), .STOP(1'b0), .ECLKOUT(eclk));
    ECLKDIV #(.ECLK_DIV("4"), .GSR("DISABLED")) u_ed (.ECLKIN(eclk), .DIVRST(1'b0), .SLIP(1'b0), .DIVOUT(sclk));
    // control registers
    reg [63:0] r; always @(posedge sclk) r <= {r[62:0], d ^ r[63]};
    wire [8:0] code; wire lock;
    DDRDLL #(.GSR("DISABLED")) u_dll (.CLKIN(eclk), .RST(r[0]), .FREEZE(r[1]), .UDDCNTL_N(r[2]), .CODE(code), .LOCK(lock), .DCNTL());
    // DQS
    wire dqs_in, dqs_o, dqs_t, dqsr90, dqsw, dqsw270; wire [2:0] rdp, wrp;
    wire btd, bud, dval, rdco, wrco, wlco, dqswrd;
    DQSBUF #(.GSR("DISABLED"), .ENABLE_FIFO("ENABLED"), .MODX("MDDRX4"), .READ_ENABLE("ENABLED"), .WRITE_ENABLE("ENABLED"))
      u_dqs (.DQSI(dqs_in), .ECLKIN(eclk), .SCLK(sclk), .RST(r[3]), .PAUSE(r[4]), .RDCLKSEL(r[8:5]), .RDDIR(r[9]),
             .RDLOADN(r[10]), .READ(r[14:11]), .READMOVE(r[15]), .SELCLK(r[16]), .WRDIR(r[17]), .WRLOAD_N(r[18]),
             .WRLVDIR(r[19]), .WRLVLOAD_N(r[20]), .WRLVMOVE(r[21]), .WRMOVE(r[22]), .RSTSMCNT(r[23]), .DLLCODE(code),
             .DQSR90(dqsr90), .DQSW(dqsw), .DQSW270(dqsw270), .RDPNTR(rdp), .WRPNTR(wrp), .BTDETECT(btd), .BURSTDETECT(bud),
             .DATAVALID(dval), .READCOUT(rdco), .WRCOUT(wrco), .WRLVCOUT(wlco), .DQSWRD(dqswrd));
    ODDRX4DQS #(.GSR("DISABLED")) u_dqso (.D0(r[24]),.D1(r[25]),.D2(r[26]),.D3(r[27]),.D4(r[28]),.D5(r[29]),.D6(r[30]),.D7(r[31]),
             .DQSW(dqsw), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(dqs_o));
    TSHX4DQS #(.GSR("DISABLED")) u_dqst (.T0(r[32]),.T1(r[33]),.T2(r[34]),.T3(r[35]), .DQSW(dqsw), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(dqs_t));
    assign dqs = dqs_t ? 1'bz : dqs_o; assign dqs_in = dqs;
    assign dqs_n_unused_dummy = 1'b0;
    // DQ
    wire [63:0] qd;
    genvar i;
    generate for (i = 0; i < 8; i = i + 1) begin : g_dq
        wire o, t, pi, pd;
        ODDRX4DQ #(.GSR("DISABLED")) u_o (.D0(r[i]),.D1(r[i+1]),.D2(r[i+2]),.D3(r[i+3]),.D4(r[i+4]),.D5(r[i+5]),.D6(r[i+6]),.D7(r[i+7]),
             .DQSW270(dqsw270), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(o));
        TSHX4DQ #(.GSR("DISABLED")) u_t (.T0(r[i+8]),.T1(r[i+9]),.T2(r[i+10]),.T3(r[i+11]), .DQSW270(dqsw270), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(t));
        assign dq[i] = t ? 1'bz : o; assign pi = dq[i];
        DELAYA #(.DEL_MODE("USER_DEFINED"), .DEL_VALUE("16"), .COARSE_DELAY_MODE("DYNAMIC")) u_dl (.A(pi), .LOAD_N(r[i+40]), .MOVE(r[i+41]), .DIRECTION(r[i+42]),
             .COARSE0(r[i+43]), .COARSE1(r[i+44]), .RANKSELECT(1'b0), .RANKENABLE(1'b0), .RANK0UPDATE(1'b0), .RANK1UPDATE(1'b0), .Z(pd), .EDETERR(), .CFLAG());
        IDDRX4DQ #(.GSR("DISABLED")) u_i (.D(pd), .DQSR90(dqsr90), .ECLK(eclk), .SCLK(sclk), .RST(r[3]),
             .RDPNTR0(rdp[0]), .RDPNTR1(rdp[1]), .RDPNTR2(rdp[2]), .WRPNTR0(wrp[0]), .WRPNTR1(wrp[1]), .WRPNTR2(wrp[2]),
             .Q0(qd[8*i]),.Q1(qd[8*i+1]),.Q2(qd[8*i+2]),.Q3(qd[8*i+3]),.Q4(qd[8*i+4]),.Q5(qd[8*i+5]),.Q6(qd[8*i+6]),.Q7(qd[8*i+7]));
    end endgenerate
    // DM (output only)
    ODDRX4DQ #(.GSR("DISABLED")) u_dm (.D0(r[50]),.D1(r[51]),.D2(r[52]),.D3(r[53]),.D4(r[54]),.D5(r[55]),.D6(r[56]),.D7(r[57]),
             .DQSW270(dqsw270), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(dm));
    // CA, CKE, CS through ODDRX4 + DELAYB; CK
    wire [7:0] cao;
    generate for (i = 0; i < 8; i = i + 1) begin : g_ca
        wire o;
        ODDRX4 #(.GSR("DISABLED")) u_o (.D0(r[i+16]),.D1(r[i+17]),.D2(r[i+18]),.D3(r[i+19]),.D4(r[i+20]),.D5(r[i+21]),.D6(r[i+22]),.D7(r[i+23]),
             .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(o));
        DELAYB #(.DEL_VALUE("8"), .DEL_MODE("USER_DEFINED")) u_d (.A(o), .Z(cao[i]));
    end endgenerate
    assign ca = cao[5:0]; assign cke = cao[6]; assign cs = cao[7];
    ODDRX4 #(.GSR("DISABLED")) u_ck (.D0(1'b0),.D1(1'b1),.D2(1'b0),.D3(1'b1),.D4(1'b0),.D5(1'b1),.D6(1'b0),.D7(1'b1), .ECLK(eclk), .SCLK(sclk), .RST(r[3]), .Q(ck));
    always @(posedge sclk) q <= ^{qd, lock, btd, bud, dval, rdco, wrco, wlco, dqswrd};
endmodule
