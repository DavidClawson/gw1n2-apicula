Hi @yrabbit — I'd like to contribute support for the **Gowin GW1N-2** (IDCODE
`0x0120681B`; GW1N-UV2 family — 2304 LUT4, 4 BSRAM, 1 rPLL, no DSP). It's the FPGA in
the FNIRSI 2C53T scope. I have it building and unpacking the device's real stock
bitstream cleanly, and would be happy to upstream it as a few small PRs if you're
open to it. Is anyone mid-flight on GW1N-2?

Two things worth flagging up front:

1. The GW1N-2 die ships license-free in the Education edition only as **GW1N-1P5C**
   (same silicon — verified the synth emits IDCODE `0x0120681B`). So the device uses
   GW1N-1P5C vendor data.
2. The reason it was never finished: GW1N-2's `.dat` is **partType 1**, which
   `dat_parser` rejects. partType-1 files are identical to partType-0 in the parsed
   fixed-offset region and only append an extended table at `0x7b4a8`.

**Plan — stage as small PRs:**
1. partType-1 `.dat` support (standalone parser fix; unblocks the whole
   GW1N-2/1P5/2B/R-2/ZR-2 family).
2. device recognition + chipdb build.
3. pinout / IO config / OSC.

Plus a matching nextpnr PR (himbaechel/gowin) and an `examples/gw1n2/` blinky.

Validated end-to-end on the stock 2C53T bitstream: `gowin_unpack -d GW1N-2` decodes
it cleanly — 847 LUT4 / 879 FF / 192 ALU / 4 BSRAM / DDR I/O all read back.

**Known gaps, deferred to follow-ups (neither blocks unpacking):**
- the rPLL — its portmap lives in the partType-1 extended table, and it can't be
  validated because GW1N-1P5C exposes no rPLL synthesis resource in Gowin EDA (would
  need real GW1N-2 vendor data);
- ~10 special-pin IO config codes.

Happy to adjust the staging or naming to match how you'd prefer it.
