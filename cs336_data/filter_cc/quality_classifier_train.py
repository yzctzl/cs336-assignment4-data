import os
import sys
from pathlib import Path

import fasttext


def train_quality_classifier():
    base_dir = Path("data")
    train_file = base_dir / "wiki" / "fasttext_train.txt"
    valid_file = base_dir / "wiki" / "fasttext_valid.txt"
    model_dir = base_dir / "classifiers"
    output_model = model_dir / "wiki_vs_cc.bin"

    if not train_file.exists():
        print(f"Error: Training file not found at {train_file}")
        sys.exit(1)

    if not valid_file.exists():
        print(f"Warning: Validation file not found at {valid_file}.")
        sys.exit(1)

    model_dir.mkdir(parents=True, exist_ok=True)

    print(f"Training FastText model using {train_file}...")
    print(f"Autotuning with validation file {valid_file}...")

    model = fasttext.train_supervised(
        input=str(train_file),
        thread=os.cpu_count() or 1,
        # Autotune instand of specify hyperparams
        autotuneValidationFile=str(valid_file),
        autotuneMetric="f1",
        autotuneDuration=3600,
        verbose=2,
        autotuneModelSize="512M"
    )

    model.save_model(str(output_model))
    print(f"Model saved to {output_model}")

    print("Evaluating on validation set...")
    result = model.test(str(valid_file))
    print(f"Samples: {result[0]}")
    print(f"Precision@1: {result[1]:.4f}")
    print(f"Recall@1: {result[2]:.4f}")


if __name__ == "__main__":
    train_quality_classifier()
