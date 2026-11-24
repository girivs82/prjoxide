# 131-config-ip: configuration cores (LFCPNX-100)

LIFCL's 131-config-ip places structural instances of the configuration cores at named sites
(TCONFIG_<core><n>), found with lapie. On LFCPNX-100 those names are not known without lapie, and a
structural instance with no site is dropped: it sets no bits at all. So this fuzzer uses the
synthesized flow with the documented user primitives (prjoxide's `docs/general/multiboot.md`), which
map places itself, with every fabric input on a register (`ip_100.v`).

| Core | LFCPNX-100 |
|---|---|
| CONFIG_MULTIBOOT_CORE (MULTIBOOT) | SOURCESEL (EFB_0) and the 32-bit MSPIADDR (EFB_0 / EFB_2): the same bits as LIFCL-40 |
| CONFIG_CLKRST_CORE | no bits: map drops it, since its outputs can only drive CONFIG_LMMI, which this device lacks |
| CONFIG_LMMI_CORE, CONFIG_HSE_CORE | not on this device: sv2udb reports them as unknown modules, and LSE knows no CONFIG_LMMI / CONFIG_LMMIC |
| CONFIG_IP_CORE, CONFIG_WDT_CORE | not fuzzed: no documented user primitive |

The settings tables are LIFCL's.

## Run

    fuzzer.py
