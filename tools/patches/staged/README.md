# Staged GW1N-2 upstream patches

Split from the consolidated `../gw1n2-support.patch` into per-PR pieces, in
submission order. Full PR text (titles, descriptions, tracking issue) is in
`docs/08-pr-drafts.md`. Process notes: `docs/04-contributing.md`.

| file | PR | files touched |
|---|---|---|
| `01-dat_parser-parttype1.patch` | PR1: partType-1 `.dat` support (standalone) | `dat_parser.py` |
| `02-recognize-and-build.patch` | PR2: recognize + build chipdb | `bslib.py`, `chipdb_builder.py`, `gowin_unpack.py`, `Makefile` |
| `03-pinout-io-osc.patch` | PR3: pinout / IO / OSC (PLL-free) | `chipdb.py` |
| `HELD-pll-partial.diff` | NOT for submission — blocked rPLL (see docs/06/07) | `chipdb.py` |
| `LOCAL-codegen-preload.patch` | NOT GW1N-2 — local headless-gw_sh aid | `codegen.py` |

### Separate repo: YosysHQ/nextpnr (reviewer `gatecat`) — `nextpnr/`
| file | what | files touched |
|---|---|---|
| `nextpnr/01-gw1n2-arch-gen.patch` | nextpnr GW1N-2 support (whole change) | `himbaechel/uarch/gowin/CMakeLists.txt`, `gowin_arch_gen.py` |
| `examples-gw1n2/` | `examples/gw1n2/` blinky for CI (drop into apicula repo) | new dir |

No `gowin.cc` change needed (example uses `--vopt family=GW1N-2`, the house idiom).
See `nextpnr/README.md`. nextpnr depends on the apicula PRs landing first.

**Validated** (2026-06-13): applying PR1+PR2+PR3 to a clean apicula tree builds the
GW1N-2 chipdb and unpacks the real FNIRSI scope bitstream cleanly (847 LUT4 / 879 FF
/ 192 ALU / 4 BSRAM) — no PLL required. The nextpnr patch + example are validated by
a from-source nextpnr build (`-DHIMBAECHEL_GOWIN_DEVICES="GW1N-2"`, 0 errors) that
routes the blinky to a `blinky-gw1n2.fs` (sync `0xA5C3`), then unpacks it back.

## Apply (on a fresh apicula checkout)
```bash
cd apicula
git apply /path/to/01-dat_parser-parttype1.patch
git apply /path/to/02-recognize-and-build.patch
git apply /path/to/03-pinout-io-osc.patch
make apycula/GW1N-2.msgpack.xz
```
