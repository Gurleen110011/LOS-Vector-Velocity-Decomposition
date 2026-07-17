#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT_DIR/config.sh"
"$PYTHON_BIN" "$ROOT_DIR/pipeline.py" coefficients \
  --input "$ROOT_DIR/$OUTPUT_DIR/02_geometry.json" \
  --output "$ROOT_DIR/$OUTPUT_DIR/03_coefficients.json"
echo "Step 3 complete: $OUTPUT_DIR/03_coefficients.json"
