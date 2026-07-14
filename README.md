# Sentinel-1 LOS Velocity Decomposition Pipeline

A SNAP-free wrapper for the **final geometry and dual-pass vector-decomposition stage**.
It does not derive LOS velocity from raw SLC phase. For now, the user supplies
ascending LOS velocity (`Vel_A`) and descending LOS velocity (`Vel_D`).

## Modes

### Manual mode

Choose IW1, IW2, or IW3 separately for ascending and descending. The code uses
configurable nominal mean angles:

| Subswath | Default mean | Broad nominal interval |
|---|---:|---:|
| IW1 | 33.0° | 29–37° |
| IW2 | 39.0° | 35–43° |
| IW3 | 43.5° | 40–46° |

These are convenience approximations, not immutable mission constants. Exact
values vary within each product and across range. XML mode is preferred when
SLC products are available.

### XML mode

Provide one ascending and one descending original Sentinel-1 SLC ZIP or
extracted `.SAFE` directory, plus the requested subswath and polarization.

For each product the code:

1. finds `annotation/*-iwN-*-POL-*.xml` for the chosen subswath/polarization;
2. reads every `geolocationGridPoint`;
3. extracts valid `incidenceAngle` values;
4. reports mean, median, min, max, population standard deviation, and sample count;
5. uses the mean angle in the workbook-style decomposition.

The annotation values are ellipsoid incidence-angle tie points. The current
mean is a tie-point mean. A later pixel-wise implementation should interpolate
the grid to the LOS velocity raster instead of reducing it to one mean.

## Fixed headings

The requested representative headings are internal constants:

- ascending: -12.51°
- descending: -167.49°

Look azimuth is heading + 90° and normalized to -180..180.

## Formulas

For each pass:

- `theta = radians(look_azimuth)`
- `alpha = radians(mean_incidence)`
- `hlos = cos(alpha)`
- `elos = -sin(alpha) * sin(theta)`

The last expression is algebraically equivalent to the spreadsheet/paper form:

`cos(pi/2-alpha) * cos(3*pi/2-theta)`

The system solved is:

- `Vel_A = elos_A * V_EW + hlos_A * V_vertical`
- `Vel_D = elos_D * V_EW + hlos_D * V_vertical`

## Run interactively

```bash
chmod +x run_all.sh scripts/*.sh
./run_all.sh
```

## Run stages separately

Fill `config.sh`, then:

```bash
./scripts/01_prepare_inputs.sh
./scripts/02_resolve_geometry.sh
./scripts/03_compute_coefficients.sh
./scripts/04_decompose_velocity.sh
```

## Outputs

- `output/01_inputs.json`: normalized user inputs
- `output/02_geometry.json`: headings, look azimuths, incidence statistics, XML pass validation
- `output/03_coefficients.json`: theta, alpha, hlos, elos
- `output/04_result.json`: E-W velocity, vertical velocity, 2-D magnitude, direction, ratio, determinant, status

Direction convention:

- 0° = East
- 90° = Up
- 180° = West
- 270° = Down

Velocity signs:

- E-W positive = East; negative = West
- vertical positive = Up; negative = Down

## Requirements

Python 3.9+; standard library only.
