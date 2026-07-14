#!/usr/bin/env bash
set -euo pipefail
python3 pipeline.py prepare --incidence-mode manual \
  --vlos-asc -0.0754646 --vlos-desc -0.0466162 \
  --unit mm/year --los-positive toward \
  --asc-subswath IW3 --desc-subswath IW2 --polarization VV \
  --output output/01_inputs.json
python3 pipeline.py geometry --input output/01_inputs.json --output output/02_geometry.json
python3 pipeline.py coefficients --input output/02_geometry.json --output output/03_coefficients.json
python3 pipeline.py decompose --inputs output/01_inputs.json --geometry output/02_geometry.json \
  --coefficients output/03_coefficients.json --output output/04_result.json
