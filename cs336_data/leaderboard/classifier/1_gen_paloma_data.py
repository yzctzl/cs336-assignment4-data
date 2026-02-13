import argparse
import numpy as np
from transformers import AutoTokenizer

from cs336_data.leaderboard.classifier.common import normalize_text


def stream_filtered_tokenized(bin_path: str, label: str, filter_func=None):
    """
    Stream and process tokenized binary data (load and yield on-the-fly).
    Splits by eos_token_id and processes documents sequentially.
    """
    print(f"Loading tokenized data from {bin_path}...")
    data = np.fromfile(bin_path, dtype=np.uint16)
    print(f"Loaded {len(data)} tokens")

    tokenizer = AutoTokenizer.from_pretrained("gpt2")
    eos_token_id = tokenizer.eos_token_id

    current_doc = []

    for token_id in data:
        if token_id == eos_token_id:
            if current_doc:
                # Decode the document
                text = tokenizer.decode(current_doc)

                # Apply filter if provided
                if filter_func is None or filter_func(text):
                    clean_text = normalize_text(text)
                    if clean_text:
                        yield f"{label} {clean_text}"

                current_doc = []
        else:
            current_doc.append(token_id)

    # Process last document if exists
    if current_doc:
        text = tokenizer.decode(current_doc)
        if filter_func is None or filter_func(text):
            clean_text = normalize_text(text)
            if clean_text:
                yield f"{label} {clean_text}"


def generate_fasttext_data(paloma_path: str):
    print(f"Loading datasets:\n Paloma: {paloma_path}")

    # Create separate generators for valid data from each source (streaming)
    paloma_stream = stream_filtered_tokenized(paloma_path, "__label__hq")
    # Interleave both streams
    for i, paloma_line in enumerate(paloma_stream):
        yield paloma_line

        if (i + 1) % 1000 == 0:
            print(f"Generated {i + 1} paloma line ...", end="\r", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate FastText training data from Paloma tokenized data and CC WARC files."
    )
    parser.add_argument("--paloma", type=str, required=True, help="Path to the Paloma tokenized binary file")
    parser.add_argument("--train", type=str, default="data/paloma/paloma/train.txt", help="Train file path")
    parser.add_argument("--valid", type=str, default="data/paloma/paloma/valid.txt", help="Valid file path")
    parser.add_argument("--test", type=str, default="data/paloma/paloma/test.txt", help="Test file path")

    args = parser.parse_args()

    count = 0
    with (
        open(args.train, "w", encoding="utf-8") as f_train,
        open(args.valid, "w", encoding="utf-8") as f_valid,
        open(args.test, "w", encoding="utf-8") as f_test,
    ):
        for line in generate_fasttext_data(args.paloma):
            if count % 10 == 0:
                f_test.write(line + "\n")
            elif count % 10 == 9:
                f_valid.write(line + "\n")
            else:
                f_train.write(line + "\n")
            count += 1

    print(f"\nDone! Generated {count} samples")
