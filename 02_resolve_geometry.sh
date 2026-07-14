#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT_DIR/config.sh"
"$PYTHON_BIN" "$ROOT_DIR/pipeline.py" geometry \
  --input "$ROOT_DIR/$OUTPUT_DIR/01_inputs.json" \
  --output "$ROOT_DIR/$OUTPUT_DIR/02_geometry.json"
echo "Step 2 complete: $OUTPUT_DIR/02_geometry.json"
