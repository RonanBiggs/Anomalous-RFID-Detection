"""
NFC ATQA Dataset: WAV → Tabular CSV Converter
==============================================
Paper: "Deep-Learning-Aided RF Fingerprinting for NFC Relay Attack Detection"
       (Electronics 2023, 12(3), 559)

Dataset layout (all files flat in one folder):
    tag1-1.wav  …  tag1-7374.wav  →  tag1_normal
    tag2-1.wav  …  tag2-7374.wav  →  tag2_normal
    tag3-1.wav  …  tag3-7374.wav  →  tag3_normal
    tag4-1.wav  …  tag4-7374.wav  →  tag4_normal
    tag5-1.wav  …  tag5-7374.wav  →  tag1_wired_relay
    tag6-1.wav  …  tag6-7374.wav  →  tag2_wired_relay
    tag7-1.wav  …  tag7-7374.wav  →  tag3_wired_relay
    tag8-1.wav  …  tag8-7374.wav  →  tag4_wired_relay
    tag9-1.wav  …  tag9-7374.wav  →  wireless_relay

Usage:
    # Single combined CSV:
    python wav_to_tabular.py --data_dir data/NFC_Relay --output data/nfc_atqa.csv

    # One CSV per label (e.g. tag1_normal.csv, tag2_wired_relay.csv, ...):
    python wav_to_tabular.py --data_dir data/NFC_Relay --output data/nfc_atqa.csv --split
"""

import argparse
import csv
import re
import sys
import wave
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Tag number → (label, class, physical_tag)
# ---------------------------------------------------------------------------

TAG_LABEL_MAP = {
    1: ("tag1_normal",       "normal",       "tag1"),
    2: ("tag2_normal",       "normal",       "tag2"),
    3: ("tag3_normal",       "normal",       "tag3"),
    4: ("tag4_normal",       "normal",       "tag4"),
    5: ("tag1_wired_relay",  "wired_relay",  "tag1"),
    6: ("tag2_wired_relay",  "wired_relay",  "tag2"),
    7: ("tag3_wired_relay",  "wired_relay",  "tag3"),
    8: ("tag4_wired_relay",  "wired_relay",  "tag4"),
    9: ("wireless_relay",    "wireless_relay","tag1"),
}

FILENAME_RE = re.compile(r"^tag(\d+)-(\d+)\.wav$", re.IGNORECASE)


def parse_filename(wav_path: Path):
    """
    Returns (tag_num, sample_index, label, cls, physical_tag)
    or None if filename does not match.
    """
    m = FILENAME_RE.match(wav_path.name)
    if not m:
        return None
    tag_num      = int(m.group(1))
    sample_index = int(m.group(2))
    if tag_num not in TAG_LABEL_MAP:
        return None
    label, cls, physical_tag = TAG_LABEL_MAP[tag_num]
    return tag_num, sample_index, label, cls, physical_tag


# ---------------------------------------------------------------------------
# WAV reading
# ---------------------------------------------------------------------------

def read_wav(path: Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as wf:
        sample_rate = wf.getframerate()
        n_channels  = wf.getnchannels()
        sampwidth   = wf.getsampwidth()
        n_frames    = wf.getnframes()
        raw_bytes   = wf.readframes(n_frames)

    dtype_map = {1: np.int8, 2: np.int16, 4: np.int32}
    if sampwidth in dtype_map:
        samples = np.frombuffer(raw_bytes, dtype=dtype_map[sampwidth]).astype(np.float32)
        samples /= float(2 ** (8 * sampwidth - 1))
    else:
        float_dtype = np.float32 if sampwidth == 4 else np.float64
        samples = np.frombuffer(raw_bytes, dtype=float_dtype).astype(np.float32)

    if n_channels > 1:
        samples = samples[::n_channels]

    return sample_rate, samples


def pad_or_truncate(samples: np.ndarray, target_len: int) -> np.ndarray:
    n = len(samples)
    if n == target_len:
        return samples
    if n > target_len:
        return samples[:target_len]
    padded = np.zeros(target_len, dtype=np.float32)
    padded[:n] = samples
    return padded


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def convert(data_dir: str, output_path: str,
            target_len: int = 1800, split: bool = False) -> None:

    data_dir = Path(data_dir)
    out_path = Path(output_path)

    if not data_dir.exists():
        sys.exit(f"[ERROR] Data directory not found: {data_dir}")

    wav_files = sorted(
        data_dir.glob("*.wav"),
        key=lambda p: (
            int(FILENAME_RE.match(p.name).group(1)) if FILENAME_RE.match(p.name) else 999,
            int(FILENAME_RE.match(p.name).group(2)) if FILENAME_RE.match(p.name) else 0,
        )
    )

    if not wav_files:
        sys.exit(f"[ERROR] No .wav files found in: {data_dir}")

    print(f"Found {len(wav_files)} .wav files.")

    amplitude_cols = [f"x{i}" for i in range(target_len)]
    header = ["filepath", "label", "tag_num", "physical_tag", "class",
              "sample_index", "sample_rate", "n_samples"] + amplitude_cols

    rows_written = 0
    skipped      = 0
    label_counts = {}

    # In split mode: one open file handle per label, all written in one pass
    out_dir     = out_path.parent
    out_stem    = out_path.stem
    out_suffix  = out_path.suffix
    split_files = {}   # label → (Path, csv.writer)

    def get_writer(label: str):
        if label not in split_files:
            p = out_dir / f"{out_stem}_{label}{out_suffix}"
            f = open(p, "w", newline="")
            w = csv.writer(f)
            w.writerow(header)
            split_files[label] = (p, f, w)
        return split_files[label][2]

    combined_file   = None
    combined_writer = None
    if not split:
        combined_file   = open(out_path, "w", newline="")
        combined_writer = csv.writer(combined_file)
        combined_writer.writerow(header)

    try:
        for wav_path in wav_files:
            parsed = parse_filename(wav_path)
            if parsed is None:
                print(f"  [SKIP] {wav_path.name}: filename does not match expected pattern")
                skipped += 1
                continue

            tag_num, sample_index, label, cls, physical_tag = parsed

            try:
                sample_rate, samples = read_wav(wav_path)
            except Exception as e:
                print(f"  [SKIP] {wav_path.name}: {e}")
                skipped += 1
                continue

            n_raw       = len(samples)
            samples_out = pad_or_truncate(samples, target_len)

            row = ([str(wav_path), label, tag_num, physical_tag, cls,
                    sample_index, sample_rate, n_raw]
                   + samples_out.tolist())

            if split:
                get_writer(label).writerow(row)
            else:
                combined_writer.writerow(row)

            rows_written += 1
            label_counts[label] = label_counts.get(label, 0) + 1

            if rows_written % 5000 == 0:
                print(f"  … {rows_written} rows written")

    finally:
        if combined_file:
            combined_file.close()
        for _, (p, f, w) in split_files.items():
            f.close()

    print(f"\n✓ Done.")
    print(f"  Rows    : {rows_written}")
    print(f"  Skipped : {skipped}")
    print(f"\n  Label counts:")
    for lbl, cnt in sorted(label_counts.items()):
        if split:
            out_file = out_dir / f"{out_stem}_{lbl}{out_suffix}"
            print(f"    {lbl:<25} {cnt:>6} files  →  {out_file}")
        else:
            print(f"    {lbl:<25} {cnt:>6} files")
    if not split:
        print(f"\n  Combined output: {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert NFC ATQA .wav files to a tabular CSV."
    )
    parser.add_argument(
        "--data_dir", required=True,
        help="Folder containing all tag1-N.wav … tag9-N.wav files."
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
        "--split", action="store_true",
        help="Write one CSV per label instead of one combined file."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    convert(
        data_dir    = args.data_dir,
        output_path = args.output,
        target_len  = args.target_len,
        split       = args.split,
    )