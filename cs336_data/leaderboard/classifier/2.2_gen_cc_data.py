import re
import argparse
import random
from multiprocessing import Pool, cpu_count

from cs336_data.filter_cc.gopher_quality_filters import gopher_quality_filter
from cs336_data.filter_cc.identify_language import identify_language
from cs336_data.leaderboard.classifier.common import normalize_text

RAW_CC_Ratio = 0.33
RE_ENDLINE = re.compile(r"[.\n]")
RECORD_SEPARATOR = f"{'=' * 30}xxx  RECORD END  xxx{'=' * 30}\n"


def is_english(text: str) -> bool:
    # language identify
    langid, _ = identify_language(text)
    return langid == "en"


def gopher_filter(text: str) -> bool:
    # is english, apply gopher quality filter
    if is_english(text):
        if random.random() < RAW_CC_Ratio:
            return gopher_quality_filter(text)
        return True
    return False


def get_avg_len(paloma_path: str = "data/paloma/paloma/train.txt"):
    words = 0
    pages = 0
    with open(paloma_path, encoding="utf-8") as f:
        for line in f:
            words += len(line.removeprefix("__label__hq "))
            pages += 1

    return words // pages if words else 0


avg_len = get_avg_len()


def split_with_boundary(text, avg_len: int = avg_len):
    start = 0
    while start < len(text):
        end = start + avg_len

        if end < len(text):
            match = RE_ENDLINE.search(text[end:])
            if match:
                end = end + match.start() + 1
            else:
                end = len(text)

        yield text[start:end].strip()
        start = end


def process_single_record(args):
    """Process a single text record with filtering."""
    text, label, apply_filter = args

    try:
        # Apply filter if needed
        if apply_filter:
            langid, _ = identify_language(text)
            if langid != "en":
                return []

            # Apply gopher filter with probability
            # if random.random() < RAW_CC_Ratio:
            #     if not gopher_quality_filter(text):
            #         return []

        # Clean and return
        clean_text = normalize_text(text)
        results = []
        for part_text in split_with_boundary(clean_text):
            if gopher_filter(part_text):
                results.append((label, part_text))
        return results

    except Exception:
        return []


def stream_filtered_text(text_path: str, label: str, apply_filter=False, num_workers=None, batch_size=256):
    """
    Stream and process text file with record separators.
    Processes records in parallel batches.
    """
    if num_workers is None:
        num_workers = cpu_count()

    print(f"Reading text file: {text_path}")

    with open(text_path, encoding="utf-8") as f:
        with Pool(num_workers) as pool:
            batch = []
            current_record = []

            for line in f:
                if line == RECORD_SEPARATOR:
                    if current_record:
                        # Join lines to form complete record
                        text = "".join(current_record)
                        batch.append((text, label, apply_filter))
                        current_record = []

                        # Process batch when full
                        if len(batch) >= batch_size:
                            for results in pool.imap_unordered(process_single_record, batch, chunksize=10):
                                for label_text, clean_text in results:
                                    yield f"{label_text} {clean_text}"
                            batch = []
                else:
                    current_record.append(line)

            # Process last record if exists
            if current_record:
                text = "".join(current_record)
                batch.append((text, label, apply_filter))

            # Process remaining batch
            if batch:
                for results in pool.imap_unordered(process_single_record, batch, chunksize=10):
                    for label_text, clean_text in results:
                        yield f"{label_text} {clean_text}"


def generate_fasttext_data(cc_text_path: str, num_workers=None):
    """Generate FastText training data from text file."""
    if num_workers is None:
        num_workers = cpu_count()

    print(f"Opening text file:\n CC:   {cc_text_path}")
    print(f"Using {num_workers} parallel workers")

    cc_stream = stream_filtered_text(cc_text_path, "__label__lq", apply_filter=True, num_workers=num_workers)

    for i, cc_line in enumerate(cc_stream):
        yield cc_line

        if (i + 1) % 1000 == 0:
            print(f"Generated {i + 1} lines ...", end="\r", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate FastText training data from TEXT files.")
    parser.add_argument("--cc", type=str, required=True, help="Path to the CC TEXT file")
    parser.add_argument("--train", type=str, default="data/paloma/cc/train.txt", help="Train file path")
    parser.add_argument("--valid", type=str, default="data/paloma/cc/valid.txt", help="Valid file path")
    parser.add_argument("--test", type=str, default="data/paloma/cc/test.txt", help="Test file path")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers (default: CPU count)")

    args = parser.parse_args()

    count = 0
    with (
        open(args.train, "w", encoding="utf-8") as f_train,
        open(args.valid, "w", encoding="utf-8") as f_valid,
        open(args.test, "w", encoding="utf-8") as f_test,
    ):
        for line in generate_fasttext_data(args.cc, num_workers=args.workers):
            if count % 10 == 1:
                f_test.write(line + "\n")
            elif count % 10 == 9:
                f_valid.write(line + "\n")
            else:
                f_train.write(line + "\n")
            count += 1

    print(f"\nDone! Generated {count} samples")
