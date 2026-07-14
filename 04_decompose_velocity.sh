#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT_DIR/config.sh"
"$PYTHON_BIN" "$ROOT_DIR/pipeline.py" decompose \
  --inputs "$ROOT_DIR/$OUTPUT_DIR/01_inputs.json" \
  --geometry "$ROOT_DIR/$OUTPUT_DIR/02_geometry.json" \
  --coefficients "$ROOT_DIR/$OUTPUT_DIR/03_coefficients.json" \
  --output "$ROOT_DIR/$OUTPUT_DIR/04_result.json"
echo "Step 4 complete: $OUTPUT_DIR/04_result.json"
