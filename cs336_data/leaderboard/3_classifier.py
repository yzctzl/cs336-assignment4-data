import os
import regex as re
import unicodedata
from pathlib import Path
from tqdm import tqdm
from multiprocessing import Pool
from fasttext.FastText import load_model

RECORD_SEPARATOR = f"{'=' * 30}xxx  RECORD END  xxx{'=' * 30}\n"
RE_SPACES = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Normalize text for classification (same as training)."""
    text = unicodedata.normalize("NFKC", text.lower())

    clean_chars = []
    for char in text:
        cat = unicodedata.category(char)
        if cat.startswith("P") or cat.startswith("S"):
            clean_chars.append(" ")
        elif cat == "Mn":
            continue
        else:
            clean_chars.append(char)

    text = "".join(clean_chars)
    text = RE_SPACES.sub(" ", text).strip()
    return text


def _classify_file(args):
    """Worker: classify records in a single file."""
    file_path, model_path = args

    # Load model in worker process
    model = load_model(model_path)

    stats = {"total": 0, "kept": 0, "filtered": 0}
    kept_records = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Split by record separator
        records = content.split(RECORD_SEPARATOR)

        for record in records:
            record = record.strip()
            if not record:
                continue

            stats["total"] += 1

            try:
                # Normalize and classify
                normalized = normalize_text(record)
                clean_text = " ".join(normalized.split())
                labels, probs = model.predict(clean_text, k=1)
                label = labels[0].removeprefix("__label__")

                if label == "hq":
                    kept_records.append(record)
                    stats["kept"] += 1
                else:
                    stats["filtered"] += 1
            except Exception:
                continue
    except Exception:
        pass

    return kept_records, stats


def filter_with_classifier(
    input_files: list[Path],
    output_file: os.PathLike,
    model_path: str = "data/classifiers/paloma_vs_cc.ftz",
    num_workers: int | None = None,
    chunksize: int = 1,
):
    """
    Filter deduplicated txt files using quality classifier with parallel processing.

    Args:
        input_files: List of deduplicated txt file paths
        output_file: Single output txt file path
        model_path: Path to fasttext model
        num_workers: Number of parallel workers (default: CPU count)
        chunksize: Number of files to process per worker task
    """
    if num_workers is None:
        num_workers = len(os.sched_getaffinity(0))

    print(f"Using {num_workers} workers for classification")

    aggregate_stats = {"total_records": 0, "kept_hq": 0, "filtered_lq": 0}

    # Process files in parallel with explicit flushing
    with open(output_file, "w", encoding="utf-8", buffering=8192*16) as fout:
        with Pool(num_workers) as pool:
            args = [(f, model_path) for f in input_files]
            results = pool.imap_unordered(_classify_file, args, chunksize=chunksize)

            for kept_records, stats in tqdm(results, total=len(input_files), desc="Paloma C4 100 Filtering"):
                # Write kept records
                for record in kept_records:
                    fout.write(record)
                    fout.write("\n" + RECORD_SEPARATOR)
                
                # Flush periodically to avoid buffer buildup
                if aggregate_stats["total_records"] % 1000 == 0:
                    fout.flush()

                # Aggregate stats
                aggregate_stats["total_records"] += stats["total"]
                aggregate_stats["kept_hq"] += stats["kept"]
                aggregate_stats["filtered_lq"] += stats["filtered"]

    return aggregate_stats


if __name__ == "__main__":
    # Configuration
    input_dir = Path("data/CC26/dedup")
    output_file = Path("data/CC26/dataset.txt")
    model_path = "data/classifiers/paloma_vs_cc.ftz"

    num_workers = len(os.sched_getaffinity(0))

    # Get all deduplicated txt files
    input_files = sorted(input_dir.glob("*.txt"))

    print(f"Found {len(input_files)} deduplicated txt files")

    if not input_files:
        print("No input files found!")
        exit(1)

    print("Filtering with quality classifier...")
    stats = filter_with_classifier(input_files, output_file, model_path, num_workers)

    print("\n" + "=" * 60)
    print("Filtering Statistics:")
    print(f"  Total records: {stats['total_records']}")
    print(f"  Kept (HQ): {stats['kept_hq']}")
    print(f"  Filtered (LQ): {stats['filtered_lq']}")
    print(f"  Keep rate: {stats['kept_hq'] / max(stats['total_records'], 1) * 100:.2f}%")
    print("=" * 60)
    print(f"\nFinal dataset saved to: {output_file}")
