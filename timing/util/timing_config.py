# These pip classes always have zero delay

zero_delay_classes = {
    "slice_internal",
    # the PLL's REFCK / FBKCK pin is its REFMUX / FBKMUX output under another name (a fixed
    # connection inside the PLL block)
    "refmux -> pll",
    "fbkmux -> pll",
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
    # LFCPNX: the CIB test-mux hop of a hard block's output (JQn_CIBTEST -> JQn, JFn_CIBTEST ->
    # JFn), part of the measured "<block> -> q" / "<block> -> f" delay (see pip_classes.rs)
    "q -> q",
    "f -> f",
    # a route through a clock cell: the cell's own arc (cells_<grade>.json "DCS:DCS", "DLLDEL")
    # carries the delay
    "dcs_internal",
    "dlldel_internal",
}

# Classes Radiant never routes through (so no design measures them), given the delay of a measured
# class of the same wire into the same kind of pin. LFCPNX: a span-1 wire into a slice's M input from
# the tile beside it (w1: / e1:); Radiant's routes only enter M from a span-1 wire in its own tile
# (timing/fuzzers/LFCPNX/21-m-input: 69k arcs, none through these pips), and the span-1 delay into
# A-D is the same within 3 ps whichever tile the wire comes from.
derived_classes = {
    "w1:span1w -> m": "span1w -> m",
    "e1:span1w -> m": "span1w -> m",
}

# Per family: speed grades to process ("M" = backanno -min) and the grade whose SDF defines the
# set of interconnect arcs for the solver (all grades share the routing)
families = {
    "LIFCL": dict(speedgrades=["4", "5", "6", "10", "11", "12", "M"], template_grade="10"),
    "LFCPNX": dict(speedgrades=["4", "5", "6", "7", "8", "9", "10", "11", "12", "M"], template_grade="9",
                   nonneg=True, keep_unsolved=True),
}


def family_from_args(argv):
    """Family named by the optional second command line argument (default LIFCL)."""
    fam = argv[2] if len(argv) > 2 else "LIFCL"
    assert fam in families, "unknown family {}".format(fam)
    return fam, families[fam]
