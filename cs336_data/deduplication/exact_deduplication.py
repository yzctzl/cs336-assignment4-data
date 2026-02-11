import os
import xxhash
from pathlib import Path
from collections import Counter


def hash_line(line: bytes) -> bytes:
    return xxhash.xxh32(line).digest()


def exact_deduplication(input_files: list[os.PathLike], output_directory: os.PathLike):
    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    # count
    line_counts = Counter()
    for file in input_files:
        with open(file, "rb") as f:
            for line in f:
                line_counts[hash_line(line)] += 1

    # write
    for file in input_files:
        input_path = Path(file)
        output_path = output_dir / input_path.name

        with open(input_path, "rb") as fin:
            with open(output_path, "wb") as fout:
                batch = []
                for line in fin:
                    if line_counts[hash_line(line)] == 1:
                        batch.append(line)
                        if len(batch) >= 10000:
                            fout.writelines(batch)
                            batch = []
                if batch:
                    fout.writelines(batch)
