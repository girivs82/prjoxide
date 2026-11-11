#!/usr/bin/env bash
# Run INSIDE the radiant-fuzz container after Radiant is installed in /opt/lscc.
# Builds pyprjoxide for amd64, points prjoxide at this Radiant and runs the
# smoke test.
set -euo pipefail
cd /work/prjoxide

[[ -d "$RADIANTDIR/ispfpga/bin/lin64" ]] || { echo "Radiant not found at $RADIANTDIR (set RADIANTDIR)"; exit 1; }
lic="$RADIANTDIR/license/license.dat"
[[ -f "$lic" ]] || echo "WARNING: no licence at $lic yet"

git submodule update --init database 2>/dev/null || true
(cd libprjoxide && cargo build --release)

cat > user_environment.sh <<EOT
# written by tools/radiant-fuzz/docker/container-setup.sh
export RADIANTDIR=$RADIANTDIR
export PYTHONPATH="\${PYTHONPATH}:$CARGO_TARGET_DIR/release"
export PATH="$CARGO_TARGET_DIR/release:\$PATH"
EOT
# python imports libpyprjoxide; cargo names the cdylib liblibpyprjoxide/libpyprjoxide.so
so=$(ls "$CARGO_TARGET_DIR"/release/lib*pyprjoxide*.so | head -1)
[[ -e "$CARGO_TARGET_DIR/release/libpyprjoxide.so" ]] || ln -sf "$so" "$CARGO_TARGET_DIR/release/libpyprjoxide.so"

python3 tools/bitstreamcache.py init || true
tools/radiant-fuzz/smoke-test.sh
