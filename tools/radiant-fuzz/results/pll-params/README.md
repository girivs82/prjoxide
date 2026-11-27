# LFCPNX PLL_CORE parameter sets (derived)

From Radiant 2026.1.1 `ipgen` with the PLL module (ip/lifcl/pll v1.9.1, lists LFCPNX as supported), for LFCPNX-100 LFG672,
each wrapper elaborated with LSE to read the resolved PLL primitive parameters (121 per case). One `name=value` file per case.
Names match prjoxide's LIFCL iptypes/PLL_CORE.ron (plus a few primitive-only ones such as SIM_FLOAT_PRECISION, PMU_WAITFORLOCK, REF_OSC_CTRL).

- Dividers are ratio-1: CLKOP = VCO/(DIVA+1); VCO = CLKI*FBK_MMD_DIG*(DIVA+1)/REF_MMD_DIG (CLKOP feedback). VCO is 1600 or 1500 MHz.
- DIV_DEL = DIVA as 7 bits; DELx = DIVx at zero phase.
- REF_MMD_PULS_CTL = 1 iff REF_MMD_DIG > 1; FBK_MMD_PULS_CTL = 1 iff FBK_MMD_DIG >= 4.
- Loop group (BW_CTL_BIAS/IPI_CMP/IPP_CTRL/IPP_SEL): 0b0101/0b0001/0b0100/0b0111 when REF_MMD_DIG=1 and FBK_MMD_DIG*(DIVA+1)=12, else 0b1111/0b1100/0b0110/0b1111.
- Constants include CSET=8P, CRIPPLE=1P, V2I_PP_RES=9K, V2I_KVCO_SEL=60, KP_VCO=0b00011, LDT_LOCK=1536CYC.
