"""
NFC ATQA Dataset: WAV → Tabular CSV Converter
==============================================
Reference Paper: "Deep-Learning-Aided RF Fingerprinting for NFC Relay Attack Detection"
       (Electronics 2023, 12(3), 559)

Dataset specs:
  - Each .wav = one ATQA segment (04 00 hex, Manchester encoded)
  - Sample rate: 10 M samples/s
  - Length: ~1800 amplitude samples per file (~180 µs of signal)
  - Labels: normal / wired_relay / wireless_relay

Output CSV format (one row per .wav):
  filepath, label, sample_rate, n_samples, x0, x1, ..., x1799

Usage:
  python wav_to_tabular.py --data_dir data/NFC_Relay  --output nfc_atqa.csv

  Folder structure assumed (matches the paper's dataset):
    dataset/
      tag1/
        normal/         *.wav
        wired_relay/    *.wav
      tag2/
        normal/         *.wav
        wired_relay/    *.wav
      ...
      wireless_relay/   *.wav   (shared across tags, or nested — auto-detected)

  The script infers the label from the parent folder name.
  Any folder whose name contains:
    "normal"          → label = "normal"
    "wired"           → label = "wired_relay"
    "wireless"        → label = "wireless_relay"
"""

import argparse
import csv
import sys
import wave
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Label inference
# ---------------------------------------------------------------------------

def infer_label(wav_path: Path) -> str:
    """
    Walk up the path components (closest first) and return the first label
    match, so deeply nested files still resolve correctly.
    """
    for part in reversed(wav_path.parts):
        lower = part.lower()
        if "wireless" in lower:
            return "wireless_relay"
        if "wired" in lower:
            return "wired_relay"
        if "normal" in lower:
            return "normal"
    return "unknown"


# ---------------------------------------------------------------------------
# WAV reading
# ---------------------------------------------------------------------------

def read_wav(path: Path) -> tuple[int, np.ndarray]:
    """
    Read a WAV file and return (sample_rate, float32_samples).

    The NFC dataset is recorded as 16-bit PCM (standard WAV).
    We normalise to [-1, 1] so columns are comparably scaled.
    If the file is already float32/float64, we just convert.
    """
    with wave.open(str(path), "rb") as wf:
        sample_rate  = wf.getframerate()
        n_channels   = wf.getnchannels()
        sampwidth    = wf.getsampwidth()   # bytes per sample
        n_frames     = wf.getnframes()
        raw_bytes    = wf.readframes(n_frames)

    # Map sampwidth → numpy dtype
    dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
    if sampwidth in dtype_map:
        samples = np.frombuffer(raw_bytes, dtype=dtype_map[sampwidth]).astype(np.float32)
        max_val = float(2 ** (8 * sampwidth - 1))
        samples = samples / max_val          # normalise to [-1, 1]
    else:
        # Assume float (32 or 64-bit)
        float_dtype = np.float32 if sampwidth == 4 else np.float64
        samples = np.frombuffer(raw_bytes, dtype=float_dtype).astype(np.float32)

    # If stereo/multi-channel, take channel 0 (should be mono for this dataset)
    if n_channels > 1:
        samples = samples[::n_channels]

    return sample_rate, samples


# ---------------------------------------------------------------------------
# Padding / truncation
# ---------------------------------------------------------------------------

def pad_or_truncate(samples: np.ndarray, target_len: int) -> np.ndarray:
    """
    Ensure every row has exactly `target_len` amplitude columns.
    Short signals are zero-padded on the right; long ones are truncated.
    """
    n = len(samples)
    if n == target_len:
        return samples
    if n > target_len:
        return samples[:target_len]
    # pad
    padded = np.zeros(target_len, dtype=np.float32)
    padded[:n] = samples
    return padded


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def convert(data_dir: str,
            output_path: str,
            target_len: int = 1800,
            recursive: bool = True) -> None:

    data_dir  = Path(data_dir)
    out_path  = Path(output_path)

    if not data_dir.exists():
        sys.exit(f"[ERROR] Data directory not found: {data_dir}")

    # Collect all .wav files
    pattern = "**/*.wav" if recursive else "*.wav"
    wav_files = sorted(data_dir.glob(pattern))

    if not wav_files:
        sys.exit(f"[ERROR] No .wav files found under: {data_dir}")

    print(f"Found {len(wav_files)} .wav files. Converting …")

    # Build header: filepath, label, sample_rate, n_samples, x0…x(N-1)
    amplitude_cols = [f"x{i}" for i in range(target_len)]
    header = ["filepath", "label", "sample_rate", "n_samples"] + amplitude_cols

    rows_written  = 0
    skipped       = 0
    label_counts  = {}

    with open(out_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)

        for wav_path in wav_files:
            try:
                sample_rate, samples = read_wav(wav_path)
            except Exception as e:
                print(f"  [SKIP] {wav_path.name}: {e}")
                skipped += 1
                continue

            label       = infer_label(wav_path)
            n_raw       = len(samples)
            samples_out = pad_or_truncate(samples, target_len)

            row = (
                [str(wav_path), label, sample_rate, n_raw]
                + samples_out.tolist()
            )
            writer.writerow(row)

            rows_written += 1
            label_counts[label] = label_counts.get(label, 0) + 1

            if rows_written % 1000 == 0:
                print(f"  … {rows_written} rows written")

    # Summary
    print(f"\n✓ Done.")
    print(f"  Output : {out_path}")
    print(f"  Rows   : {rows_written}")
    print(f"  Skipped: {skipped}")
    print(f"  Labels :")
    for lbl, cnt in sorted(label_counts.items()):
        print(f"    {lbl:<20} {cnt:>6} files")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert NFC ATQA .wav files to a tabular CSV."
    )
    parser.add_argument(
        "--data_dir", required=True,
        help="Root folder of the NFC dataset (searched recursively)."
    )
    parser.add_argument(
        "--output", default="nfc_atqa.csv",
        help="Output CSV file path. (default: nfc_atqa.csv)"
    )
    parser.add_argument(
        "--target_len", type=int, default=1800,
        help="Number of amplitude columns per row. (default: 1800)"
    )
    parser.add_argument(
        "--no_recursive", action="store_true",
        help="Only search the top-level data_dir, not subdirectories."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    convert(
        data_dir    = args.data_dir,
        output_path = args.output,
        target_len  = args.target_len,
        recursive   = not args.no_recursive,
    )