# 05 — "Needs David" checklist (human-only items)

> Updated 2026-06-13 after M5. The original build blockers (Gowin EDA + Linux env)
> are **resolved** — the full pipeline runs on mars and the real scope bitstream
> unpacks. Only outward-facing / physical steps remain.

## ✅ Resolved build blockers (history)
- **Gowin EDA**: installed on mars as **Education V1.9.11.03** at
  `~/gowin/V1.9.11.03_Education` (license-free; the Standard edition needs a license
  server). Note: the GW1N-2 die ships only as **GW1N-1P5C** in Education — same
  silicon, IDCODE `0x0120681B` verified. Headless `gw_sh` works with
  `QT_QPA_PLATFORM=offscreen` + system-libfreetype preload (`tools/gowin-env.sh`).
- **Linux env**: `david@mars.local` (x86-64 Ubuntu 24.04), apicula venv +
  oss-cad-suite + a locally-built `nextpnr/bba/bbasm` all in `~/gw1n2-apicula/tools/`.

## Remaining human-only items

### 1 — Submit the upstream contribution (M6) 📤
The code is done and validated; submission is community interaction, so it's yours.
- [ ] Ping `yrabbit` on Matrix `#apicula:matrix.org`; open a tracking Issue
      ("Add GW1N-2 support").
- [ ] Open the staged PRs per `docs/04-contributing.md` → "GW1N-2 staging plan"
      (patches ready in `tools/patches/gw1n2-support.patch` +
      `tools/patches/nextpnr-gw1n2-gen.patch`). Disclose the documented caveats.

### 2 — Physical scope hardware 🔌 (optional, verification)
- [ ] Load an authored GW1N-2 `.fs` (e.g. `tools/roundtrip/top.fs`) onto the 2C53T
      over JTAG/SPI to confirm a hand-built bitstream actually configures the part.
      Everything to date is validated in software (CRC + round-trip + plausible
      decode of the stock stream) but not yet on silicon.

## Optional follow-ups the agent CAN still do (not blocked)
- **M4a — finish the PLL** (portmap in the partType-1 extended table @ 0x7b4a8 +
  attr codes 107/108). Located; needs the Gowin EDA oracle to finalize offsets.
- Map the 10 `UNKNOWN_CFG_*` special-pin IO config codes; the OSCO oscillator ports.
- BRAM init-content round-trip; clock-spine/global-clock routing deep-dive.
