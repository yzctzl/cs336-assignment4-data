import os
import json
# import gzip
from tqdm import tqdm
import concurrent.futures
from tldextract import TLDExtract
from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.filter_cc.identify_language import identify_language
from cs336_data.filter_cc.harmful_content import classify_nsfw, classify_toxic
# from cs336_data.filter_cc.mask_pii import mask_pii
from cs336_data.filter_cc.gopher_quality_filters import gopher_quality_filter

extractor = TLDExtract(cache_dir="/tmp/tld_cache")
RECORD_SEPARATOR = f"\n{'=' * 30}xxx  RECORD END  xxx{'=' * 30}\n"

def process_single_wet_file(input_path: str, output_path: str):
    """Process a single WET file and write to text."""
    stats = {
        "total_records": 0,
        "kept": 0,
        "filtered_non_english": 0,
        "filtered_nsfw": 0,
        "filtered_toxic": 0,
        "filtered_gopher_quality": 0,
        # "filtered_paloma_quality": 0,
    }

    with open(output_path, "w", encoding="utf-8") as out:
        for record in ArchiveIterator(open(input_path, "rb"), record_types=WarcRecordType.conversion):
            stats["total_records"] += 1

            try:
                text_bytes = record.reader.read()
                text = text_bytes.decode("utf-8", errors="ignore")
                # url = record.headers.get("WARC-Target-URI")

                if not text or len(text.strip()) < 10:
                    continue

                lang, lang_conf = identify_language(text)
                if lang != "en":
                    stats["filtered_non_english"] += 1
                    continue

                nsfw_label, nsfw_conf = classify_nsfw(text)
                if nsfw_label == "nsfw":
                    stats["filtered_nsfw"] += 1
                    continue

                toxic_label, toxic_conf = classify_toxic(text)
                if toxic_label == "toxic":
                    stats["filtered_toxic"] += 1
                    continue

                if not gopher_quality_filter(text, langid="en"):
                    stats["filtered_gopher_quality"] += 1
                    continue

                # quality_label, quality_conf = paloma_quality(text)
                # if quality_label == "lq":
                #     stats["filtered_paloma_quality"] += 1
                #     continue

                # text = mask_pii(text)

                # output_record = {
                #     "text": text,
                #     "id": record.record_id[10:-1],
                #     "added": record.record_date.isoformat() if record.record_date else None,
                #     "source": "cc2604",
                #     "subdomain": extractor(url=url).fqdn,
                #     "metadata": {},
                # }
                # out.write(json.dumps(output_record) + "\n")
                out.write(text + RECORD_SEPARATOR)
                stats["kept"] += 1

            except Exception:
                continue

    return stats


# Setup
input_directory_path = "data/CC26/wet_files"
output_directory_path = "data/CC26/filter_cc"
num_cpus = len(os.sched_getaffinity(0))
wet_filepaths = sorted(os.listdir(input_directory_path))
os.makedirs(output_directory_path, exist_ok=True)

aggregate_stats = {
    "total_records": 0,
    "kept": 0,
    "filtered_non_english": 0,
    "filtered_nsfw": 0,
    "filtered_toxic": 0,
    "filtered_gopher_quality": 0,
    # "filtered_paloma_quality": 0,
}

# Submit all jobs
with concurrent.futures.ProcessPoolExecutor(max_workers=num_cpus) as executor:
    futures = {}
    for wet_filepath in wet_filepaths:
        input_path = os.path.join(input_directory_path, wet_filepath)
        output_path = os.path.join(output_directory_path, wet_filepath.replace(".warc.wet.gz", ".txt"))
        future = executor.submit(process_single_wet_file, input_path, output_path)
        futures[future] = wet_filepath

    # Process as they complete
    for future in tqdm(
        concurrent.futures.as_completed(futures), total=len(futures), desc="Processing"
    ):
        try:
            file_stats = future.result()
            for key in aggregate_stats:
                aggregate_stats[key] += file_stats[key]
        except Exception as e:
            print(f"Error: {futures[future]}: {e}")

# Print stats
print("\n" + "=" * 60)
print("Final Statistics:")
print(json.dumps(aggregate_stats, indent=4))
print("=" * 60)
