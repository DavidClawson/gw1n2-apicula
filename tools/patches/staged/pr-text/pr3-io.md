- `json_pinout` / `get_pins`: expose the GW1N-1P5C pinout, keyed under both the
  vendor name and `GW1N-2`.
- OSC: an `('OSCO','GW1N-2')` stub so the oscillator hard-block doesn't block the
  build (full OSCO port map is a TODO).
- IO config: map the GW1N-2 special-pin config codes. 5 of the 10 unmapped codes
  are resolved by cross-referencing the same global `cfg_code` against devices that
  bond the pin out with a label (`75`→LPLL_T_IN, `136`→MCLK/D4, `153`→MO/D6,
  `154`→MI/D7, `160`→MCS_N/D5; from GW1NZ-1 / GW1NS-4). The remaining 5 (codes
  43/44/45/46 @ IOR3A/B,IOR4A/B and 141 @ IOB12A) carry no package label on any
  device with vendor data, so they stay non-fatal `UNKNOWN_CFG_<n>` placeholders
  (all unbonded on QFN48XF — no decode impact).

**Validation (all three apicula PRs together):** the real FNIRSI 2C53T stock
bitstream `gowin_unpack -d GW1N-2`s cleanly — 847 LUT4, 879 FF, 192 ALU, 4 BSRAM,
DDR I/O.

Depends on #517. Part of #515.
