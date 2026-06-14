# GW1N-2 / Apicula — contribution backlog

> Running list of upstream contributions & loose ends we've discussed. Starting point
> for picking work back up after a context compact. Last updated **2026-06-13**.
> Companion to `docs/06-progress-log.md` (full history) and the `[[gw1n2-bringup-status]]`
> + `[[osc-collab-requests]]` memories.

---

## In flight right now (upstream PRs)

| PR | Repo | What | Status |
|----|------|------|--------|
| [#516](https://github.com/YosysHQ/apicula/pull/516) | apicula | `dat_parser`: partType-1 `.dat` | ✅ **MERGED** |
| [#517](https://github.com/YosysHQ/apicula/pull/517) | apicula | recognize device + build chipdb (incl. GSR@`[0,1]` fix from review) | OPEN, mergeable |
| [#518](https://github.com/YosysHQ/apicula/pull/518) | apicula | pinout, IO config, OSC (stacked on #517) | OPEN, mergeable |
| [#1735](https://github.com/YosysHQ/nextpnr/pull/1735) | nextpnr | `[himbaechel/gowin]` Add GW1N-2 device | OPEN, no review yet |

When review comes in: edit in `~/gh-prs/{apicula,nextpnr}`, commit, `git push --force-with-lease`.
Fork clones live there; staged source patches in `tools/patches/staged/`.

---

## Backlog

### A. Finish the GW1N-2 set (lands with / right after the PRs)

1. **`examples/gw1n2/` blinky + `toolchain.yml` CI matrix entry** — *queued, trivial, timing-gated.*
   Files built & validated in `tools/patches/staged/examples-gw1n2/`. **Send only after**
   nextpnr#1735 merges **and** apicula bumps its pinned nextpnr commit — otherwise example
   CI builds against a nextpnr that doesn't know GW1N-2 and goes red. Matrix entry:
   `{target: gw1n2, dir: examples/gw1n2}`. Coordinate timing + board/part naming with yrabbit.

2. **Map the ~10 `UNKNOWN_CFG_*` special-pin IO codes** — ✅ **mostly done (2026-06-13).**
   Resolved 5/10 by cross-device vendor cross-reference (NO oracle/fuzz needed — `_io_cfg`
   is a global enumeration, so codes unlabelled on QFN48XF are labelled on bigger packages
   of other devices): `75`→LPLL_T_IN, `136`→MCLK/D4, `153`→MO/D6, `154`→MI/D7, `160`→MCS_N/D5.
   Method validated 27/0 vs known `_io_cfg`. Tool `tools/m_iocfg_mine.py`; write-up
   `docs/IO-CFG-CODES-FINDINGS.md`. The other 5 (43/44/45/46 @ IOR3A/B,IOR4A/B; 141 @ IOB12A)
   have no package label anywhere available → kept as honest `UNKNOWN_CFG` (all unbonded on
   QFN48XF; would need the datasheet pin table). Folded into PR3 #518 (local commit on
   `gw1n2-io`, **not pushed** — David to review+force-push); staged `03`/consolidated/`pr3-io.md`
   regenerated.

3. **OSCO oscillator port map** — *moderate; needs mars + oracle.*
   PR3 ships an empty `('OSCO','GW1N-2')` stub. Fuzz the OSC primitive to fill the real portmap.

### B. New contributions we've prototyped

4. **BSRAM init-content decode for `gowin_unpack`** — *core built & verified; integration is medium.*
   `tools/bsram_init_decode.py` inverts `gowin_pack.store_bsram_init_val` to recover BRAM
   memory contents. Self-test round-trips **both** width modes (256 / 288=X9) against
   apicula's real encoder; end-to-end verified (pulled the ramp/marker back out of the R1
   validator; stock reads all-zero). **Two catches before a clean PR:** (a) a proper
   `gowin_unpack` *core* feature also needs BRAM **width/subtype config-decode** (unpack
   currently recovers only CSA/SPA bel attrs, not BIT_WIDTH/SUBTYPE); (b) a cosmetic
   off-by-one in the **288/X9 byte view** (canonical INIT_RAM bitstrings are correct).
   **Recommended:** float to yrabbit first — "want it as a `gowin_unpack` feature (needs
   width-config decode) or a standalone extract tool?" — before building a speculative PR.
   Decoder is already useful to us (can dump scope BRAM contents once osc captures real data).

### C. Frontier / blocked

5. **rPLL decode** — *high value, hard, blocked.* The one real GW1N-2 gap. The license-free
   GW1N-1P5C proxy exposes **no rPLL** to fuzz against; the portmap lives in the partType-1
   extended table @ `0x7b4a8`. Needs real GW1N-2 vendor data (a Standard Gowin license) or
   painstaking multi-bitstream RE. PRs ship it as a documented TODO. Parked.

### D. Community goodwill (low effort, builds standing with yrabbit)

6. **Answer open apicula issues in our wheelhouse** — we now have deep config-entry/SSPI
   (UG290), BRAM, pinout, and GSR knowledge. Candidates touch rPLL config (#409, #427),
   IOBUF (#507), SDRAM pins (#506). #436 ("Requesting GW1N-UV1P5") is effectively answered
   by our PRs — could close the loop there once they merge.

---

## Assets & techniques (so a fresh session can move fast)

- **Gowin oracle diff-fuzz:** `tools/fuzz.py` (`synth()` runs `gw_sh` for a partnumber →
  `.fs`; `diff()`/`bitmap()`). Env: `source tools/gowin-env.sh` on mars (sets `GOWINHOME`,
  `QT_QPA_PLATFORM=offscreen`, `GOWIN_LD_PRELOAD=libfreetype`). Gowin EDA:
  `~/gowin/V1.9.11.03_Education/IDE/bin/gw_sh`. Partnumber `GW1N-UV1P5QN48XFC7/I6`.
- **Locating a bel/wire (used for the GSR fix):** diff-fuzz feature-on vs -off; run with the
  signal on **two different pins** and intersect changed tiles → isolates the cell from
  routing; match the invariant changed fuses against `db[r,c].pips` → the destination wire.
- **chipdb rebuild:** `python -m apycula.chipdb_builder GW1N-2` (needs gowin-env). nextpnr
  chipdb regen + from-source build documented in `docs/06` / `tools/roundtrip/`.
- **mars** = `david@mars.local`; apicula venv at `~/gw1n2-apicula/tools/apicula/.venv`
  (has msgspec/numpy; system python3 lacks msgpack). Chipdb `GW1N-2.msgpack.xz` built there.

## Hard constraints (don't forget)
- osc hardware: **SRAM load only** (`openFPGALoader -m`); **never** flash (`-f` etc.) — the
  FPGA's NV flash holds the only copy of the meter design.
- osc repo writes: **new files only**, never modify their code/docs, never commit.
- This repo: keep tooling in `tools/`, notes in `docs/`, don't pollute `reference/`,
  don't `git init`/commit unless asked. Public GitHub actions under David's account need
  explicit go-ahead.
