#!/usr/bin/env python3
"""
Augment KeFRA-style 512-point amplitude CSV files using 1D analogs of the
six image augmentations described in the ResNet50 KeFRA paper:

1. X-axis reflection      -> reverse time axis
2. Y-axis reflection      -> reflect amplitude around known graph limits or row midpoint
3. Rotation              -> small coordinate rotation of waveform, then resample
4. Rescaling             -> time/amplitude zoom around center
5. Horizontal translation -> time shift
6. Vertical translation   -> amplitude offset

By default this creates exactly 6 augmented rows per original row, matching the
paper's reported 340 -> 2040 expansion factor. Use --include-original if you
also want to keep the original rows in the output CSVs.

Expected input files by default:
    Kefra_Processed_Data/Real.csv
    Kefra_Processed_Data/Fake_High.csv
    Kefra_Processed_Data/Fake_Low.csv

Each CSV may contain a leading 'file' column followed by 512 amplitude columns.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def numeric_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c != "file"]


def resample_1d(y: np.ndarray, n: int) -> np.ndarray:
    old_x = np.linspace(0.0, 1.0, len(y))
    new_x = np.linspace(0.0, 1.0, n)
    return np.interp(new_x, old_x, y)


def horizontal_shift(y: np.ndarray, frac_shift: float) -> np.ndarray:
    n = len(y)
    x = np.arange(n, dtype=float)
    src_x = x - frac_shift * n
    return np.interp(src_x, x, y, left=y[0], right=y[-1])


def vertical_reflect(y: np.ndarray, y_top: float | None, y_bottom: float | None) -> np.ndarray:
    if y_top is not None and y_bottom is not None:
        center_twice = y_top + y_bottom
    else:
        center_twice = float(np.nanmin(y) + np.nanmax(y))
    return center_twice - y


def rotation_like_warp(y: np.ndarray, degrees: float) -> np.ndarray:
    """Approximate image rotation for a 1D plotted waveform."""
    n = len(y)
    x = np.linspace(-1.0, 1.0, n)
    ymin, ymax = float(np.nanmin(y)), float(np.nanmax(y))
    scale = ymax - ymin
    if scale < 1e-12:
        return y.copy()

    y_norm = 2.0 * (y - ymin) / scale - 1.0
    theta = np.deg2rad(degrees)

    xr = x * np.cos(theta) - y_norm * np.sin(theta)
    yr = x * np.sin(theta) + y_norm * np.cos(theta)

    order = np.argsort(xr)
    xr = xr[order]
    yr = yr[order]

    # Collapse duplicate/nonmonotonic x values by interpolation over sorted coordinates.
    target_x = np.linspace(max(-1.0, xr.min()), min(1.0, xr.max()), n)
    y_interp = np.interp(target_x, xr, yr, left=yr[0], right=yr[-1])
    y_out = (y_interp + 1.0) * 0.5 * scale + ymin
    return resample_1d(y_out, n)


def rescale_waveform(y: np.ndarray, x_scale: float, y_scale: float) -> np.ndarray:
    n = len(y)
    x = np.linspace(-1.0, 1.0, n)
    src_x = x / x_scale
    old_x = np.linspace(-1.0, 1.0, n)
    y_x_scaled = np.interp(src_x, old_x, y, left=y[0], right=y[-1])
    center = float(np.nanmean(y_x_scaled))
    return center + y_scale * (y_x_scaled - center)


def augment_one_row(
    y: np.ndarray,
    rng: np.random.Generator,
    y_top: float | None,
    y_bottom: float | None,
    rotation_degrees: float,
    scale_range: tuple[float, float],
    hshift_frac: float,
    vshift_value: float,
) -> list[tuple[str, np.ndarray]]:
    """Return the six paper-style augmentations for one amplitude vector."""
    rot = rng.uniform(-rotation_degrees, rotation_degrees)
    x_scale = rng.uniform(scale_range[0], scale_range[1])
    y_scale = rng.uniform(scale_range[0], scale_range[1])
    hshift = rng.uniform(-hshift_frac, hshift_frac)
    vshift = rng.uniform(-vshift_value, vshift_value)

    return [
        ("x_reflect", y[::-1].copy()),
        ("y_reflect", vertical_reflect(y, y_top, y_bottom)),
        ("rotation", rotation_like_warp(y, rot)),
        ("rescale", rescale_waveform(y, x_scale, y_scale)),
        ("h_translate", horizontal_shift(y, hshift)),
        ("v_translate", y + vshift),
    ]


def augment_csv(
    in_csv: Path,
    out_csv: Path,
    seed: int,
    include_original: bool,
    y_top: float | None,
    y_bottom: float | None,
    rotation_degrees: float,
    scale_range: tuple[float, float],
    hshift_frac: float,
    vshift_value: float,
) -> None:
    df = pd.read_csv(in_csv)
    cols = numeric_columns(df)
    X = df[cols].to_numpy(dtype=np.float32)
    rng = np.random.default_rng(seed)

    out_rows = []
    out_files = []

    for i, y in enumerate(X):
        source_name = str(df.loc[i, "file"]) if "file" in df.columns else f"row_{i:04d}"

        if include_original:
            out_rows.append(y.copy())
            out_files.append(f"{source_name}__original")

        for aug_name, aug_y in augment_one_row(
            y=y,
            rng=rng,
            y_top=y_top,
            y_bottom=y_bottom,
            rotation_degrees=rotation_degrees,
            scale_range=scale_range,
            hshift_frac=hshift_frac,
            vshift_value=vshift_value,
        ):
            out_rows.append(aug_y.astype(np.float32))
            out_files.append(f"{source_name}__aug_{aug_name}")

    out = pd.DataFrame(np.vstack(out_rows), columns=cols)
    out.insert(0, "file", out_files)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"{in_csv} -> {out_csv}: {len(df)} rows -> {len(out)} rows")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create paper-style augmented KeFRA CSV datasets.")
    parser.add_argument("--input-dir", default="Kefra_Processed_Data", help="Directory containing Real.csv, Fake_High.csv, Fake_Low.csv")
    parser.add_argument("--output-dir", default="Kefra_Augmented_Data", help="Directory for augmented CSVs")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--include-original", action="store_true", help="Keep original rows in addition to six augmentations")
    parser.add_argument("--y-top", type=float, default=-10.0, help="Top graph amplitude. Use with --y-bottom for Y reflection.")
    parser.add_argument("--y-bottom", type=float, default=-130.0, help="Bottom graph amplitude. Use with --y-top for Y reflection.")
    parser.add_argument("--no-fixed-y-limits", action="store_true", help="Reflect each row around its own min/max instead of fixed graph limits")
    parser.add_argument("--rotation-degrees", type=float, default=10.0)
    parser.add_argument("--scale-min", type=float, default=0.90)
    parser.add_argument("--scale-max", type=float, default=1.10)
    parser.add_argument("--hshift-frac", type=float, default=0.10, help="Max horizontal shift as fraction of sequence length")
    parser.add_argument("--vshift-value", type=float, default=5.0, help="Max vertical amplitude offset")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    in_dir = Path(args.input_dir)
    out_dir = Path(args.output_dir)

    y_top = None if args.no_fixed_y_limits else args.y_top
    y_bottom = None if args.no_fixed_y_limits else args.y_bottom

    files = {
        "Real.csv": args.seed + 0,
        "Fake_High.csv": args.seed + 1,
        "Fake_Low.csv": args.seed + 2,
    }

    for name, seed in files.items():
        in_csv = in_dir / name
        out_csv = out_dir / name
        if not in_csv.exists():
            raise FileNotFoundError(f"Missing input CSV: {in_csv}")
        augment_csv(
            in_csv=in_csv,
            out_csv=out_csv,
            seed=seed,
            include_original=args.include_original,
            y_top=y_top,
            y_bottom=y_bottom,
            rotation_degrees=args.rotation_degrees,
            scale_range=(args.scale_min, args.scale_max),
            hshift_frac=args.hshift_frac,
            vshift_value=args.vshift_value,
        )

    print("Done. Augmented CSVs are in:", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
