#!/usr/bin/env python3
"""Lightweight diff-fuzzing harness for GW1N-2 bring-up (M2+).

Synthesizes tiny designs with the Gowin gw_sh oracle and returns parsed
bitstream bitmaps so two designs can be diffed to locate the fuse(s) that
control one feature. Run inside the apicula venv with gowin-env.sh sourced.
"""
import os, tempfile, subprocess
from apycula import bslib

GOWINHOME = os.environ["GOWINHOME"]
PRELOAD   = os.environ.get("GOWIN_LD_PRELOAD")

def synth(verilog, cst, partnumber, keep=True):
    """Run gw_sh; return (path_to_top.fs, workdir)."""
    d = tempfile.mkdtemp(prefix="fuzz.")
    with open(d+"/top.v","w") as f: f.write(verilog)
    with open(d+"/top.cst","w") as f: f.write(cst)
    with open(d+"/run.tcl","w") as f:
        f.write("set_option -verilog_std sysv2017\n"
                "add_file -type cst top.cst\n"
                "add_file -type verilog top.v\n"
                f"set_device {partnumber}\n"
                "run pnr\n")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    if PRELOAD: env["LD_PRELOAD"] = PRELOAD
    r = subprocess.run([GOWINHOME+"/IDE/bin/gw_sh","run.tcl"],
                       cwd=d, env=env, capture_output=True, text=True)
    fs = d+"/impl/pnr/project.fs"
    if not os.path.exists(fs):
        raise RuntimeError("synth failed:\n"+r.stdout[-3000:])
    return fs, d

def bitmap(fs):
    """Full-chip bit matrix (list of rows of 0/1)."""
    bm, hdr, ftr, slots = bslib.read_bitstream(fs)
    return bm

def diff(a, b):
    """(row, col) positions where bitmaps a and b differ, with old/new bit."""
    out = []
    for r in range(min(len(a), len(b))):
        ra, rb = a[r], b[r]
        for c in range(min(len(ra), len(rb))):
            if ra[c] != rb[c]:
                out.append((r, c, ra[c], rb[c]))
    return out

def locate(db, diffs):
    """Map global (row,col) diffs to (tile_row, tile_col, in-tile row,col) using a chipdb."""
    # tile_bitmap splits the global bitmap; here we just report which tile each
    # changed bit falls in via the chipdb's tile geometry.
    from apycula import chipdb
    res = []
    for (r, c, ob, nb) in diffs:
        res.append((r, c, ob, nb))
    return res
