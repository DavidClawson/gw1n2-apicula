#!/usr/bin/env python3
"""Mine the vendor cfg_code -> special-function name map across all supported devices.

Background
----------
`apycula.chipdb.dat_fill_io_cfgs` labels each IOB with its special function
(clock input, PLL feedback, config pin, ...) via a per-pin integer `cfg_code`
read from the vendor `.dat` (`compat_dict['Cfg']` / `['SpecCfg']`). The hand-
maintained `_io_cfg` dict turns those codes into names. For GW1N-2 a handful of
codes (45 @ IOR3A, etc.) aren't in `_io_cfg`, so the build emits `UNKNOWN_CFG_<n>`.

These codes are a *global* enumeration (one shared `_io_cfg` for every non-GW5
device), so a code that's unlabelled on GW1N-2's tiny QFN48 package is very
often bonded out *with* a package label on a bigger package of another device.

This probe reuses apicula's exact build path: it monkeypatches
`dat_fill_io_cfgs` to record `(device, pin, cfg_code, package_label)` for every
IOB, then aborts the (slow) rest of the build with a sentinel. Running it for
each minable device yields an empirical inverse of `_io_cfg`. We then:
  1. validate it reproduces the known `_io_cfg` entries (no contradictions),
  2. read off names for the GW1N-2 unknown codes.

No Gowin oracle / synthesis needed — pure vendor-data cross-reference.

Run on mars inside the apicula venv with gowin-env.sh sourced.
"""
import sys
from collections import defaultdict

from apycula import chipdb, chipdb_builder

# Devices whose vendor folder is present in the Education install AND which use
# the GW1N/GW2A (non-GW5) cfg path that shares the global `_io_cfg`.
MINE_DEVICES = ["GW1N-2", "GW1NZ-1", "GW1NS-4", "GW1N-9C", "GW2A-18C"]

RECORDS = []  # (device, io_name, cfg_code, package_label_tuple_or_None)


class _StopMining(Exception):
    pass


_orig_loc2pin = chipdb.loc2pin_name


def _collect(db, dat, device, pindesc):
    """Drop-in for dat_fill_io_cfgs: record every IOB's (cfg_code, package_cfg)."""
    cfg_dict = dat.compat_dict['Cfg']
    if device in {'GW5AST-138C'}:
        cfg_dict = dat.compat_dict['Cfg5']
    pkg_pins = {p[0]: p[1] for p in pindesc.values()}
    for row in range(db.rows):
        for col in range(db.cols):
            rc = db[row, col]
            for name, bel in rc.bels.items():
                if not name.startswith('IOB'):
                    continue
                iob_idx = name[-1]
                io_name = _orig_loc2pin(db, row, col) + iob_idx
                side = io_name[2]
                package_cfg = pkg_pins.get(io_name, None)
                if bel.simplified_iob:
                    cfg_code = dat.compat_dict['SpecCfg'][f'IO{side}'][ord(iob_idx) - ord('A')]
                else:
                    idx = col + 1 if side in 'TB' else row + 1
                    cfg_code = cfg_dict[side + iob_idx][idx]
                RECORDS.append((device, io_name, int(cfg_code),
                                tuple(package_cfg) if package_cfg else None))
    raise _StopMining


def mine_one(device):
    chipdb.dat_fill_io_cfgs = _collect
    sys.argv = ["chipdb_builder", device]
    try:
        chipdb_builder.main()
    except _StopMining:
        return True
    except SystemExit:
        raise
    except Exception as e:
        print(f"  !! {device}: build failed before io-cfg fill: {type(e).__name__}: {e}")
        return False
    print(f"  !! {device}: dat_fill_io_cfgs never called?")
    return False


def main():
    for dev in MINE_DEVICES:
        print(f"[mine] {dev} ...", flush=True)
        mine_one(dev)
    print(f"\nCollected {len(RECORDS)} IOB records across {len(MINE_DEVICES)} devices.\n")

    # Build the empirical inverse: cfg_code -> {label_tuple -> [devices/pins]}
    code2labels = defaultdict(lambda: defaultdict(list))
    for dev, pin, code, label in RECORDS:
        if label is not None:
            code2labels[code][label].append(f"{dev}:{pin}")

    # --- Validate against the known _io_cfg ---
    known = chipdb._io_cfg
    print("=== Validation vs known _io_cfg (mined label must contain the known name) ===")
    agree = contradict = 0
    for code, names in sorted(known.items()):
        mined = code2labels.get(code)
        if not mined:
            print(f"  code {code:>3} {names}: (no package label in mined corpus)")
            continue
        mined_names = set()
        for lab in mined:
            mined_names.update(lab)
        ok = any(n in mined_names for n in names)
        flag = "OK " if ok else "!! "
        if ok:
            agree += 1
        else:
            contradict += 1
        print(f"  {flag}code {code:>3} known={names} mined={sorted(mined_names)}")
    print(f"\n  validation: {agree} agree, {contradict} disagree\n")

    # --- GW1N-2: the TRUE unknown emitters ---
    # A code only emits UNKNOWN_CFG_<n> when the GW1N-2 pin has NO package label
    # (otherwise dat_fill keeps the label and never consults _io_cfg). So filter
    # GW1N-2 records to (package_label is None) and (code not in _io_cfg).
    print("=== GW1N-2 TRUE UNKNOWN_CFG emitters (no pkg label, code not in _io_cfg) ===")
    true_unknown = []  # (code, pin)
    for dev, pin, code, label in RECORDS:
        if dev == "GW1N-2" and code and code not in known and label is None:
            true_unknown.append((code, pin))
    resolved = []
    stragglers = []
    for code, pin in sorted(true_unknown):
        mined = code2labels.get(code)
        # only labels from OTHER devices count (GW1N-2 itself had none here)
        other = {}
        for lab, where in (mined or {}).items():
            ext = [w for w in where if not w.startswith("GW1N-2:")]
            if ext:
                other[lab] = ext
        if other:
            names = sorted({n for lab in other for n in lab})
            src = sorted({w for ws in other.values() for w in ws})
            print(f"  code {code:>3} @ {pin:<7} -> {names}   (from {', '.join(src[:6])})")
            resolved.append((code, pin, names, src))
        else:
            print(f"  code {code:>3} @ {pin:<7} -> ??? no external label (oracle/positional)")
            stragglers.append((code, pin))
    print(f"\n  {len(resolved)} resolvable by mining, {len(stragglers)} stragglers\n")

    print("=== Suggested _io_cfg additions ===")
    for code, pin, names, src in resolved:
        print(f"    {code}: {names},   # {pin} (GW1N-2); seen labelled at {src[0]}")
    print("\n=== Stragglers (genuinely unlabelled anywhere) ===")
    for code, pin in stragglers:
        print(f"    code {code} @ {pin}")


if __name__ == "__main__":
    main()
