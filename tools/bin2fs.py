#!/usr/bin/env python3
"""Convert a raw Gowin bitstream (.bin) into Apicula's ASCII .fs.

A Gowin .fs is just the bitstream bytes rendered MSB-first as '0'/'1', with a
newline at every command/frame boundary (see bslib.write_bitstream). The raw
.bin is the identical byte stream with no newlines. So converting is purely a
matter of re-inserting the boundaries:

    <each cmd in db.cmd_hdr on its own line>           (header, uncompressed)
    <each frame: frame_data + 2 CRC + 6 bytes 0xff>    x n_frames
    <each cmd in db.cmd_ftr on its own line>           (footer)

The header/footer command lengths come from the chipdb (db.cmd_hdr / cmd_ftr);
the frame count is read from the 0x3b command in the stream; the frame stride is
derived from (total - header - footer) / n_frames. Per-frame CRC-16 is already
correct in a real bitstream, so gowin_unpack's CRC asserts validate the result.

Only uncompressed streams are handled (the scope bitstream is uncompressed). If
the 0x10 command has the compress bit set we refuse, since framing would differ.

Usage: python3 bin2fs.py <in.bin> <out.fs> [-d GW1N-2]
"""
import argparse, os, sys
from apycula.chipdb import load_chipdb

_B2B = [f"{i:08b}" for i in range(256)]


def bin2fs(binpath, fspath, db):
    b = open(binpath, "rb").read()
    hdr_lens = [len(bytes(c)) for c in db.cmd_hdr]
    ftr_lens = [len(bytes(c)) for c in db.cmd_ftr]
    hdr_total = sum(hdr_lens)
    ftr_total = sum(ftr_lens)

    # sanity: sync word should sit where cmd_hdr puts it
    if b.find(b"\xa5\xc3") < 0:
        raise SystemExit("no a5c3 sync word found -- not a Gowin bitstream?")

    # slice the header per cmd_hdr lengths
    pos = 0
    header_lines = []
    for L in hdr_lens:
        header_lines.append(b[pos:pos + L])
        pos += L

    # frame count from the 0x3b command (last header command)
    fc = header_lines[-1]
    if fc[0] != 0x3b:
        raise SystemExit(f"expected 0x3b frame-count cmd at end of header, got {fc.hex()}")
    n_frames = int.from_bytes(fc[2:4], "big")

    # compression check (0x10 command, bit 13)
    for hl in header_lines:
        if hl and hl[0] == 0x10 and (int.from_bytes(hl, "big") & (1 << 13)):
            raise SystemExit("bitstream is compressed -- bin2fs only handles uncompressed")

    # derive frame stride
    body = len(b) - hdr_total - ftr_total
    if n_frames <= 0 or body % n_frames:
        raise SystemExit(f"body {body} not divisible by {n_frames} frames")
    stride = body // n_frames  # frame_data + 2 (crc) + 6 (0xff pad)

    frame_lines = []
    for i in range(n_frames):
        frame_lines.append(b[pos:pos + stride])
        pos += stride

    footer_lines = []
    for L in ftr_lens:
        footer_lines.append(b[pos:pos + L])
        pos += L

    assert pos == len(b), f"didn't consume whole file: {pos} != {len(b)}"

    with open(fspath, "w") as f:
        for ba in header_lines + frame_lines + footer_lines:
            f.write("".join(_B2B[x] for x in ba))
            f.write("\n")

    return dict(n_frames=n_frames, stride=stride, frame_data=stride - 8,
               hdr=hdr_total, ftr=ftr_total, total=len(b))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("binfile")
    ap.add_argument("fsfile")
    ap.add_argument("-d", "--device", default="GW1N-2")
    args = ap.parse_args()
    dbp = os.path.expanduser(f"~/gw1n2-apicula/tools/apicula/apycula/{args.device}.msgpack.xz")
    db = load_chipdb(dbp)
    info = bin2fs(args.binfile, args.fsfile, db)
    print("converted:", info)
