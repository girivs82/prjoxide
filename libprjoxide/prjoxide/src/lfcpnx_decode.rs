//! LFCPNX-only decoder post-passes for the HP-bank (bank 3/4/5) SYSIO tiles.
//!
//! The per-tile decoder picks, for each enum, the longest option whose bits all match. On the
//! LFCPNX HP IO pairs that gives two kinds of misleading output, which these passes resolve with
//! context from the other features. Neither pass changes which bits are explained: a feature is
//! only relabelled to another option whose bits also match, or dropped when the features that
//! remain explain every one of its set bits. Packing the result gives the same CRAM.
//!
//! (a) Pair context. A PIO's settings are split over the pair's two tiles (`SYSIO_B<n>_0*` holds
//!     PIOA, `SYSIO_B<n>_1*` holds PIOB and the rest of PIOA's enums). In the second tile, PIOA's
//!     BASE_TYPE (and DIFFIO18 enums) only see bits that belong to PIOB's unused state, e.g. F89B0,
//!     so on their own they decode as an arbitrary option (OUTPUT_SSTL15_II). They are relabelled to
//!     what the first tile decodes for PIOA (or NONE when PIOA is unused), or dropped when PIOB's
//!     features explain those bits.
//!
//! (b) Shared encodings. DRIVE_<v> and TERMINATION_<v> share bits between supply voltages, and
//!     SLEWRATE / SLEWRATE_REF between groups of IO types, so several decode at
//!     once. Only the ones for the PIO's IO type are kept (the others are dropped when the rest
//!     explains their bits). Options with identical bits within one enum
//!     (e.g. BIDIR_HSUL12, BIDIR_HSTL15_I, BIDIR_LVCMOS15H and BIDIR_LVCMOS18H in the PIOB BASE_TYPE)
//!     cannot be told apart from the bitstream; the decoder emits the canonical one, the last by name,
//!     and the database description of each such enum lists the equivalents.
//!
//! (c) Single-ended LVSTL with the internal reference. An LVSTL_I / LVSTL_II pad with
//!     VREF=VREF_INT sets SEIO18 BASE_TYPE *_LVSTL_* plus VREF_LVSTL.VREF_INT, and together those
//!     cover every set bit of DIFFIO18 BASE_TYPE *_LVSTLD_*, so the differential type decodes as
//!     well. A differential LVSTL pair never sets VREF_INT, so when VREF_INT is decoded the
//!     DIFFIO18 option is dropped (when the remaining features explain its bits): the pad is the
//!     single-ended type with the internal reference.

use crate::chip::{Chip, DecodedFeature, Tile, TileDecode};
use crate::database::Database;
use regex::Regex;
use std::collections::BTreeSet;

lazy_static! {
    static ref FIRST_TILE: Regex = Regex::new(r"^SYSIO_B[345]_0").unwrap();
    static ref SECOND_TILE: Regex = Regex::new(r"^SYSIO_B[345]_1").unwrap();
}

/// The enums of a PIO that exist in several variants, one per group of IO types.
struct Classes {
    /// DRIVE_<x>
    drive: &'static str,
    /// TERMINATION_<x>
    termination: &'static str,
    /// SLEWRATE (LVCMOS) or SLEWRATE_REF (referenced standards)
    slewrate: &'static str,
}

/// The enum variants that apply to an IO standard.
fn io_classes(std: &str) -> Option<Classes> {
    // differential types use the variants of their single-ended standard
    let base = match std {
        "HSUL12D" => "HSUL12",
        "SSTL15D_I" | "SSTL15D_II" => "SSTL15_I",
        "SSTL135D_I" | "SSTL135D_II" => "SSTL135_I",
        "HSTL15D_I" => "HSTL15_I",
        "LVSTLD_I" | "LVSTLD_II" => "LVSTL_I",
        "LVSTL_II" => "LVSTL_I",
        s => s,
    };
    let c = |drive, termination, slewrate| Classes {
        drive,
        termination,
        slewrate,
    };
    Some(match base {
        "LVCMOS18H" | "LVCMOS10R" => c("1V8", "1V8", "SLEWRATE"),
        "LVCMOS15H" => c("1V5", "1V5", "SLEWRATE"),
        "LVCMOS12H" => c("1V2", "1V2", "SLEWRATE"),
        "LVCMOS10H" => c("1V0", "1V0", "SLEWRATE"),
        "SSTL15_I" | "SSTL15_II" | "HSTL15_I" => c("1V5", "1V5", "SLEWRATE_REF"),
        "SSTL135_I" | "SSTL135_II" => c("1V35", "1V35", "SLEWRATE_REF"),
        "HSUL12" => c("HSUL12", "1V2", "SLEWRATE_REF"),
        "LVSTL_I" => c("LVSTL", "1V1", "SLEWRATE_REF"),
        _ => return None,
    })
}

/// The IO standard part of a BASE_TYPE option ("BIDIR_SSTL15_I" -> "SSTL15_I").
fn option_std(opt: &str) -> Option<&str> {
    for d in ["INPUT_", "OUTPUT_", "BIDIR_"] {
        if let Some(s) = opt.strip_prefix(d) {
            return Some(s);
        }
    }
    None
}

fn find<'a>(dec: &'a TileDecode, enum_name: &str) -> Option<&'a str> {
    dec.features.iter().find_map(|f| match &f.enum_name {
        Some((e, o)) if e == enum_name => Some(o.as_str()),
        _ => None,
    })
}

/// Remove the features marked in `drop` whose set bits the remaining features explain.
fn drop_explained(tile: &Tile, dec: &mut TileDecode, drop: &BTreeSet<usize>) {
    if drop.is_empty() {
        return;
    }
    let mut keep: Vec<bool> = (0..dec.features.len())
        .map(|i| !drop.contains(&i))
        .collect();
    // drop one at a time, so two candidates cannot each rely on the other for their bits
    for &i in drop.iter() {
        let explained: BTreeSet<(usize, usize)> = dec
            .features
            .iter()
            .enumerate()
            .filter(|(j, _)| *j != i && (keep[*j] || (drop.contains(j) && *j > i)))
            .flat_map(|(_, f)| f.bits.iter().cloned())
            .chain(dec.always_on.iter().cloned())
            .collect();
        let needed = dec.features[i]
            .bits
            .iter()
            .filter(|(f, b)| tile.cram.get(*f, *b))
            .all(|fb| explained.contains(fb));
        keep[i] = !needed;
    }
    let mut idx = 0;
    dec.features.retain(|_| {
        idx += 1;
        keep[idx - 1]
    });
}

fn relabel(tile: &Tile, db: &mut Database, f: &mut DecodedFeature, opt: &str) -> bool {
    let tdb = db.tile_bitdb(&tile.family, &tile.tiletype);
    let (en, _) = f.enum_name.clone().unwrap();
    let bits = match tdb.db.enums.get(&en).and_then(|e| e.options.get(opt)) {
        Some(b) if tile.option_matches(b) => b.clone(),
        _ => return false,
    };
    f.text = format!("{}.{}", en, opt);
    f.enum_name = Some((en, opt.to_string()));
    f.bits = bits.iter().map(|cb| (cb.frame, cb.bit)).collect();
    true
}

/// (a): second-tile PIOA enums take the first tile's decode of the same enum.
fn pair_context(d0: &TileDecode, t1: &Tile, d1: &mut TileDecode, db: &mut Database) {
    let mut drop = BTreeSet::new();
    for i in 0..d1.features.len() {
        let (en, opt) = match &d1.features[i].enum_name {
            Some((e, o)) if e.starts_with("PIOA.") => (e.clone(), o.clone()),
            _ => continue,
        };
        let owner = find(d0, &en).map(|s| s.to_string());
        let target = match owner {
            Some(o) => o,
            // nothing decoded for PIOA there: PIOA is unused
            None => "NONE".to_string(),
        };
        if target == opt {
            continue;
        }
        if !relabel(t1, db, &mut d1.features[i], &target) {
            drop.insert(i);
        }
    }
    drop_explained(t1, d1, &drop);
}

/// (b): of the per-IO-type enum variants (DRIVE_*, TERMINATION_*, SLEWRATE / SLEWRATE_REF),
/// keep only the ones for the PIO's IO type.
fn voltage_select(tile: &Tile, dec: &mut TileDecode, pio: &str, std: Option<String>) {
    let classes = std.as_deref().and_then(io_classes);
    let mut drop = BTreeSet::new();
    for (i, f) in dec.features.iter().enumerate() {
        let en = match &f.enum_name {
            Some((e, _)) => e,
            None => continue,
        };
        let rest = match en
            .strip_prefix(pio)
            .and_then(|r| r.strip_prefix(".SEIO18."))
        {
            Some(r) => r,
            None => continue,
        };
        let wanted = if let Some(v) = rest.strip_prefix("DRIVE_") {
            classes.as_ref().map_or(false, |c| c.drive == v)
        } else if let Some(v) = rest.strip_prefix("TERMINATION_") {
            classes.as_ref().map_or(false, |c| c.termination == v)
        } else if rest == "SLEWRATE" || rest == "SLEWRATE_REF" {
            classes.as_ref().map_or(false, |c| c.slewrate == rest)
        } else {
            continue;
        };
        if !wanted {
            drop.insert(i);
        }
    }
    drop_explained(tile, dec, &drop);
}

/// (c): a single-ended LVSTL pad with VREF_INT also matches the differential LVSTLD type; drop the
/// DIFFIO18 option in that case.
fn lvstl_single_ended(tile: &Tile, dec: &mut TileDecode, pio: &str) {
    if find(dec, &format!("{}.SEIO18.VREF_LVSTL", pio)) != Some("VREF_INT") {
        return;
    }
    match find(dec, &format!("{}.SEIO18.BASE_TYPE", pio)).and_then(option_std) {
        Some("LVSTL_I") | Some("LVSTL_II") => {}
        _ => return,
    }
    let diff = format!("{}.DIFFIO18.BASE_TYPE", pio);
    let drop: BTreeSet<usize> = dec
        .features
        .iter()
        .enumerate()
        .filter(|(_, f)| match &f.enum_name {
            Some((e, o)) => *e == diff && option_std(o).map_or(false, |s| s.starts_with("LVSTLD_")),
            None => false,
        })
        .map(|(i, _)| i)
        .collect();
    drop_explained(tile, dec, &drop);
}

/// The IO standard a PIO is configured for, from its BASE_TYPE decodes (differential first).
fn pio_std(dec: &TileDecode, pio: &str) -> Option<String> {
    for kind in ["DIFFIO18", "SEIO18"] {
        if let Some(o) = find(dec, &format!("{}.{}.BASE_TYPE", pio, kind)) {
            if o != "NONE" {
                return option_std(o).map(|s| s.to_string());
            }
        }
    }
    None
}

/// Apply the LFCPNX post-passes to the decodes of all of a chip's tiles (same order as chip.tiles).
pub fn postprocess(chip: &Chip, db: &mut Database, decs: &mut [TileDecode]) {
    for i in 0..chip.tiles.len() {
        let t1 = &chip.tiles[i];
        if !SECOND_TILE.is_match(&t1.tiletype) || t1.x == 0 {
            continue;
        }
        // the first tile of the pair is the SYSIO tile one column to the left
        let j = match chip
            .tiles
            .iter()
            .position(|t| t.x + 1 == t1.x && t.y == t1.y && FIRST_TILE.is_match(&t.tiletype))
        {
            Some(j) => j,
            None => continue,
        };
        let (d0, d1) = if j < i {
            let (a, b) = decs.split_at_mut(i);
            (&mut a[j], &mut b[0])
        } else {
            let (a, b) = decs.split_at_mut(j);
            (&mut b[0], &mut a[i])
        };
        let t0 = &chip.tiles[j];
        lvstl_single_ended(t0, d0, "PIOA");
        let std_a = pio_std(d0, "PIOA");
        voltage_select(t0, d0, "PIOA", std_a);
        pair_context(d0, t1, d1, db);
        let std_b = pio_std(d1, "PIOB");
        voltage_select(t1, d1, "PIOB", std_b);
    }
}
