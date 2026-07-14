#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CONFIG="$ROOT_DIR/config.sh"
source "$CONFIG"

prompt_default() {
  local var_name=$1
  local prompt=$2
  local default=${3-}
  local current=${!var_name-}
  if [[ -n "$current" ]]; then return; fi
  local value
  if [[ -n "$default" ]]; then
    read -r -p "$prompt [$default]: " value
    value=${value:-$default}
  else
    read -r -p "$prompt: " value
  fi
  printf -v "$var_name" '%s' "$value"
}

if [[ -z "${INCIDENCE_MODE:-}" ]]; then
  echo "Select incidence-angle mode:"
  echo "  1) manual subswath preset"
  echo "  2) read incidence angles from Sentinel-1 SLC annotation XML"
  read -r -p "Mode [1/2]: " mode_choice
  case "$mode_choice" in
    1) INCIDENCE_MODE="manual" ;;
    2) INCIDENCE_MODE="xml" ;;
    *) echo "Invalid mode" >&2; exit 2 ;;
  esac
fi

prompt_default ASC_SUBSWATH "Ascending subswath (IW1/IW2/IW3)"
prompt_default DESC_SUBSWATH "Descending subswath (IW1/IW2/IW3)"
prompt_default POLARIZATION "Polarization" "VV"

if [[ "$INCIDENCE_MODE" == "xml" ]]; then
  prompt_default ASCENDING_SLC "Ascending SLC ZIP or .SAFE path"
  prompt_default DESCENDING_SLC "Descending SLC ZIP or .SAFE path"
fi

prompt_default VEL_A "Ascending LOS velocity (Vel_A)"
prompt_default VEL_D "Descending LOS velocity (Vel_D)"
prompt_default VELOCITY_UNIT "Velocity unit" "mm/year"
prompt_default LOS_POSITIVE "Positive LOS means toward or away" "toward"

# Export runtime values into a temporary config loaded by every stage.
RUNTIME_CONFIG=$(mktemp)
trap 'rm -f "$RUNTIME_CONFIG"' EXIT
cat > "$RUNTIME_CONFIG" <<EOF
INCIDENCE_MODE=$(printf '%q' "$INCIDENCE_MODE")
ASC_SUBSWATH=$(printf '%q' "$ASC_SUBSWATH")
DESC_SUBSWATH=$(printf '%q' "$DESC_SUBSWATH")
POLARIZATION=$(printf '%q' "$POLARIZATION")
ASCENDING_SLC=$(printf '%q' "${ASCENDING_SLC:-}")
DESCENDING_SLC=$(printf '%q' "${DESCENDING_SLC:-}")
VEL_A=$(printf '%q' "$VEL_A")
VEL_D=$(printf '%q' "$VEL_D")
VELOCITY_UNIT=$(printf '%q' "$VELOCITY_UNIT")
LOS_POSITIVE=$(printf '%q' "$LOS_POSITIVE")
OUTPUT_DIR=$(printf '%q' "$OUTPUT_DIR")
PYTHON_BIN=$(printf '%q' "$PYTHON_BIN")
EOF

# Stage scripts source config.sh, so run them with variables exported in environment.
export INCIDENCE_MODE ASC_SUBSWATH DESC_SUBSWATH POLARIZATION
export ASCENDING_SLC DESCENDING_SLC VEL_A VEL_D VELOCITY_UNIT LOS_POSITIVE
export OUTPUT_DIR PYTHON_BIN

# config.sh currently assigns defaults, so construct direct stage calls here to preserve prompts.
mkdir -p "$ROOT_DIR/$OUTPUT_DIR"
"$PYTHON_BIN" "$ROOT_DIR/pipeline.py" prepare \
  --incidence-mode "$INCIDENCE_MODE" --vlos-asc "$VEL_A" --vlos-desc "$VEL_D" \
  --unit "$VELOCITY_UNIT" --los-positive "$LOS_POSITIVE" \
  --asc-subswath "$ASC_SUBSWATH" --desc-subswath "$DESC_SUBSWATH" \
  --polarization "$POLARIZATION" \
  ${ASCENDING_SLC:+--ascending-slc "$ASCENDING_SLC"} \
  ${DESCENDING_SLC:+--descending-slc "$DESCENDING_SLC"} \
  --output "$ROOT_DIR/$OUTPUT_DIR/01_inputs.json"
"$PYTHON_BIN" "$ROOT_DIR/pipeline.py" geometry \
  --input "$ROOT_DIR/$OUTPUT_DIR/01_inputs.json" \
  --output "$ROOT_DIR/$OUTPUT_DIR/02_geometry.json"
"$PYTHON_BIN" "$ROOT_DIR/pipeline.py" coefficients \
  --input "$ROOT_DIR/$OUTPUT_DIR/02_geometry.json" \
  --output "$ROOT_DIR/$OUTPUT_DIR/03_coefficients.json"
"$PYTHON_BIN" "$ROOT_DIR/pipeline.py" decompose \
  --inputs "$ROOT_DIR/$OUTPUT_DIR/01_inputs.json" \
  --geometry "$ROOT_DIR/$OUTPUT_DIR/02_geometry.json" \
  --coefficients "$ROOT_DIR/$OUTPUT_DIR/03_coefficients.json" \
  --output "$ROOT_DIR/$OUTPUT_DIR/04_result.json"

echo
echo "All steps completed. Outputs are in: $ROOT_DIR/$OUTPUT_DIR"
