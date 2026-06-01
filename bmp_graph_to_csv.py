#!/usr/bin/env python3
"""
Convert BMP waveform-graph images into one CSV row per image.

Each output row contains one extracted amplitude sequence:
    file, amp_0000, amp_0001, ..., amp_NNNN

The first column keeps the source filename for traceability. Use
--no-file-column if you want only numeric amplitude columns.

This script is tuned for images like the provided BMP:
- black waveform/grid on a white background
- a fixed y-axis amplitude scale, default -10 at the top and -130 at the bottom
- constant time spacing, so only amplitude values are exported

Requirements:
    pip install pillow numpy

Examples:
    python bmp_graph_to_csv.py unlockFSH_433_427_40_001.bmp --out data.csv
    python bmp_graph_to_csv.py "*.bmp" --out data.csv
    python bmp_graph_to_csv.py "*.bmp" --out data.csv --points 1800
"""

from __future__ import annotations

import argparse
import csv
import glob
import sys
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np
from PIL import Image


BBox = Tuple[int, int, int, int]  # left, top, right, bottom, inclusive pixel bounds


def expand_inputs(patterns: Sequence[str]) -> list[Path]:
    """Expand file and glob patterns while preserving sorted order and removing duplicates."""
    files: list[Path] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            files.extend(Path(m) for m in matches)
        else:
            files.append(Path(pattern))

    seen = set()
    unique: list[Path] = []
    for p in files:
        rp = p.resolve()
        if rp not in seen:
            unique.append(p)
            seen.add(rp)
    return unique


def parse_bbox(text: Optional[str]) -> Optional[BBox]:
    """Parse 'left,top,right,bottom' into a bounding box."""
    if not text:
        return None
    try:
        parts = [int(x.strip()) for x in text.split(",")]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--bbox must be left,top,right,bottom") from exc
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("--bbox must be left,top,right,bottom")
    left, top, right, bottom = parts
    if not (left < right and top < bottom):
        raise argparse.ArgumentTypeError("--bbox values must satisfy left < right and top < bottom")
    return left, top, right, bottom


def load_dark_mask(image_path: Path, dark_threshold: int) -> tuple[np.ndarray, np.ndarray]:
    """Return RGB image array and a boolean mask for dark pixels."""
    img = Image.open(image_path).convert("RGB")
    arr = np.asarray(img)
    gray = arr.mean(axis=2)
    dark = gray <= dark_threshold
    return arr, dark


def longest_true_run(mask_1d: np.ndarray) -> tuple[int, int, int]:
    """Return (length, start, end) for the longest continuous True run in a 1D mask."""
    best_len = 0
    best_start = 0
    best_end = -1
    cur_start: Optional[int] = None

    for i, value in enumerate(mask_1d):
        if value:
            if cur_start is None:
                cur_start = i
            cur_len = i - cur_start + 1
            if cur_len > best_len:
                best_len = cur_len
                best_start = cur_start
                best_end = i
        else:
            cur_start = None

    return best_len, best_start, best_end


def auto_detect_plot_bbox(dark: np.ndarray) -> BBox:
    """
    Detect the plotting rectangle from long, continuous grid/border lines.

    This is more reliable than simply counting dark pixels because the waveform
    itself can contain dense dark bands.
    """
    height, width = dark.shape

    row_runs: list[tuple[int, int, int, int]] = []
    for y in range(height):
        run_len, start, end = longest_true_run(dark[y, :])
        row_runs.append((run_len, y, start, end))

    max_row_run = max(r[0] for r in row_runs)
    if max_row_run < max(50, int(width * 0.20)):
        raise RuntimeError(
            "Could not auto-detect horizontal plot/grid lines. "
            "Try --threshold 120 or pass --bbox left,top,right,bottom."
        )

    # Full horizontal grid lines have the maximum continuous run.
    row_candidates = [r for r in row_runs if r[0] >= 0.90 * max_row_run]
    top = min(r[1] for r in row_candidates)
    bottom = max(r[1] for r in row_candidates)
    left_from_rows = int(round(float(np.median([r[2] for r in row_candidates]))))
    right_from_rows = int(round(float(np.median([r[3] for r in row_candidates]))))

    col_runs: list[tuple[int, int, int, int]] = []
    for x in range(width):
        run_len, start, end = longest_true_run(dark[:, x])
        col_runs.append((run_len, x, start, end))

    max_col_run = max(c[0] for c in col_runs)
    if max_col_run < max(50, int((bottom - top + 1) * 0.40)):
        left, right = left_from_rows, right_from_rows
    else:
        col_candidates = [c for c in col_runs if c[0] >= 0.90 * max_col_run]
        # Prefer vertical lines that span the same y range as the horizontal grid.
        close = [c for c in col_candidates if abs(c[2] - top) <= 3 and abs(c[3] - bottom) <= 3]
        if not close:
            close = col_candidates
        left = min(c[1] for c in close)
        right = max(c[1] for c in close)
        top = int(round(float(np.median([c[2] for c in close]))))
        bottom = int(round(float(np.median([c[3] for c in close]))))

    # The row-derived x coordinates are a useful sanity check/fallback.
    if right - left < 0.8 * (right_from_rows - left_from_rows):
        left, right = left_from_rows, right_from_rows

    if not (0 <= left < right < width and 0 <= top < bottom < height):
        raise RuntimeError(f"Detected invalid plot box: {(left, top, right, bottom)}")

    return int(left), int(top), int(right), int(bottom)


def remove_grid_lines(crop_dark: np.ndarray) -> np.ndarray:
    """
    Remove long continuous horizontal/vertical grid lines from a cropped plot mask.

    The waveform may be dense, so we remove only nearly full-length continuous
    lines, not rows/columns that merely contain many dark pixels.
    """
    h, w = crop_dark.shape
    cleaned = crop_dark.copy()

    for y in range(h):
        run_len, start, end = longest_true_run(crop_dark[y, :])
        if run_len >= 0.90 * w and start <= 2 and end >= w - 3:
            cleaned[y, :] = False

    for x in range(w):
        run_len, start, end = longest_true_run(crop_dark[:, x])
        if run_len >= 0.90 * h and start <= 2 and end >= h - 3:
            cleaned[:, x] = False

    return cleaned


def choose_y(ys: np.ndarray, method: str) -> float:
    """Choose one y-position from all remaining trace pixels in one x-column."""
    if method == "top":
        return float(np.min(ys))
    if method == "bottom":
        return float(np.max(ys))
    if method == "center":
        return float((np.min(ys) + np.max(ys)) / 2.0)
    if method == "median":
        return float(np.median(ys))
    if method == "mean":
        return float(np.mean(ys))
    raise ValueError(f"Unknown method: {method}")


def interpolate_nans(values: np.ndarray) -> np.ndarray:
    """Fill missing values by linear interpolation; extend edge values if needed."""
    values = values.astype(float, copy=True)
    x = np.arange(len(values))
    good = np.isfinite(values)
    if good.sum() == 0:
        raise RuntimeError("No waveform pixels were detected after grid removal.")
    if good.sum() == 1:
        values[~good] = values[good][0]
        return values
    values[~good] = np.interp(x[~good], x[good], values[good])
    return values


def resample(values: np.ndarray, n_points: int) -> np.ndarray:
    """Linearly resample a 1D vector to n_points."""
    if n_points <= 1:
        raise ValueError("--points must be greater than 1")
    if len(values) == n_points:
        return values
    old_x = np.linspace(0.0, 1.0, len(values))
    new_x = np.linspace(0.0, 1.0, n_points)
    return np.interp(new_x, old_x, values)


def extract_amplitudes(
    image_path: Path,
    y_top_value: float,
    y_bottom_value: float,
    dark_threshold: int,
    method: str,
    bbox: Optional[BBox] = None,
    n_points: Optional[int] = None,
) -> tuple[np.ndarray, BBox]:
    """Extract one amplitude vector from one graph image."""
    _, dark = load_dark_mask(image_path, dark_threshold)

    if bbox is None:
        bbox = auto_detect_plot_bbox(dark)

    left, top, right, bottom = bbox
    crop_dark = dark[top : bottom + 1, left : right + 1]
    cleaned = remove_grid_lines(crop_dark)

    h, w = cleaned.shape
    y_pixels = np.full(w, np.nan, dtype=float)

    for x in range(w):
        ys = np.where(cleaned[:, x])[0]
        if len(ys):
            y_pixels[x] = choose_y(ys, method)

    y_pixels = interpolate_nans(y_pixels)

    # Convert pixel y to amplitude. y=0 is plot top; y=h-1 is plot bottom.
    amplitudes = y_top_value + (y_pixels / max(1, h - 1)) * (y_bottom_value - y_top_value)

    if n_points is not None:
        amplitudes = resample(amplitudes, n_points)

    return amplitudes, bbox


def read_existing_header(csv_path: Path) -> Optional[list[str]]:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return None
    with csv_path.open("r", newline="") as f:
        reader = csv.reader(f)
        return next(reader, None)


def header_info(header: Optional[Sequence[str]]) -> tuple[Optional[int], Optional[bool]]:
    """
    Return (n_features, has_file_column) for an existing CSV header.

    If no CSV exists, returns (None, None).
    """
    if not header:
        return None, None
    if len(header) >= 2 and header[0] == "file" and header[1].startswith("amp_"):
        return len(header) - 1, True
    if len(header) >= 1 and header[0].startswith("amp_"):
        return len(header), False
    # Fallback for a headerless CSV: treat every column as data.
    return len(header), False


def make_header(n_features: int, include_file_column: bool) -> list[str]:
    width = max(4, len(str(n_features - 1)))
    amp_cols = [f"amp_{i:0{width}d}" for i in range(n_features)]
    if include_file_column:
        return ["file"] + amp_cols
    return amp_cols


def append_rows(
    csv_path: Path,
    rows: Iterable[list[object]],
    n_features: int,
    include_file_column: bool,
) -> None:
    """Create CSV with header if missing, otherwise append rows."""
    new_file = (not csv_path.exists()) or csv_path.stat().st_size == 0
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(make_header(n_features, include_file_column))
        writer.writerows(rows)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert BMP waveform graph images to CSV rows of amplitude values."
    )
    parser.add_argument("images", nargs="+", help="BMP files or glob patterns, e.g. '*.bmp'")
    parser.add_argument("--out", default="data.csv", help="Output CSV path. Default: data.csv")
    parser.add_argument("--points", type=int, default=None, help="Resample each row to this many amplitude values, e.g. 512.")
    parser.add_argument("--y-top", type=float, default=-10.0, help="Amplitude at the top of the plot. Default: -10")
    parser.add_argument("--y-bottom", type=float, default=-130.0, help="Amplitude at the bottom of the plot. Default: -130")
    parser.add_argument("--threshold", type=int, default=80, help="Dark-pixel threshold, 0-255. Default: 80")
    parser.add_argument(
        "--method",
        choices=["top", "bottom", "center", "median", "mean"],
        default="top",
        help=(
            "How to choose one y-value when multiple trace pixels occur in one x-column. "
            "Use 'top' for the upper envelope/peaks, 'center' or 'median' for a centerline. Default: top"
        ),
    )
    parser.add_argument(
        "--bbox",
        type=parse_bbox,
        default=None,
        help="Manual plot area as left,top,right,bottom pixels. Use if auto-detection fails.",
    )
    parser.add_argument("--precision", type=int, default=6, help="Decimal places in CSV. Default: 6")
    parser.add_argument(
        "--no-file-column",
        action="store_true",
        help="Write only amplitude columns, with no leading file column.",
    )

    args = parser.parse_args(argv)

    files = expand_inputs(args.images)
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        print("Missing input file(s): " + ", ".join(missing), file=sys.stderr)
        return 2
    if not files:
        print("No input files found.", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    existing_header = read_existing_header(out_path)
    existing_n_features, existing_has_file_column = header_info(existing_header)

    include_file_column = not args.no_file_column
    if existing_has_file_column is not None and existing_has_file_column != include_file_column:
        print(
            f"Existing CSV column structure does not match this run. Existing has file column: "
            f"{existing_has_file_column}; this run has file column: {include_file_column}.",
            file=sys.stderr,
        )
        return 2

    # If appending to an existing CSV and --points was not supplied, reuse the
    # existing feature count so appended rows match the existing shape.
    expected_n = args.points or existing_n_features

    rows: list[list[object]] = []
    detected_bbox: Optional[BBox] = None

    for image_path in files:
        amps, bbox = extract_amplitudes(
            image_path=image_path,
            y_top_value=args.y_top,
            y_bottom_value=args.y_bottom,
            dark_threshold=args.threshold,
            method=args.method,
            bbox=args.bbox,
            n_points=expected_n,
        )

        if expected_n is None:
            expected_n = len(amps)
        elif len(amps) != expected_n:
            amps = resample(amps, expected_n)

        fmt = f"{{:.{args.precision}f}}"
        amp_values = [fmt.format(float(v)) for v in amps]
        row: list[object]
        if include_file_column:
            row = [image_path.name] + amp_values
        else:
            row = amp_values
        rows.append(row)
        detected_bbox = bbox
        print(
            f"Processed {image_path} -> {len(amps)} points; "
            f"min={np.min(amps):.3f}, max={np.max(amps):.3f}; bbox={bbox}"
        )

    if not rows:
        print("No rows were written.", file=sys.stderr)
        return 2

    assert expected_n is not None
    append_rows(out_path, rows, expected_n, include_file_column)
    print(f"Appended {len(rows)} row(s) to {out_path}")
    if args.bbox is None and detected_bbox is not None:
        print(f"Auto-detected plot area: {detected_bbox}. Reuse manually with --bbox left,top,right,bottom if needed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
