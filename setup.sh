#!/usr/bin/env bash
# setup.sh — bootstrap the GW1N-2 / Apicula dev environment on a Linux (Ubuntu) box.
#
# This is the runnable form of docs/01-environment-setup.md. It does the parts that
# DON'T need David: system deps, Apicula clone + editable install, OSS-CAD-Suite
# (yosys + nextpnr-himbaechel + apycula). It then VERIFIES the human-only pieces
# (Gowin EDA 1.9.10.03 via $GOWINHOME) and reports what's missing — see
# docs/05-needs-david.md.
#
# Safe to re-run (idempotent-ish). Run from the project root:  bash setup.sh
set -euo pipefail

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; BOLD=$'\033[1m'; NC=$'\033[0m'
ok()   { echo "${GREEN}✓${NC} $*"; }
warn() { echo "${YELLOW}!${NC} $*"; }
err()  { echo "${RED}✗${NC} $*"; }
hdr()  { echo; echo "${BOLD}== $* ==${NC}"; }

GW_VERSION="1.9.10.03"          # the Gowin EDA version Apicula pins (GWVERSION)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS="$PROJECT_ROOT/tools"
APICULA="$TOOLS/apicula"
OSSCAD="$TOOLS/oss-cad-suite"

# ---------------------------------------------------------------------------
hdr "0. Platform check"
if [[ "$(uname -s)" != "Linux" ]]; then
  err "This is $(uname -s), not Linux. The build/fuzz flow must run on Linux."
  err "Run this on David's Ubuntu server (or a Linux VM), not the Mac. Aborting."
  exit 1
fi
ARCH="$(uname -m)"
ok "Linux $ARCH"
if [[ "$ARCH" != "x86_64" ]]; then
  warn "Gowin EDA ships x86-64 Linux binaries; '$ARCH' may not run the vendor tools."
fi

# ---------------------------------------------------------------------------
hdr "1. System dependencies (apt)"
if command -v apt-get >/dev/null 2>&1; then
  SUDO=""; [[ "$(id -u)" -ne 0 ]] && SUDO="sudo"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y --no-install-recommends \
    git python3 python3-venv python3-pip build-essential \
    libfontconfig1 libgl1 ca-certificates curl xz-utils
  ok "apt packages installed"
else
  warn "no apt-get found; install git/python3/venv/pip/build-essential manually"
fi

# ---------------------------------------------------------------------------
hdr "2. Apicula (clone + editable install)"
mkdir -p "$TOOLS"
if [[ -d "$APICULA/.git" ]]; then
  ok "apicula already cloned at $APICULA"
else
  git clone https://github.com/YosysHQ/apicula "$APICULA"
  ok "apicula cloned"
fi
echo "   pinned vendor version (GWVERSION): $(cat "$APICULA/GWVERSION" 2>/dev/null || echo '?')  (expect $GW_VERSION)"
python3 -m venv "$APICULA/.venv"
# shellcheck disable=SC1091
source "$APICULA/.venv/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -e "$APICULA"
ok "apicula editable-installed into .venv ($(python3 -c 'import apycula,os;print(os.path.dirname(apycula.__file__))'))"

# ---------------------------------------------------------------------------
hdr "3. yosys + nextpnr-himbaechel (OSS-CAD-Suite)"
if [[ -d "$OSSCAD" ]]; then
  ok "oss-cad-suite already present at $OSSCAD"
else
  warn "OSS-CAD-Suite not present."
  echo "   Fetch the latest Linux x64 nightly from:"
  echo "     https://github.com/YosysHQ/oss-cad-suite-build/releases"
  echo "   then extract into $OSSCAD, e.g.:"
  echo "     curl -L -o /tmp/oss.tgz <asset-url>   # oss-cad-suite-linux-x64-YYYYMMDD.tgz"
  echo "     mkdir -p '$OSSCAD' && tar -xf /tmp/oss.tgz -C '$TOOLS'"
  echo "   (auto-download skipped: release asset URL is dated/not pinned here.)"
fi
[[ -f "$OSSCAD/environment" ]] && ok "source $OSSCAD/environment  # to get yosys + nextpnr-himbaechel on PATH"

# ---------------------------------------------------------------------------
hdr "4. Gowin EDA (the oracle) — NEEDS DAVID, verify only"
MISSING=0
if [[ -z "${GOWINHOME:-}" ]]; then
  err "\$GOWINHOME is not set."
  echo "   Install Gowin EDA Education $GW_VERSION, then: export GOWINHOME=/path/to/gowin"
  MISSING=1
else
  ok "\$GOWINHOME = $GOWINHOME"
  [[ -x "$GOWINHOME/IDE/bin/gw_sh" ]] && ok "gw_sh found" || { err "missing $GOWINHOME/IDE/bin/gw_sh"; MISSING=1; }
  [[ -f "$GOWINHOME/Programmer/bin/libfontconfig.so.1" ]] && ok "libfontconfig.so.1 found" \
    || { warn "missing $GOWINHOME/Programmer/bin/libfontconfig.so.1 (fuzzer LD_PRELOADs it)"; MISSING=1; }
  for d in GW1NZ-1 GW1N-2; do
    if [[ -f "$GOWINHOME/IDE/share/device/$d/$d.fse" ]]; then ok "vendor data for $d present"
    else err "missing vendor data: $GOWINHOME/IDE/share/device/$d/$d.fse"; MISSING=1; fi
  done
fi

# ---------------------------------------------------------------------------
hdr "Summary / next steps"
if [[ "$MISSING" -eq 0 && -n "${GOWINHOME:-}" ]]; then
  ok "Environment looks complete. Next: reproduce the template build (M0 gate):"
  echo "     source $APICULA/.venv/bin/activate"
  echo "     cd $APICULA && make apycula/GW1NZ-1.msgpack.xz"
else
  warn "Human-only blockers remain — see docs/05-needs-david.md:"
  echo "     • Install Gowin EDA Education $GW_VERSION and export \$GOWINHOME"
  echo "     • (if needed) fetch OSS-CAD-Suite into $OSSCAD"
  echo "   Re-run this script after that to verify, then run the M0 build above."
fi
