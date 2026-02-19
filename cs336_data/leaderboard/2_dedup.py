"""Two-phase deduplication: line-level exact + document-level LSH."""

import os
from pathlib import Path

from cs336_data.deduplication.exact_deduplication import exact_deduplication
# from cs336_data.deduplication.minhash_deduplication import minhash_deduplication

# Record separator for document boundaries
RECORD_SEPARATOR = f"\n{'=' * 30}xxx  RECORD END  xxx{'=' * 30}\n"


if __name__ == "__main__":
    # Configuration
    input_dir = Path("data/CC26/filter_cc")
    # temp_dir = Path("data/CC26/dedup_temp")
    output_dir = Path("data/CC26/dedup")

    num_workers = len(os.sched_getaffinity(0))

    # Get all text files
    input_files = sorted(input_dir.glob("*.txt"))

    print(f"Found {len(input_files)} text files")
    print(f"Using {num_workers} workers\n")

    if not input_files:
        print("No input files found!")
        exit(1)

    # Phase 1: Line-level exact deduplication (optimized)
    print("=" * 60)
    print("Phase 1: Line-level exact deduplication (optimized)")
    print("=" * 60)
    temp_files, total_lines, unique_lines = exact_deduplication(
        input_files,  # type: ignore[arg-type]
        output_dir,
        record_separator=RECORD_SEPARATOR,
        num_workers=num_workers,
        show_progress=True,
    )
    print(f"Generated {len(temp_files)} deduplicated txt files")
    print(f"Line dedup rate: {(total_lines - unique_lines) / total_lines * 100:.2f}%\n")

    # Phase 2: Document-level LSH deduplication
    # LSH parameters
    # NUM_HASHES = 128
    # NUM_BANDS = 16
    # NGRAMS = 5
    # JACCARD_THRESHOLD = 0.8

    # print("=" * 60)
    # print("Phase 2: Document-level LSH deduplication")
    # print("=" * 60)
    # kept, removed = minhash_deduplication(
    #     temp_files,
    #     num_hashes=NUM_HASHES,
    #     num_bands=NUM_BANDS,
    #     ngrams=NGRAMS,
    #     jaccard_threshold=JACCARD_THRESHOLD,
    #     output_directory=output_dir,
    #     num_workers=num_workers,
    #     record_separator=RECORD_SEPARATOR,
    # )

    # Summary
    # print("\n" + "=" * 60)
    # print("Deduplication Complete!")
    # print("=" * 60)
    # print(f"Input files:        {len(input_files)}")
    # print(f"After line dedup:   {len(temp_files)}")
    # print(f"After LSH dedup:    {kept}")
    # print(f"Total removed:      {removed}")
    # print(f"Removal rate:       {removed / len(temp_files) * 100:.2f}%")
    # print("=" * 60)
