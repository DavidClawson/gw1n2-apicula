# GW1N-2 blinky example (validated)

A counter→LED blinky that round-trips on real GW1N-2 support:
`yosys → nextpnr-himbaechel → gowin_pack → .fs → gowin_unpack` (verified 2026-06-13;
readback = 26 ALU carry-chain + 34 DFFE counter + LED OBUF).

This is the seed for the upstream `examples/gw1n2/` directory. It must be added to
Apicula's `examples/` **with or after** the nextpnr-himbaechel GW1N-2 support lands,
because CI (`toolchain.yml`) builds the example through nextpnr (which needs the
GW1N-2 chipdb). Coordinate the board/part naming with the maintainers.

## Build (on mars)
```bash
cd ~/gw1n2-apicula/tools/apicula && source .venv/bin/activate
export PATH=~/gw1n2-apicula/tools/oss-cad-suite/bin:$PATH
yosys -p "read_verilog blinky.v; synth_gowin -json blinky.json"
nextpnr-himbaechel --device GW1N-UV1P5QN48XFC7/I6 --vopt family=GW1N-2 \
    --json blinky.json --write pnr.json --vopt cst=blinky.cst
python3 -m apycula.gowin_pack -d GW1N-2 -o blinky.fs pnr.json
```
Pins (`blinky.cst`) are placeholders for the QFN48XF package — set real board pins
before flashing hardware.
