# Source this before running the Apicula chipdb build / fuzzer on mars.
#   source ~/gw1n2-apicula/tools/gowin-env.sh
#
# Sets up the Gowin EDA "oracle" (gw_sh) for headless use on Ubuntu 24.04.
# Background in docs/01-environment-setup.md and the [[gowin-eda-install-mars]] memory.

# Install root of the license-free Education edition (contains IDE/ and Programmer/).
export GOWINHOME="${GOWINHOME:-$HOME/gowin/V1.9.11.03_Education}"

# gw_sh pulls in Qt5; on a headless box force the offscreen platform plugin.
export QT_QPA_PLATFORM=offscreen

# The bundled 2019 libs are too old for Ubuntu 24.04. Preload the *system* libfreetype
# so the system libfontconfig (needed by Qt5WebEngine) resolves. apycula/codegen.py
# reads $GOWIN_LD_PRELOAD and passes it to gw_sh instead of the bundled libfontconfig.
export GOWIN_LD_PRELOAD="$(ldconfig -p | grep -m1 'libfreetype.so.6' | awk '{print $NF}')"

echo "gowin-env: GOWINHOME=$GOWINHOME  QT_QPA_PLATFORM=$QT_QPA_PLATFORM  GOWIN_LD_PRELOAD=$GOWIN_LD_PRELOAD"
