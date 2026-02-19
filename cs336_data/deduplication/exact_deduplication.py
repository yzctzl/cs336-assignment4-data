"""Fixed version with controlled future submission."""

import os
import xxhash
import pickle
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm


def hash_line(line: str) -> int:
    """Hash a line using xxhash64."""
    return xxhash.xxh64(line.strip().encode("utf-8")).intdigest()


def _count_lines_in_file(file_path: os.PathLike) -> dict[int, int]:
    """Count line hash occurrences in a single file."""
    counts = {}
    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    h = hash_line(stripped)
                    counts[h] = counts.get(h, 0) + 1
    except Exception as e:
        print(f"Warning: Failed to read {file_path}: {e}")
    return counts


def _deduplicate_file(args) -> tuple[Path, int, int]:
    """Deduplicate a single file, keeping only unique lines."""
    file_path, output_dir, dup_counts_path, record_separator = args

    with open(dup_counts_path, "rb") as f:
        dup_counts = pickle.load(f)

    input_path = Path(file_path)
    output_path = output_dir / input_path.name

    total_lines = 0
    unique_lines = 0

    try:
        with open(input_path, encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
            content = fin.read()
            docs = content.split(record_separator) if record_separator else [content]

            for doc in docs:
                if not doc.strip():
                    continue

                output_lines = []
                for line in doc.splitlines(keepends=True):
                    total_lines += 1
                    stripped = line.strip()

                    if not stripped:
                        output_lines.append(line)
                        continue

                    h = hash_line(stripped)
                    if h not in dup_counts:
                        output_lines.append(line)
                        unique_lines += 1

                if output_lines:
                    fout.writelines(output_lines)
                    if record_separator:
                        fout.write(record_separator)

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return output_path, 0, 0

    return output_path, total_lines, unique_lines


def exact_deduplication(
    input_files: list[os.PathLike],
    output_directory: os.PathLike,
    record_separator: str = "",
    num_workers: int | None = None,
    show_progress: bool = True,
    max_pending: int = 100,  # Limit number of pending futures
) -> tuple[list[Path], int, int]:
    """
    Exact line-level deduplication with controlled future submission.

    Key fix: Don't submit all futures at once. Instead, maintain a sliding
    window of pending futures to avoid memory accumulation.
    """
    if num_workers is None:
        num_workers = len(os.sched_getaffinity(0))

    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Count line occurrences with controlled submission
    if show_progress:
        print(f"Phase 1: Counting lines ({num_workers} workers, max {max_pending} pending)...")

    all_counts = {}

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Use a sliding window approach
        pending_futures = {}
        file_iter = iter(input_files)
        files_submitted = 0
        files_completed = 0

        # Initial submission
        for _ in range(min(max_pending, len(input_files))):
            try:
                f = next(file_iter)
                future = executor.submit(_count_lines_in_file, f)
                pending_futures[future] = f
                files_submitted += 1
            except StopIteration:
                break

        # Progress bar
        pbar = tqdm(total=len(input_files), desc="Counting") if show_progress else None

        # Process completed futures and submit new ones
        while pending_futures:
            # Wait for at least one future to complete
            done_futures = set()
            for future in as_completed(pending_futures):
                # Process result
                file_counts = future.result()
                for h, count in file_counts.items():
                    all_counts[h] = all_counts.get(h, 0) + count

                done_futures.add(future)
                files_completed += 1

                if pbar:
                    pbar.update(1)

                # Submit a new future to maintain the window
                try:
                    new_file = next(file_iter)
                    new_future = executor.submit(_count_lines_in_file, new_file)
                    pending_futures[new_future] = new_file
                    files_submitted += 1
                except StopIteration:
                    pass

                # Only process one at a time to maintain control
                break

            # Remove completed futures
            for future in done_futures:
                del pending_futures[future]

        if pbar:
            pbar.close()

    # Only keep duplicate hashes
    dup_counts = {h: count for h, count in all_counts.items() if count > 1}

    if show_progress:
        print(f"  Unique lines: {len(all_counts):,}")
        print(f"  Duplicate lines: {len(dup_counts):,}")

    # Save to disk
    counts_path = output_dir / "_dup_counts.pkl"
    with open(counts_path, "wb") as f:
        pickle.dump(dup_counts, f)

    del all_counts

    # Phase 2: Rewrite files
    phase2_workers = max(1, num_workers // 3)
    if show_progress:
        print(f"\nPhase 2: Writing deduplicated files ({phase2_workers} workers)...")

    output_files = []
    total_lines = 0
    unique_lines = 0

    with ProcessPoolExecutor(max_workers=phase2_workers) as executor:
        # Use same sliding window approach for Phase 2
        pending_futures = {}
        file_iter = iter(input_files)

        # Initial submission
        for _ in range(min(max_pending, len(input_files))):
            try:
                f = next(file_iter)
                future = executor.submit(_deduplicate_file, (f, output_dir, counts_path, record_separator))
                pending_futures[future] = f
            except StopIteration:
                break

        pbar = tqdm(total=len(input_files), desc="Writing") if show_progress else None

        while pending_futures:
            done_futures = set()
            for future in as_completed(pending_futures):
                try:
                    output_path, tl, ul = future.result()
                    output_files.append(output_path)
                    total_lines += tl
                    unique_lines += ul
                except Exception as e:
                    file_path = pending_futures[future]
                    print(f"Error processing {file_path}: {e}")

                done_futures.add(future)

                if pbar:
                    pbar.update(1)

                # Submit new future
                try:
                    new_file = next(file_iter)
                    new_future = executor.submit(
                        _deduplicate_file, (new_file, output_dir, counts_path, record_separator)
                    )
                    pending_futures[new_future] = new_file
                except StopIteration:
                    pass

                break

            for future in done_futures:
                del pending_futures[future]

        if pbar:
            pbar.close()

    # Cleanup
    counts_path.unlink(missing_ok=True)

    if show_progress:
        removed = total_lines - unique_lines
        removal_rate = removed / total_lines * 100 if total_lines > 0 else 0
        print("\nResults:")
        print(f"  Total lines: {total_lines:,}")
        print(f"  Unique lines: {unique_lines:,}")
        print(f"  Removed: {removed:,} ({removal_rate:.1f}%)")

    return output_files, total_lines, unique_lines
