import argparse
from multiprocessing import Pool, cpu_count

from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.filter_cc.extract_text import extract_text_from_html_bytes
from cs336_data.filter_cc.gopher_quality_filters import gopher_quality_filter
from cs336_data.filter_cc.identify_language import identify_language


def is_english(text: str) -> bool:
    # language identify
    langid, _ = identify_language(text)
    return True if langid == "en" else False


def gopher_filter(text: str) -> bool:
    # is english, apply gopher quality filter
    return is_english(text) and gopher_quality_filter(text)


def clean_text_for_fasttext(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.split())


def process_single_record(args):
    """
    Process a single WARC record with 30-second timeout.
    Returns (label, cleaned_text) if successful, None otherwise.
    """
    import signal
    import sys

    def timeout_handler(signum, frame):
        raise TimeoutError()

    content, label, filter_func = args

    try:
        # Set 30 second timeout
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)

        # Extract text (this is the slow part)
        text = extract_text_from_html_bytes(content)

        # Cancel timeout
        signal.alarm(0)

        # Apply filter if provided
        if filter_func and not filter_func(text):
            return None

        # Clean and return
        clean_text = clean_text_for_fasttext(text)
        if clean_text:
            return (label, clean_text)

    except TimeoutError:
        signal.alarm(0)
        print("\n[TIMEOUT] Skipped slow record after 30s", file=sys.stderr, flush=True)
        return None
    except Exception:
        signal.alarm(0)
        return None

    return None


def stream_filtered_warc(warc_path: str, label: str, filter_func=None, num_workers=None, batch_size=256):
    """
    Parallel version with streaming results (first-come-first-served).
    Uses imap_unordered for better throughput - results arrive as soon as they're ready.
    Slow records don't block fast ones.
    """
    if num_workers is None:
        num_workers = cpu_count()

    with open(warc_path, "rb") as f:
        with Pool(num_workers) as pool:
            batch = []

            for record in ArchiveIterator(f, record_types=WarcRecordType.response):
                try:
                    content = record.reader.read()
                    batch.append((content, label, filter_func))

                    # Process batch when full
                    if len(batch) >= batch_size:
                        # imap_unordered: results arrive as soon as ready (first-come-first-served)
                        # Slow records don't block fast ones
                        for result in pool.imap_unordered(process_single_record, batch, chunksize=10):
                            if result is not None:
                                label_text, clean_text = result
                                yield f"{label_text} {clean_text}"
                        batch = []
                except Exception:
                    continue

            # Process remaining batch
            if batch:
                for result in pool.imap_unordered(process_single_record, batch, chunksize=10):
                    if result is not None:
                        label_text, clean_text = result
                        yield f"{label_text} {clean_text}"


def generate_fasttext_data(wiki_warc_path: str, cc_warc_path: str, num_workers=None):
    if num_workers is None:
        num_workers = cpu_count()

    print(f"Opening WARC files:\n Wiki: {wiki_warc_path}\n CC:   {cc_warc_path}")
    print(f"Using {num_workers} parallel workers per file")

    # Create separate generators for valid data from each source (parallel version)
    wiki_stream = stream_filtered_warc(
        wiki_warc_path, "__label__wiki", filter_func=gopher_filter, num_workers=num_workers
    )
    cc_stream = stream_filtered_warc(cc_warc_path, "__label__cc", filter_func=is_english, num_workers=num_workers)

    # zip() will consume both generators.
    # The loop terminates when the *shorter* stream of VALID documents is exhausted.
    for i, (wiki_line, cc_line) in enumerate(zip(wiki_stream, cc_stream)):
        yield wiki_line
        yield cc_line

        if (i + 1) % 1000 == 0:
            print(f"Generated {i + 1} pairs...", end="\r", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate FastText training data from WARC files.")
    parser.add_argument("--wiki", type=str, required=True, help="Path to the Wiki WARC file")
    parser.add_argument("--cc", type=str, required=True, help="Path to the CC WARC file")
    parser.add_argument("--train", type=str, default="data/wiki/fasttext_train.txt", help="Train file path")
    parser.add_argument("--valid", type=str, default="data/wiki/fasttext_valid.txt", help="Valid file path")
    parser.add_argument("--test", type=str, default="data/wiki/fasttext_test.txt", help="Test file path")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: CPU count)")

    args = parser.parse_args()

    count = 0
    with (
        open(args.train, "w", encoding="utf-8") as f_train,
        open(args.valid, "w", encoding="utf-8") as f_valid,
        open(args.test, "w", encoding="utf-8") as f_test,
    ):
        for line in generate_fasttext_data(args.wiki, args.cc, num_workers=args.workers):
            if count % 10 == 0:
                f_test.write(line + "\n")
            elif count % 10 == 9:
                f_valid.write(line + "\n")
            else:
                f_train.write(line + "\n")
            count += 1

    print(f"\nDone! Generated {count} samples")
