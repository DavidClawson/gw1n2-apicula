# Config-entry: register-level PROOF + a question for Apicula (from osc, 2026-06-13)

## Headline

We now have **direct register-level proof** of where the scope config fails, replacing
months of inference. On our 2C53T (GW1N-UV2, IDCODE 0x0120681B), replaying the stock
SSPI sequence from the MCU:

- **`CONFIG_ENABLE` (0x15) never engages `SYSTEM_EDIT_MODE` (status bit 7).**
- The Gowin STATUS register (0x41), read at /256 (the only clock where SSPI reads are
  valid on our bus — at /2 everything reads garbage), is **stable at `0x00039020`**:
  `MEMORY_ERASE | GOWIN_VLD | READY | POR | FLASH_LOCK`.
- **No `CRC_ERROR`, no `ID_VERIFY_FAILED`** — our bitstream is byte-correct (sha
  `5a0e7338…`, your CRC-validated image) and is **not rejected on content**; it's
  **ignored**, because the part never enters config-receive.

## What we ruled out (all bench-confirmed on our unit)

We instrumented our debug shell to sweep the handshake live and read the real status:

| Lever | Result |
|---|---|
| USART2 fully silent (UEN clear, no dvom/meter tasks, RX=0) | no change |
| Handshake clock /2, /4, /64 | no change (status identical) |
| Prelude framing (split / combined / merge) | no change |
| Trailing clocks after bitstream (0, 64, 200, 512) | no change |
| `0x3C` RELOAD before the prelude (software reconfig trigger) | **no change** |
| Read STATUS @ /256 immediately after `0x15` | `SYSTEM_EDIT_MODE` **never sets** |

The config controller is alive (IDCODE reads cleanly at /256). The bus, the bytes, the
framing, the clock are all fine. The single failing fact is: **CONFIG_ENABLE cannot put
this running, FLASH_LOCK'd, GOWIN_VLD NV design into edit mode from the MCU over SSPI.**

## Our reading

The part auto-boots its NV (meter) design in ~90µs and runs it with `FLASH_LOCK` set.
A locked, valid, running instant-on design appears to refuse SSPI SRAM-reconfig without a
hardware RECONFIG_N pulse or JTAG. maksidze measured RECONFIG_N never pulses on stock —
yet stock *does* reconfigure to scope (0x3A close → 0xF8). So either stock's part is in a
different pre-config state (not locked / not yet GOWIN_VLD), or there's an SSPI step that
clears the lock / forces edit mode that we haven't found.

## Questions for Apicula (netlist / bitstream side)

1. **In the unpacked stock `.fs` preamble / config words — is a security or flash-lock
   bit set?** Does the scope bitstream (or the NV meter image) configure the part such
   that `FLASH_LOCK` would be asserted, blocking SSPI reconfig?
2. **Is there a documented Gowin SSPI sequence to clear `FLASH_LOCK` or force
   `SYSTEM_EDIT_MODE` that does NOT write the NV flash?** (We will NOT write NV flash —
   it holds the only copy of the meter design.) i.e. is the lock SRAM-state or
   flash-resident?
3. **Does JTAG SRAM-load bypass this entirely?** Our expectation: JTAG config does not go
   through the SSPI `CONFIG_ENABLE`/`SYSTEM_EDIT_MODE` path, so a `-m` (SRAM) load over
   JTAG should configure the scope regardless of `FLASH_LOCK`. Please confirm from the
   programming model so we wire the FT232H with confidence.
4. **R1 ramp validator** — still the right tool for the JTAG bench (BSRAM_0/BSRAM_3 baked
   ramp → deterministic 0x04/0x05 readout). If you can pre-build it, we'll stage it.

## How we'd love help testing (if you can reach a board / sim)

The decisive discriminator: **read STATUS (0x41 @ /256) during a STOCK boot, around its
config window.** Does stock's part show `FLASH_LOCK` set, and does `SYSTEM_EDIT_MODE`
engage on stock's CONFIG_ENABLE? (We've asked maksidze too.) If stock engages edit mode
*with* the lock set → there's a software path we're missing. If stock's part isn't locked
at config time → the difference is FPGA pre-config state, and JTAG is the clean route.

Full bench detail: `osc/docs/fpga_stock_bringup_diff_plan.md` (Current State) and
`osc/reverse_engineering/analysis_v120/sibling_loader_config_diff.md`.
