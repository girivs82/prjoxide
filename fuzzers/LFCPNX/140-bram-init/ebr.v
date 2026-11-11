
(* \db:architecture ="LFCPNX", \db:device ="LFCPNX-100", \db:package ="LFG672", \db:speed ="7_High-Performance_1.0V", \db:timestamp =1576073342, \db:view ="physical" *)
module top (
    
);
   (* \dm:primitive ="EBR_CORE", \dm:programming ="MODE:EBR_CORE EBR_CORE:::WID=0b00000000000,INITVAL_${a}=${v}", \dm:site ="EBR_CORE_R10C99" *) 
   EBR_CORE EBR_I ( );

    // A primitive is needed, but VHI should be harmless
    (* \xref:LOG ="q_c@0@9" *)
    VHI vhi_i();
endmodule
