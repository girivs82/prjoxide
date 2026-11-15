(* \db:architecture ="LFCPNX", \db:device ="LFCPNX-100", \db:package ="LFG672", \db:speed ="7_High-Performance_1.0V", \db:timestamp =1576073342, \db:view ="physical" *)
module top (
    ${cmt} ${pintype} q
);

    // Radiant 2026.1 bitgen refuses an undriven q_c (ERROR 67005003), so the VHI drives it.
    // Its route adds CIB pip bits; filter_route_bits.py removes them afterwards.
    (* \xref:LOG ="q_c@0@9" *)
    VHI vhi_i(.Z(q_c));

    (* \xref:LOG ="q_c@0@9" *)
    wire q_c;

    ${cmt}(* \xref:LOG ="${primtype}=q_pad.bb_inst@0@8", \dm:cellmodel_primitives ="${primtype}=q_pad.bb_inst", \dm:primitive ="${primtype}", \dm:programming ="MODE:${primtype} ${primtype}:::IO_TYPE=${iotype},BANK_VCCIO=${vcc}${extra_config}:T=${t}", \dm:site ="${site}" *) 
    ${cmt}${primtype} \q_pad.bb_inst  (.PADDO(q_c));

endmodule