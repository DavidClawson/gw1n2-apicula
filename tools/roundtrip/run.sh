#!/usr/bin/env bash
# End-to-end GW1N-2 round-trip: yosys -> nextpnr-himbaechel -> gowin_pack -> gowin_unpack.
# Run on mars with the apicula venv active and oss-cad-suite on PATH.
set -e
cd "$(dirname "$0")"

CAD=~/gw1n2-apicula/tools/oss-cad-suite
export PATH="$CAD/bin:$PATH"
DEV="GW1N-UV1P5QN48XFC7/I6"     # partnumber; --vopt family forces our chipdb
FAM="GW1N-2"

echo "=== [1/4] yosys synth_gowin ==="
yosys -q -p "read_verilog top.v; synth_gowin -json top.json" 2>&1 | tail -5

echo "=== [2/4] nextpnr-himbaechel (family=$FAM) ==="
nextpnr-himbaechel --device "$DEV" --vopt family="$FAM" \
    --json top.json --write top_pnr.json \
    --vopt cst=top.cst 2>&1 | tail -25

echo "=== [3/4] gowin_pack ==="
cd ~/gw1n2-apicula/tools/apicula
python3 -m apycula.gowin_pack -d "$FAM" -o "$OLDPWD/top.fs" "$OLDPWD/top_pnr.json" 2>&1 | tail -10

echo "=== [4/4] gowin_unpack (read back) ==="
python3 -m apycula.gowin_unpack -d "$FAM" "$OLDPWD/top.fs" -o "$OLDPWD/top_unpacked.v" 2>&1 | tail -5

echo "=== RESULT ==="
ls -la "$OLDPWD/top.fs" "$OLDPWD/top_unpacked.v"
echo "--- primitives in round-tripped netlist (excl DFFSE noise) ---"
grep -oE "^(LUT[0-9]|DFF[A-Z]*|IBUF|OBUF|IOBUF|ALU|MUX[0-9]) " "$OLDPWD/top_unpacked.v" | sort | uniq -c
