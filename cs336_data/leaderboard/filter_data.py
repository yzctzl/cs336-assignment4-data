import json
from fastwarc.warc import ArchiveIterator, WarcRecordType
from tldextract import TLDExtract
import pathlib
import concurrent.futures
import os
from tqdm import tqdm
from cs336_data.filter_cc.identify_language import identify_language
from cs336_data.filter_cc.harmful_content import classify_nsfw, classify_toxic
from cs336_data.filter_cc.mask_pii import mask_pii
from cs336_data.filter_cc.gopher_quality_filters import gopher_quality_filter
from cs336_data.filter_cc.classify_quality import classify_quality

extractor = TLDExtract(cache_dir="/tmp/tld_cache")


def process_single_wet_file(input_path: str, output_path: str):
    """Process a single WET file and track filter statistics."""
    stats = {
        "total_records": 0,
        "kept": 0,
        "filtered_non_english": 0,
        "filtered_nsfw": 0,
        "filtered_toxic": 0,
        "filtered_gopher_quality": 0,
    }

    with open(output_path, "w") as out:
        for record in ArchiveIterator(open(input_path, "rb"), record_types=WarcRecordType.conversion):
            stats["total_records"] += 1

            try:
                # Extract text from WET record (already extracted from HTML)
                text_bytes = record.reader.read()
                text = text_bytes.decode("utf-8", errors="ignore")
                url = record.headers.get("WARC-Target-URI")

                # Skip empty documents
                if not text or len(text.strip()) < 10:
                    continue

                # Filter 1: Language identification
                lang, lang_conf = identify_language(text)
                if lang != "en":
                    stats["filtered_non_english"] += 1
                    continue

                # Filter 2: NSFW content
                nsfw_label, nsfw_conf = classify_nsfw(text)
                if nsfw_label == "nsfw":
                    stats["filtered_nsfw"] += 1
                    continue

                # Filter 3: Toxic content
                toxic_label, toxic_conf = classify_toxic(text)
                if toxic_label == "toxic":
                    stats["filtered_toxic"] += 1
                    continue

                # Filter 4: Gopher quality filters
                if not gopher_quality_filter(text, langid="en"):
                    stats["filtered_gopher_quality"] += 1
                    continue

                # Filter 5: Quality classification
                quality_label, quality_conf = classify_quality(text)
                if quality_label == "cc":
                    continue

                # Apply PII masking
                text = mask_pii(text)

                # Write output
                output_record = json.dumps({
                    "text": text,
                    "id": record.record_id,
                    "added": record.record_date.isoformat() if record.record_date else None,
                    "source": "cc2604",
                    "subdomain": str(extractor(url=url)) if url else "",
                    "metadata": {
                        "lang_confidence": float(lang_conf),
                        "nsfw_confidence": float(nsfw_conf),
                        "toxic_confidence": float(toxic_conf),
                        "quality_confidence": float(quality_conf),
                    },
                }, indent=4) + "\n"
                out.write(output_record)
                stats["kept"] += 1

            except Exception:
                # Skip records that cause errors during processing
                continue

    return stats


# Set up the executor
num_cpus = len(os.sched_getaffinity(0))
executor = concurrent.futures.ProcessPoolExecutor(max_workers=num_cpus)
wet_filepaths = sorted(os.listdir("data/CC26/test_files"))
output_directory_path = "data/CC26/test_out"

# Create output directory if it doesn't exist
os.makedirs(output_directory_path, exist_ok=True)

futures = []
filepath_to_future = {}

for wet_filepath in wet_filepaths:
    # For each warc.wet.gz filepath, submit a job to the executor and get a future back
    wet_filename = str(pathlib.Path(wet_filepath).name)
    future = executor.submit(
        process_single_wet_file,
        os.path.join("data/CC26/test_files", wet_filepath),
        os.path.join(output_directory_path, wet_filename.replace(".warc.wet.gz", ".jsonl")),
    )
    # Store the futures
    futures.append(future)
    filepath_to_future[future] = wet_filepath

# Aggregate statistics
aggregate_stats = {
    "total_records": 0,
    "kept": 0,
    "filtered_non_english": 0,
    "filtered_nsfw": 0,
    "filtered_toxic": 0,
    "filtered_gopher_quality": 0,
}

# Iterate over the completed futures as they finish, using a progress bar
# to keep track of progress.
for future in tqdm(
    concurrent.futures.as_completed(futures), total=len(wet_filepaths),
    desc="Processing WET files"
):
    try:
        file_stats = future.result()
        # Aggregate statistics
        for key in aggregate_stats:
            aggregate_stats[key] += file_stats[key]
    except Exception as e:
        print(f"Error processing file: {e}")

executor.shutdown(wait=True)

# Print final statistics report
print(json.dumps(aggregate_stats, indent=4))
