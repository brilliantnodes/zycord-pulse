#!/bin/bash
# Zycord Pulse: rebuild every data file from your own Zycord node (read-only).
#   tools/refresh.sh [RPC_URL] [WORK_DIR]
# Needs: a synced Zycord node with RPC (default http://127.0.0.1:9420), Python 3, and the pulsescan binary
# (build it from tools/pulsescan, see the README). The first run reads the whole chain; later runs read only new blocks.
set -euo pipefail
RPC=${1:-http://127.0.0.1:9420}
WORK=${2:-./pulse-work}
HERE=$(cd "$(dirname "$0")" && pwd); SITE=$(cd "$HERE/.." && pwd)
SCAN=${PULSESCAN:-$HERE/pulsescan/pulsescan}
mkdir -p "$WORK"
"$SCAN" -rpc "$RPC" -to 0 -out "$WORK" -rate 240 -max "${SCAN_MAX:-9h}"
python3 "$HERE/pulse_agg.py" "$WORK" > "$WORK/daily.json"
python3 "$HERE/export_now.py" "$RPC" > "$WORK/now.json"
python3 "$HERE/build_site_data.py" "$SITE/data/pulse.json" "$WORK/daily.json" "$WORK/now.json" "$SITE/data"
python3 "$HERE/market_build.py" "$SITE/data"
