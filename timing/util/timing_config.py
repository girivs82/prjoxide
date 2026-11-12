# These pip classes always have zero delay

zero_delay_classes = {
    "slice_internal",
    "vcc_internal",
    "s1:span1s -> a",
    "jeclkdiv0_mid_entry",
    "jeclkdiv0 -> jvpf_mid",
    "f -> a",
    "f -> b",
    "f -> c",
    "f -> d",
    "q -> abcd",
    "cibmuxo -> io18",
    "clk -> clk_dff",
}

# Per family: speed grades to process ("M" = backanno -min) and the grade whose SDF defines the
# set of interconnect arcs for the solver (all grades share the routing)
families = {
    "LIFCL": dict(speedgrades=["4", "5", "6", "10", "11", "12", "M"], template_grade="10"),
    "LFCPNX": dict(speedgrades=["4", "5", "6", "7", "8", "9", "10", "11", "12", "M"], template_grade="9",
                   nonneg=True),
}


def family_from_args(argv):
    """Family named by the optional second command line argument (default LIFCL)."""
    fam = argv[2] if len(argv) > 2 else "LIFCL"
    assert fam in families, "unknown family {}".format(fam)
    return fam, families[fam]
