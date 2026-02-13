#!/bin/bash

OUT_DIR="data/paloma/paloma_cc"
mkdir -p $OUT_DIR

DIR_1="data/paloma/paloma"
DIR_2="data/paloma/cc"

# train
echo "building train set ..."
> "$OUT_DIR/train_raw.tmp"

echo "  -> Set 1 (Paloma) x5..."
for i in {1..5}; do
    cat "$DIR_1/train.txt" >> "$OUT_DIR/train_raw.tmp"
done

echo "  -> Set 2..."
cat "$DIR_2/train.txt" >> "$OUT_DIR/train_raw.tmp"

echo "  -> Shuffling..."
shuf "$OUT_DIR/train_raw.tmp" > "$OUT_DIR/train.txt"

rm "$OUT_DIR/train_raw.tmp"


# valid
echo "building valid set ..."
cat "$DIR_1/valid.txt" \
    "$DIR_2/valid.txt" > "$OUT_DIR/valid.tmp"

echo "  -> Shuffling..."
shuf "$OUT_DIR/valid.tmp" > "$OUT_DIR/valid.txt"

rm "$OUT_DIR/valid.tmp"

# test
echo "build test set ..."
cat "$DIR_1/test.txt" \
    "$DIR_2/test.txt" > "$OUT_DIR/test.tmp"

echo "  -> Shuffling..."
shuf "$OUT_DIR/test.tmp" > "$OUT_DIR/test.txt"

rm "$OUT_DIR/test.tmp"

echo "DONE!"
