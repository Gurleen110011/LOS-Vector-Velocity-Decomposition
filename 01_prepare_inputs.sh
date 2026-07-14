#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$ROOT_DIR/config.sh"
mkdir -p "$ROOT_DIR/$OUTPUT_DIR"

"$PYTHON_BIN" "$ROOT_DIR/pipeline.py" prepare \
  --incidence-mode "$INCIDENCE_MODE" \
  --vlos-asc "$VEL_A" \
  --vlos-desc "$VEL_D" \
  --unit "$VELOCITY_UNIT" \
  --los-positive "$LOS_POSITIVE" \
  --asc-subswath "$ASC_SUBSWATH" \
  --desc-subswath "$DESC_SUBSWATH" \
  --polarization "$POLARIZATION" \
  ${ASCENDING_SLC:+--ascending-slc "$ASCENDING_SLC"} \
  ${DESCENDING_SLC:+--descending-slc "$DESCENDING_SLC"} \
  --output "$ROOT_DIR/$OUTPUT_DIR/01_inputs.json"

echo "Step 1 complete: $OUTPUT_DIR/01_inputs.json"
