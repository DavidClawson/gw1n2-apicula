# examples/gw1n2 — GW1N-2 toolchain example

Drop this directory in at `apicula/examples/gw1n2/` (mirrors `examples/gw5a/`).
It feeds `toolchain.yml` so CI exercises the new device end-to-end.

## Files
- `blinky.v` — 24-bit counter → LED (carry chain + FFs + IO).
- `gw1n2.cst` — pin constraints (`clk`=9, `led`=14, valid for QN48).
- `Makefile` — self-contained; `make gw1n2` builds `blinky-gw1n2.fs`.

## How it builds
```
yosys synth_gowin
  → nextpnr-himbaechel --device GW1N-UV1P5QN48XFC7/I6 --vopt family=GW1N-2
  → gowin_pack -d GW1N-2 → blinky-gw1n2.fs
```
`--vopt family=GW1N-2` selects the chipdb, the same idiom `tangnano9k` uses with
`--vopt family=GW1N-9C`. No `gowin.cc` change is needed.

## Validated (2026-06-13, mars)
Against a from-source nextpnr built with `-DHIMBAECHEL_GOWIN_DEVICES="GW1N-2"`:
`make gw1n2` completes with 0 errors; `blinky-gw1n2.fs` has sync `0xA5C3`;
`make gw1n2-unpacked` reads it back to 26 ALU / 38 DFFE / 8 LUT4 / OBUF+IBUF.

## CI wiring
Add to `.github/workflows/toolchain.yml` `example` matrix:
```yaml
        - {target: gw1n2, dir: examples/gw1n2}
```

## Open item (maintainer call)
Board/part identity. The only GW1N-2 hardware on hand is the FNIRSI 2C53T scope
(not a dev board); the die ships license-free as GW1N-1P5C, so the example uses the
GW1N-1P5C partnumber. The board *name* and whether to use a real GW1N-2-branded
partnumber (needs GW1N-2 package aliases in apicula pinout data) is TBD with
`gatecat`/`yrabbit`.
