#!/usr/bin/env bash
set -e

POINTS=512
METHOD="top"

SCRIPT="bmp_graph_to_csv.py"
DATA_DIR="data/Kefra"

rm -f Fake_High.csv Fake_Low.csv Real.csv

python "$SCRIPT" "$DATA_DIR/Fake_Signal_High_Gain/*.bmp" \
  --out Fake_High.csv \
  --points "$POINTS" \
  --method "$METHOD"

python "$SCRIPT" "$DATA_DIR/Fake_Signal_Low_Gain/*.bmp" \
  --out Fake_Low.csv \
  --points "$POINTS" \
  --method "$METHOD"

python "$SCRIPT" "$DATA_DIR/Real_Signal/*.bmp" \
  --out Real.csv \
  --points "$POINTS" \
  --method "$METHOD"

echo "Done. Created Fake_High.csv, Fake_Low.csv, and Real.csv"
