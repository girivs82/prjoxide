(* \db:architecture ="LFCPNX", \db:device ="LFCPNX-100", \db:package ="LFG672", \db:speed ="7_High-Performance_1.0V", \db:timestamp =1576073342, \db:view ="physical" *)
module top (
    
);
    ${cmt} (* \dm:primitive ="DQSBUFA_CORE", \dm:programming ="MODE:${mode} ${config}", \dm:site ="${site}" *) 
    ${cmt} DQSBUFA_CORE DQSBUFA_CORE_I ( );

    // A primitive is needed, but VHI should be harmless
    (* \xref:LOG ="q_c@0@9" *)
    VHI vhi_i();
endmodule
