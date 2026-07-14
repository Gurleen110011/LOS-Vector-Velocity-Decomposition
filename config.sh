#!/usr/bin/env bash
# Non-interactive defaults. run_all.sh prompts when these are empty.

INCIDENCE_MODE=""          # manual or xml
ASC_SUBSWATH=""            # IW1, IW2, IW3
DESC_SUBSWATH=""           # IW1, IW2, IW3
POLARIZATION="VV"

# Required only in XML mode. ZIP or extracted .SAFE directories are accepted.
ASCENDING_SLC=""
DESCENDING_SLC=""

# Required for the current workflow.
VEL_A=""                    # Ascending LOS velocity
VEL_D=""                    # Descending LOS velocity
VELOCITY_UNIT="mm/year"
LOS_POSITIVE="toward"       # toward or away

OUTPUT_DIR="output"
PYTHON_BIN="python3"
