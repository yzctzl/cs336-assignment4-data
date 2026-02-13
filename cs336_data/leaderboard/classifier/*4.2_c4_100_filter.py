import os
import gzip
import argparse
from pathlib import Path
from multiprocessing import Pool
from fastwarc.warc import ArchiveIterator, WarcRecordType
from fastwarc.stream_io import BytesIOStream
import tldextract
from cs336_data.filter_cc.gopher_quality_filters import gopher_quality_filter
from cs336_data.filter_cc.identify_language import identify_language
from cs336_data.leaderboard.classifier.common import text_cleaner


def load_domains(domain_file: str) -> set[str]:
    """Load domain whitelist and normalize to registered domains"""
    domains = set()
    with open(domain_file, encoding="utf-8") as f:
        for line in f:
            domain = line.strip()
            if domain:
                # Extract registered domain (e.g., rt.com from www.rt.com)
                ext = tldextract.extract(domain)
                if ext.domain and ext.suffix:
                    domains.add(f"{ext.domain}.{ext.suffix}")
    print(f"Loaded {len(domains)} unique registered domains")
    return domains


def extract_domain(url: str) -> str:
    """Extract registered domain (e.g., rt.com from abc.rt.com)"""
    try:
        ext = tldextract.extract(url)
        if ext.domain and ext.suffix:
            return f"{ext.domain}.{ext.suffix}"
        return ""
    except Exception:
        return ""


def is_english(text: str) -> bool:
    # language identify
    langid, _ = identify_language(text)
    return langid == "en"


def gopher_filter(text: str) -> bool:
    # is english, apply gopher quality filter
    if is_english(text):
        return gopher_quality_filter(text)
    return False


def process_file(args):
    """Process single wet.gz file, keep raw WARC records"""
    wet_file, allowed_domains = args

    raw_records = []
    total = 0
    kept = 0

    try:
        with open(wet_file, "rb") as stream:
            for record in ArchiveIterator(stream, record_types=WarcRecordType.conversion):
                total += 1
                uri = record.headers.get("WARC-Target-URI", "")
                domain = extract_domain(uri)  # ty:ignore[invalid-argument-type]

                # apply gopher filter
                if domain in allowed_domains:
                    # Store raw record bytes
                    buf = BytesIOStream()
                    record.write(buf)
                    text = text_cleaner(buf.getvalue().decode("utf-8"))
                    if gopher_filter(text):
                        raw_records.append(buf.getvalue())
                        kept += 1

        return {"file": wet_file, "total": total, "kept": kept, "records": raw_records}

    except Exception as e:
        print(f"Error: {wet_file}: {e}")
        return {"file": wet_file, "total": 0, "kept": 0, "records": []}


def write_output(output_file: str, raw_records: list[bytes]):
    """Write raw WARC records to wet.gz"""
    with gzip.open(output_file, "wb") as f:
        for raw_record in raw_records:
            f.write(raw_record)


def process_batch(files: list[str], output: str, domains: set[str], workers: int):
    """Process batch of files"""
    print(f"\nBatch: {len(files)} files -> {output}")

    all_records = []
    total_in = 0
    total_out = 0

    with Pool(workers) as pool:
        for i, result in enumerate(
            pool.imap_unordered(process_file, [(f, domains) for f in files]), 1
        ):
            total_in += result["total"]
            total_out += result["kept"]
            all_records.extend(result["records"])

            filter_rate = (1 - total_out / max(total_in, 1)) * 100
            print(
                f"  Progress: {i}/{len(files)} | Records: {total_in} -> {total_out} | Filter: {filter_rate:.1f}%",
                end="\r",
                flush=True,
            )

    print()
    write_output(output, all_records)
    print(f"  Done: {total_in} -> {total_out} records")

    return total_in, total_out


def main():
    parser = argparse.ArgumentParser(description="Batch domain filter for wet.gz files")
    parser.add_argument("--input_dir", default="data/CC26/wet_files", help="Input directory")
    parser.add_argument("--output_dir", default="data/CC26/c4_100", help="Output directory")
    parser.add_argument("--domain_list", default="data/paloma/c4_100_domains/domain_list.txt", help="Domain whitelist file")
    parser.add_argument("--batch_size", type=int, default=200, help="Files per batch")
    parser.add_argument("--workers", type=int, default=40, help="Worker processes")

    args = parser.parse_args()

    workers = args.workers or len(os.sched_getaffinity(0))
    print(f"Using {workers} workers")

    domains = load_domains(args.domain_list)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted([str(f) for f in Path(args.input_dir).glob("*.wet.gz")])

    print(f"Found {len(files)} wet.gz files")

    num_batches = (len(files) + args.batch_size - 1) // args.batch_size
    print(f"Processing {num_batches} batches ({args.batch_size} files each)")

    grand_in = 0
    grand_out = 0

    for batch_idx in range(num_batches):
        start = batch_idx * args.batch_size
        end = min(start + args.batch_size, len(files))
        batch_files = files[start:end]

        output_file = output_dir / f"filtered_batch_{batch_idx:04d}.wet.gz"

        total_in, total_out = process_batch(batch_files, str(output_file), domains, workers)
        grand_in += total_in
        grand_out += total_out

    print("\n" + "=" * 60)
    print(f"Complete: {len(files)} files -> {num_batches} batches")
    print(f"Records: {grand_in} -> {grand_out} ({(1 - grand_out / max(grand_in, 1)) * 100:.1f}% filtered)")
    print("=" * 60)


if __name__ == "__main__":
    main()
