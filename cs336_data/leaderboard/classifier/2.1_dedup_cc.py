import xxhash
from fastwarc.warc import ArchiveIterator, WarcRecordType


def process_wet_with_dedup(input_warc_gz, output_text_file):
    seen_line_hashes = set()

    total_records = 0
    total_lines = 0
    kept_lines = 0

    with open(output_text_file, "w", encoding="utf-8") as fout:
        with open(input_warc_gz, "rb") as stream:
            for record in ArchiveIterator(stream, record_types=WarcRecordType.conversion):
                total_records += 1

                content = record.reader.read().decode("utf-8", errors="ignore")
                lines = content.splitlines()

                record_content = []
                for line in lines:
                    clean_line = line.strip()
                    total_lines += 1

                    # dup by line
                    h = xxhash.xxh64(clean_line).digest()
                    if h not in seen_line_hashes:
                        seen_line_hashes.add(h)
                        record_content.append(clean_line)
                        kept_lines += 1

                if record_content:
                    fout.writelines(line + "\n" for line in record_content)
                    fout.write(f"\n{'=' * 30}xxx  RECORD END  xxx{'=' * 30}\n")

            if total_records % 1000:
                print(f"proceed {total_records} ...", flush=True)

    print("-" * 20, "DONE!", "-" * 20)
    print(f"output: {output_text_file}")
    print(f"record: {total_records}")
    print(f"lines: {total_lines}")
    print(f"dup_line: {kept_lines}")
    print(f"dup ratio: {1 - (kept_lines / total_lines):.2%}")


if __name__ == "__main__":
    INPUT_FILE = "data/CC26/CC-MAIN-20260112222830-20260113012830-00110-00119.warc.wet.gz"
    OUTPUT_FILE = "data/CC26/CC-MAIN-20260112222830-20260113012830-00110-00119.txt"

    process_wet_with_dedup(INPUT_FILE, OUTPUT_FILE)
