# reference/ — the validation target (NOT a build input)

> **Not redistributed.** `scope_bitstream_2c53t_v120.bin` is a byte-exact slice of
> FNIRSI's proprietary stock firmware, so it is **gitignored** (`reference/*.bin`)
> and not committed to this repo. Reproduce it locally from the recipe below; the
> sha256 lets you confirm an identical file:
>
> ```sh
> dd if=APP_2C53T_V1.2.0_251015.bin bs=1 skip=$((0x4AD19)) count=115638 \
>    of=reference/scope_bitstream_2c53t_v120.bin
> sha256sum reference/scope_bitstream_2c53t_v120.bin   # 5a0e7338…efd5c3b
> ```

## `scope_bitstream_2c53t_v120.bin`

- **What:** the FPGA configuration bitstream extracted from the FNIRSI 2C53T stock
  firmware `APP_2C53T_V1.2.0_251015.bin`, file offset `0x4AD19`, length 115,638 bytes.
- **sha256:** `5a0e73384e496bdb3b3d591b852bec2e806e70cbc71439c9829695324efd5c3b`
- **Provenance:** byte-exact slice of the stock APP binary; independently matched a
  Saleae logic-analyzer capture of a stock boot (the `0x3B … 0x3A` SPI3 upload).
  Full story in the `osc` repo: `reverse_engineering/captures/SPI3_STOCK_BOOT_CAPTURE_ANALYSIS.md`.

## Why it's here but not "used"

Building GW1N-2 support means **generating fresh bitstreams from Gowin's EDA tool
and diffing them**. This file is never fed into that process. It is the *goal*: the
day a GW1N-2 chipdb exists, step one is

```
python3 -m apycula.gowin_unpack -d GW1N-2 -o scope_fabric.txt <this file, converted to .fs>
```

and a clean unpack is how we know the chipdb is correct on a real-world design.

## Confirmed header facts (textbook Gowin)

| Offset | Bytes                 | Meaning                                  |
|--------|-----------------------|------------------------------------------|
| 0x00   | `FF × 22`             | preamble padding (22 bytes, 0x00–0x15)   |
| 0x16   | `A5 C3`               | Gowin sync word                          |
| 0x18   | `06 00 00 00 01 20 68 1b` | device-ID command → IDCODE `0x0120681B` |
| 0x40   | `3B 80 02 D2`         | frame-count command                      |

> Offsets re-verified 2026-06-13 against the actual file (a hexdump of the first
> 0x48 bytes). The sync word and device-ID command sit at **0x16 / 0x18**, not the
> 0x1D / 0x1E quoted in an earlier draft; the frame-count command at 0x40 is correct.
> The device-ID byte string `06 00 00 00 01 20 68 1b` matches the recognition branch
> staged in `tools/patches/0001-bslib-recognize-gw1n2.patch`.

## Format caveat for unpacking

Apicula's `gowin_unpack` reads the **ASCII `.fs`** text format (lines of `'0'`/`'1'`
chars + `//` comments), opened in text mode — feeding it this raw binary dies
immediately with `UnicodeDecodeError: … 0xff in position 0`. A binary→`.fs`
converter is needed first, and it must reconstruct the correct Gowin frame
widths/padding so the per-frame CRC-16 validates (those width/padding constants come
*from* the chipdb — another reason the chipdb has to exist first).
