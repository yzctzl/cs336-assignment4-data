"""Tokenize filtered text data using GPT-2 tokenizer."""

import os
import numpy as np
from pathlib import Path
from tqdm import tqdm
from multiprocessing import Pool
from transformers import AutoTokenizer

RECORD_SEPARATOR = f"{'=' * 30}xxx  RECORD END  xxx{'=' * 30}\n"

# Global tokenizer for worker processes
_tokenizer = None


def _init_worker(tokenizer_name):
    """Initialize tokenizer once per worker process."""
    global _tokenizer
    _tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)


def _tokenize_chunk(text_chunk):
    """Worker: tokenize a chunk of text."""
    global _tokenizer
    # Tokenize
    tokens = _tokenizer.encode(text_chunk, add_special_tokens=False)  # ty:ignore[unresolved-attribute]
    return tokens


def tokenize_file(
    input_file: Path,
    output_file: Path,
    tokenizer_name: str = "gpt2",
    chunk_size: int = 1000000,  # chars per chunk (1MB)
    num_workers: int | None = None,
    show_progress: bool = True,
    batch_size: int = 1000,  # chunks to process before writing
):
    """
    Tokenize a single text file and save as numpy array with streaming.

    Args:
        input_file: Input text file path
        output_file: Output .npy file path
        tokenizer_name: HuggingFace tokenizer name
        chunk_size: Characters per chunk for parallel processing
        num_workers: Number of parallel workers
        show_progress: Whether to show progress
        batch_size: Number of chunks to process before writing to disk
    """
    if num_workers is None:
        num_workers = len(os.sched_getaffinity(0))

    # Get file size for progress
    file_size = input_file.stat().st_size
    estimated_chunks = file_size // chunk_size + 1

    if show_progress:
        print(f"File size: {file_size / 1024 / 1024:.2f} MB")
        print(f"Estimated chunks: {estimated_chunks}")

    # Create a temporary file for incremental writing
    temp_file = output_file.with_suffix(".tmp.npy")

    total_tokens = 0
    all_token_batches = []

    def chunk_generator():
        """Generator to read file in chunks without loading all into memory."""
        with open(input_file, encoding="utf-8") as f:
            buffer = ""
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    if buffer:
                        yield buffer.replace(RECORD_SEPARATOR, "\n\n")
                    break

                buffer += chunk
                # Find last newline to avoid splitting words
                last_newline = buffer.rfind("\n")
                if last_newline > chunk_size // 2:  # Keep at least half chunk
                    yield buffer[:last_newline].replace(RECORD_SEPARATOR, "\n\n")
                    buffer = buffer[last_newline + 1 :]
                elif len(buffer) > chunk_size * 2:  # Force yield if buffer too large
                    yield buffer.replace(RECORD_SEPARATOR, "\n\n")
                    buffer = ""

    # Process in batches to limit memory
    with Pool(num_workers, initializer=_init_worker, initargs=(tokenizer_name,)) as pool:
        chunk_iter = chunk_generator()

        pbar = tqdm(total=estimated_chunks, desc="Tokenizing") if show_progress else None

        while True:
            # Get a batch of chunks
            batch = []
            for _ in range(batch_size):
                try:
                    batch.append(next(chunk_iter))
                except StopIteration:
                    break

            if not batch:
                break

            # Process batch
            for tokens in pool.imap(_tokenize_chunk, batch):
                all_token_batches.append(np.array(tokens, dtype=np.uint16))
                total_tokens += len(tokens)
                if pbar:
                    pbar.update(1)

            # Write to disk periodically to free memory
            if len(all_token_batches) >= 100:
                if show_progress:
                    print(f"\nWriting batch to disk... ({total_tokens:,} tokens so far)")

                # Concatenate and write
                batch_array = np.concatenate(all_token_batches)

                if temp_file.exists():
                    # Append to existing file
                    existing = np.load(temp_file)
                    combined = np.concatenate([existing, batch_array])
                    np.save(temp_file, combined)
                else:
                    np.save(temp_file, batch_array)

                all_token_batches = []

        if pbar:
            pbar.close()

    # Write remaining tokens
    if all_token_batches:
        batch_array = np.concatenate(all_token_batches)

        if temp_file.exists():
            existing = np.load(temp_file)
            combined = np.concatenate([existing, batch_array])
            np.save(output_file, combined)
            temp_file.unlink()
        else:
            np.save(output_file, batch_array)
    elif temp_file.exists():
        temp_file.rename(output_file)

    return total_tokens


def tokenize_dataset(
    input_file: Path,
    output_dir: Path,
    tokenizer_name: str = "gpt2",
    num_workers: int | None = None,
):
    """
    Tokenize dataset and save as numpy arrays.

    Args:
        input_file: Input text file
        output_dir: Output directory for .npy files
        tokenizer_name: HuggingFace tokenizer name
        num_workers: Number of parallel workers
    """
    if num_workers is None:
        num_workers = len(os.sched_getaffinity(0))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Tokenizing with {tokenizer_name}")
    print(f"Using {num_workers} workers\n")

    # Output file
    output_file = output_dir / "tokens.npy"

    # Tokenize
    print("=" * 60)
    print("Tokenization")
    print("=" * 60)
    num_tokens = tokenize_file(input_file, output_file, tokenizer_name=tokenizer_name, num_workers=num_workers)

    # Summary
    print("\n" + "=" * 60)
    print("Tokenization Complete!")
    print("=" * 60)
    print(f"Input file:     {input_file}")
    print(f"Output file:    {output_file}")
    print(f"Total tokens:   {num_tokens:,}")
    print(f"File size:      {output_file.stat().st_size / 1024 / 1024:.2f} MB")
    print("=" * 60)


if __name__ == "__main__":
    # Configuration
    input_file = Path("data/CC26/dataset.txt")
    output_dir = Path("data/CC26/tokenized")
    tokenizer_name = "gpt2"

    num_workers = len(os.sched_getaffinity(0))

    if not input_file.exists():
        print(f"Input file not found: {input_file}")
        exit(1)

    tokenize_dataset(input_file, output_dir, tokenizer_name=tokenizer_name, num_workers=num_workers)
