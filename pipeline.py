#!/usr/bin/env python3
"""Sentinel-1 LOS velocity vector decomposition pipeline.

This module intentionally separates geometry selection/extraction from the
mathematical decomposition. It does not produce LOS velocity from raw SLC data;
Vel_A and Vel_D are supplied by the user for now.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

FIXED_HEADINGS_DEG = {
    "ascending": -12.51,
    "descending": -167.49,
}

# Nominal, configurable convenience values for manual mode. They are not
# mission constants. Exact incidence geometry must be read from each product.
SUBSWATH_PRESETS = {
    "IW1": {"mean_deg": 33.0, "nominal_range_deg": [29.0, 37.0]},
    "IW2": {"mean_deg": 39.0, "nominal_range_deg": [35.0, 43.0]},
    "IW3": {"mean_deg": 43.5, "nominal_range_deg": [40.0, 46.0]},
}


class PipelineError(RuntimeError):
    pass


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PipelineError(f"Missing input file: {path}") from exc


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def signed_angle(angle_deg: float) -> float:
    return ((angle_deg + 180.0) % 360.0) - 180.0


def normalize_subswath(value: str) -> str:
    swath = value.strip().upper()
    if swath not in SUBSWATH_PRESETS:
        raise PipelineError(f"Unsupported subswath {value!r}; choose IW1, IW2, or IW3")
    return swath


def normalize_polarization(value: str) -> str:
    pol = value.strip().upper()
    if pol not in {"VV", "VH", "HH", "HV"}:
        raise PipelineError(f"Unsupported polarization {value!r}")
    return pol


def annotation_filename_matches(name: str, subswath: str, polarization: str) -> bool:
    filename = Path(name).name.lower()
    return (
        filename.endswith(".xml")
        and f"-{subswath.lower()}-" in filename
        and re.search(rf"(?:^|[-_]){re.escape(polarization.lower())}(?:[-_.]|$)", filename)
        is not None
    )


def iter_product_files(product: Path, wanted) -> list[tuple[str, bytes]]:
    """Return files from a SAFE directory or original SAFE ZIP."""
    matches: list[tuple[str, bytes]] = []
    if product.is_dir():
        for path in product.rglob("*"):
            if path.is_file() and wanted(path.as_posix()):
                matches.append((path.as_posix(), path.read_bytes()))
        return matches

    if product.is_file() and zipfile.is_zipfile(product):
        with zipfile.ZipFile(product) as archive:
            for name in archive.namelist():
                if wanted(name):
                    matches.append((name, archive.read(name)))
        return matches

    raise PipelineError(f"Not a readable Sentinel-1 SAFE directory or ZIP: {product}")


def read_orbit_pass(product: Path) -> str | None:
    """Read ASCENDING/DESCENDING from manifest.safe when available."""
    files = iter_product_files(product, lambda n: Path(n).name.lower() == "manifest.safe")
    for _, blob in files:
        try:
            root = ET.fromstring(blob)
        except ET.ParseError:
            continue
        for elem in root.iter():
            if local_name(elem.tag).lower() in {"pass", "passdirection"} and elem.text:
                value = elem.text.strip().upper()
                if value in {"ASCENDING", "DESCENDING"}:
                    return value
    return None


def incidence_statistics_from_annotation(
    product: Path,
    subswath: str,
    polarization: str,
) -> dict:
    """Read ellipsoid incidence-angle tie points from SLC annotation XML.

    Sentinel-1 Level-1 SLC annotation contains a geolocationGrid. Every
    geolocationGridPoint includes image line/pixel, geographic coordinates, and
    incidenceAngle. This function selects the annotation matching the requested
    subswath and polarization and computes descriptive statistics over all valid
    incidence-angle tie points.

    The returned mean is a tie-point mean. It is appropriate for reproducing a
    workbook that uses one mean angle per pass. A future pixel-wise workflow
    should interpolate the tie-point grid onto the LOS velocity grid.
    """
    swath = normalize_subswath(subswath)
    pol = normalize_polarization(polarization)

    def wanted(name: str) -> bool:
        low = name.lower().replace("\\", "/")
        return (
            "/annotation/" in low
            and "/annotation/calibration/" not in low
            and annotation_filename_matches(name, swath, pol)
        )

    files = iter_product_files(product, wanted)
    if not files:
        raise PipelineError(
            f"No annotation XML found for {swath}/{pol} in {product}. "
            "Check the chosen subswath and polarization."
        )

    values: list[float] = []
    used_files: list[str] = []
    for name, blob in files:
        try:
            root = ET.fromstring(blob)
        except ET.ParseError as exc:
            raise PipelineError(f"Invalid XML in {name}: {exc}") from exc

        file_values: list[float] = []
        for point in root.iter():
            if local_name(point.tag) != "geolocationGridPoint":
                continue
            for child in point:
                if local_name(child.tag) == "incidenceAngle" and child.text:
                    try:
                        value = float(child.text.strip())
                    except ValueError:
                        break
                    if math.isfinite(value) and 0.0 < value < 90.0:
                        file_values.append(value)
                    break
        if file_values:
            used_files.append(name)
            values.extend(file_values)

    if not values:
        raise PipelineError(
            f"No valid incidenceAngle entries found in {swath}/{pol} annotation XML"
        )

    mean_value = statistics.fmean(values)
    median_value = statistics.median(values)
    std_value = statistics.pstdev(values) if len(values) > 1 else 0.0
    preset = SUBSWATH_PRESETS[swath]
    return {
        "source": "sentinel1_annotation_xml",
        "product": str(product),
        "subswath": swath,
        "polarization": pol,
        "mean_deg": mean_value,
        "median_deg": median_value,
        "min_deg": min(values),
        "max_deg": max(values),
        "std_deg": std_value,
        "sample_count": len(values),
        "annotation_files": used_files,
        "nominal_manual_preset_deg": preset["mean_deg"],
        "method": (
            "Arithmetic mean of valid incidenceAngle values from the selected "
            "SLC annotation geolocation-grid tie points."
        ),
    }


def manual_incidence(subswath: str) -> dict:
    swath = normalize_subswath(subswath)
    preset = SUBSWATH_PRESETS[swath]
    return {
        "source": "manual_subswath_preset",
        "subswath": swath,
        "mean_deg": preset["mean_deg"],
        "nominal_range_deg": preset["nominal_range_deg"],
        "method": (
            "Configurable nominal mean selected from subswath. "
            "Use XML mode when product-specific geometry is available."
        ),
    }


def resolve_incidence(mode: str, product: str | None, subswath: str, polarization: str) -> dict:
    if mode == "manual":
        return manual_incidence(subswath)
    if mode == "xml":
        if not product:
            raise PipelineError("XML mode requires both ascending and descending SLC paths")
        return incidence_statistics_from_annotation(Path(product), subswath, polarization)
    raise PipelineError(f"Unknown incidence mode: {mode}")


def geometry_coefficients(heading_deg: float, incidence_deg: float) -> dict:
    look_azimuth_deg = signed_angle(heading_deg + 90.0)
    theta_rad = math.radians(look_azimuth_deg)
    alpha_rad = math.radians(incidence_deg)
    hlos = math.cos(alpha_rad)
    # Equivalent to cos(pi/2-alpha) * cos(3*pi/2-theta)
    elos = -math.sin(alpha_rad) * math.sin(theta_rad)
    return {
        "heading_deg": heading_deg,
        "look_azimuth_deg": look_azimuth_deg,
        "theta_rad": theta_rad,
        "incidence_deg": incidence_deg,
        "alpha_rad": alpha_rad,
        "hlos": hlos,
        "elos": elos,
    }


def decompose(vlos_asc: float, vlos_desc: float, asc: dict, desc: dict) -> dict:
    ea, ha = float(asc["elos"]), float(asc["hlos"])
    ed, hd = float(desc["elos"]), float(desc["hlos"])
    determinant = ea * hd - ed * ha
    if abs(determinant) < 1e-10:
        raise PipelineError(
            "Ascending/descending geometry is singular or nearly singular; "
            "the decomposition cannot be solved reliably."
        )

    velocity_ew = (vlos_asc * hd - vlos_desc * ha) / determinant
    velocity_vertical = (ea * vlos_desc - ed * vlos_asc) / determinant
    magnitude = math.hypot(velocity_ew, velocity_vertical)
    direction_signed = math.degrees(math.atan2(velocity_vertical, velocity_ew))
    direction_360 = direction_signed % 360.0
    ratio = (
        abs(velocity_vertical) / abs(velocity_ew)
        if abs(velocity_ew) > 1e-15
        else math.inf
    )

    return {
        "velocity_east_west": velocity_ew,
        "velocity_vertical": velocity_vertical,
        "velocity_real_2d": magnitude,
        "velocity_direction_deg_from_east_ccw": direction_signed,
        "velocity_direction_deg_0_360": direction_360,
        "absolute_vertical_horizontal_ratio": ratio,
        "geometry_determinant": determinant,
        "east_west_sign": "positive=east, negative=west",
        "vertical_sign": "positive=up, negative=down",
        "direction_convention": (
            "0=east, 90=up, 180=west, 270=down in the East-West/vertical plane"
        ),
        "status": "ok" if abs(determinant) >= 0.05 else "warning_small_determinant",
    }


def command_prepare(args: argparse.Namespace) -> None:
    mode = args.incidence_mode.lower()
    if mode not in {"manual", "xml"}:
        raise PipelineError("incidence mode must be manual or xml")
    data = {
        "workflow": "dual_pass_los_decomposition",
        "incidence_mode": mode,
        "vlos_asc": args.vlos_asc,
        "vlos_desc": args.vlos_desc,
        "velocity_unit": args.unit,
        "los_positive_input": args.los_positive,
        "asc_subswath": normalize_subswath(args.asc_subswath),
        "desc_subswath": normalize_subswath(args.desc_subswath),
        "polarization": normalize_polarization(args.polarization),
        "ascending_slc": args.ascending_slc,
        "descending_slc": args.descending_slc,
    }
    save_json(args.output, data)


def command_geometry(args: argparse.Namespace) -> None:
    inputs = load_json(args.input)
    mode = inputs["incidence_mode"]

    asc_inc = resolve_incidence(
        mode, inputs.get("ascending_slc"), inputs["asc_subswath"], inputs["polarization"]
    )
    desc_inc = resolve_incidence(
        mode, inputs.get("descending_slc"), inputs["desc_subswath"], inputs["polarization"]
    )

    validation = {}
    if mode == "xml":
        asc_pass = read_orbit_pass(Path(inputs["ascending_slc"]))
        desc_pass = read_orbit_pass(Path(inputs["descending_slc"]))
        validation = {
            "ascending_manifest_pass": asc_pass,
            "descending_manifest_pass": desc_pass,
            "pass_validation": (
                "ok"
                if (asc_pass in {None, "ASCENDING"} and desc_pass in {None, "DESCENDING"})
                else "warning_product_pass_mismatch"
            ),
        }

    data = {
        "heading_policy": "fixed Sentinel-1 representative values requested by user",
        "fixed_headings_deg": FIXED_HEADINGS_DEG,
        "ascending": {
            "heading_deg": FIXED_HEADINGS_DEG["ascending"],
            "look_azimuth_deg": signed_angle(FIXED_HEADINGS_DEG["ascending"] + 90.0),
            "incidence": asc_inc,
        },
        "descending": {
            "heading_deg": FIXED_HEADINGS_DEG["descending"],
            "look_azimuth_deg": signed_angle(FIXED_HEADINGS_DEG["descending"] + 90.0),
            "incidence": desc_inc,
        },
        "validation": validation,
    }
    save_json(args.output, data)


def command_coefficients(args: argparse.Namespace) -> None:
    geometry = load_json(args.input)
    asc = geometry_coefficients(
        float(geometry["ascending"]["heading_deg"]),
        float(geometry["ascending"]["incidence"]["mean_deg"]),
    )
    desc = geometry_coefficients(
        float(geometry["descending"]["heading_deg"]),
        float(geometry["descending"]["incidence"]["mean_deg"]),
    )
    save_json(args.output, {"ascending": asc, "descending": desc})


def command_decompose(args: argparse.Namespace) -> None:
    inputs = load_json(args.inputs)
    coefficients = load_json(args.coefficients)
    geometry = load_json(args.geometry)

    va = float(inputs["vlos_asc"])
    vd = float(inputs["vlos_desc"])
    # Internal equations use the workbook/paper convention: positive toward sensor.
    if inputs["los_positive_input"] == "away":
        va, vd = -va, -vd

    result = decompose(va, vd, coefficients["ascending"], coefficients["descending"])
    output = {
        "inputs_used": {
            "vlos_asc_normalized_positive_toward": va,
            "vlos_desc_normalized_positive_toward": vd,
            "velocity_unit": inputs["velocity_unit"],
            "original_los_positive_convention": inputs["los_positive_input"],
        },
        "geometry_used": {
            "asc_subswath": inputs["asc_subswath"],
            "desc_subswath": inputs["desc_subswath"],
            "asc_incidence_deg": geometry["ascending"]["incidence"]["mean_deg"],
            "desc_incidence_deg": geometry["descending"]["incidence"]["mean_deg"],
            "asc_heading_deg": geometry["ascending"]["heading_deg"],
            "desc_heading_deg": geometry["descending"]["heading_deg"],
        },
        "coefficients": coefficients,
        "result": result,
    }
    save_json(args.output, output)

    unit = inputs["velocity_unit"]
    print("\nFINAL RESULT")
    print("------------")
    print(f"Ascending incidence : {output['geometry_used']['asc_incidence_deg']:.6f} deg")
    print(f"Descending incidence: {output['geometry_used']['desc_incidence_deg']:.6f} deg")
    print(f"East-West velocity  : {result['velocity_east_west']:.12g} {unit}")
    print(f"Vertical velocity   : {result['velocity_vertical']:.12g} {unit}")
    print(f"Real 2-D velocity   : {result['velocity_real_2d']:.12g} {unit}")
    print(
        "Direction           : "
        f"{result['velocity_direction_deg_from_east_ccw']:.6f} deg from East CCW"
    )
    print(f"Direction (0-360)   : {result['velocity_direction_deg_0_360']:.6f} deg")
    print(f"Status              : {result['status']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="Validate and save user inputs")
    p.add_argument("--incidence-mode", choices=["manual", "xml"], required=True)
    p.add_argument("--vlos-asc", type=float, required=True)
    p.add_argument("--vlos-desc", type=float, required=True)
    p.add_argument("--unit", default="mm/year")
    p.add_argument("--los-positive", choices=["toward", "away"], default="toward")
    p.add_argument("--asc-subswath", required=True)
    p.add_argument("--desc-subswath", required=True)
    p.add_argument("--polarization", default="VV")
    p.add_argument("--ascending-slc")
    p.add_argument("--descending-slc")
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(func=command_prepare)

    p = sub.add_parser("geometry", help="Resolve fixed headings and incidence angles")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(func=command_geometry)

    p = sub.add_parser("coefficients", help="Compute theta, alpha, hlos, and elos")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(func=command_coefficients)

    p = sub.add_parser("decompose", help="Compute E-W, vertical, magnitude, and direction")
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--geometry", type=Path, required=True)
    p.add_argument("--coefficients", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.set_defaults(func=command_decompose)

    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        args.func(args)
        return 0
    except PipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # defensive top-level error reporting for HPC jobs
        print(f"UNEXPECTED ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
