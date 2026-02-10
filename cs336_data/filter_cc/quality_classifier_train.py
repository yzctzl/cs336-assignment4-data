import os
import sys
from pathlib import Path

import fasttext


base_dir = Path("data")
train_file = base_dir / "wiki" / "fasttext_train.txt"
valid_file = base_dir / "wiki" / "fasttext_valid.txt"
test_file = base_dir / "wiki" / "fasttext_test.txt"
model_dir = base_dir / "classifiers"
output_model = model_dir / "wiki_vs_cc_full.bin"
quantize_model = model_dir / "wiki_vs_cc.ftz"


def print_model_args(model, title="Model Parameters"):
    """Print all FastText model arguments in a readable format."""
    args = model.f.getArgs()

    print(f"\n{'=' * 50}")
    print(f"{title:^50}")
    print(f"{'=' * 50}")

    # Training parameters
    print("\n[Training Parameters]")
    print(f"  Learning rate (lr):        {args.lr}")
    print(f"  Learning rate update (lrUpdateRate): {args.lrUpdateRate}")
    print(f"  Dimensions (dim):          {args.dim}")
    print(f"  Epochs:                    {args.epoch}")
    print(f"  Word n-grams:              {args.wordNgrams}")
    print(f"  Loss function:             {args.loss}")

    # Dictionary parameters
    print("\n[Dictionary Parameters]")
    print(f"  Min count:                 {args.minCount}")
    print(f"  Min count label:           {args.minCountLabel}")
    print(f"  Bucket size:               {args.bucket}")
    print(f"  Min n-gram:                {args.minn}")
    print(f"  Max n-gram:                {args.maxn}")

    # Model parameters
    print("\n[Model Parameters]")
    print(f"  Model type:                {args.model}")
    print(f"  Negative sampling:         {args.neg}")
    print(f"  Context window:            {args.ws}")

    # Other parameters
    print("\n[Other Parameters]")
    print(f"  Threads:                   {args.thread}")
    print(f"  Verbose:                   {args.verbose}")
    print(f"  Save output:               {args.saveOutput}")

    print(f"{'=' * 50}\n")


def train_quality_classifier():
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
    )

    # Print the autotuned parameters
    print_model_args(model, "Autotune Results")

    model.save_model(str(output_model))
    print(f"Model saved to {output_model}")

    evaluate(model)


def quantize():
    """Load the trained model for quantization"""
    print(f"Load model from {output_model} to quantize")
    model = fasttext.load_model(str(output_model))
    model.quantize(
        input=str(train_file),
        cutoff=60000,
        retrain=True,
        thread=os.cpu_count() or 1,
        verbose=2
    )
    model.save_model(str(quantize_model))
    print(f"Quantized model saved to {quantize_model}")

    evaluate(model)


def evaluate(model):
    print("Evaluating on validation set...")
    result = model.test(str(test_file))
    print(f"Samples: {result[0]}")
    print(f"Precision@1: {result[1]:.4f}")
    print(f"Recall@1: {result[2]:.4f}")


if __name__ == "__main__":
    train_quality_classifier()
    quantize()
