Gowin's `.dat` files carry a `partType` field (offset `0x7b4a4`). `dat_parser`
handles partType 0 (1/2 series) and 2 (5 series) but raises on **partType 1**, the
format used by the GW1N-2 / GW1N-1P5 / GW1N-2B / GW1NR-2 / GW1NZR-2 family.

partType-1 files are byte-identical to partType-0 across the entire fixed-offset
region the parser reads (primitives, grid, portmap, IO) — they only *append* a
~33 KB extended table at `0x7b4a8`. This patch treats partType 1 like partType 0 (all
existing offset asserts pass) and reads the trailing table.

This alone unblocks the whole GW1N-2/1P5 family for downstream device work. It's a
standalone parser fix — no new device required to land it.

Part of #515.
