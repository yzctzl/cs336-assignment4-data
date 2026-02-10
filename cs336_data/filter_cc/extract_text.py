from fastwarc.warc import ArchiveIterator, WarcRecordType
from resiliparse.extract.html2text import extract_plain_text
from resiliparse.parse.encoding import bytes_to_str, detect_encoding


def extract_text_from_html_bytes(html_bytes: bytes) -> str:
    """takes a byte string containing HTML and returns a string containing the extracted text"""
    decoded = bytes_to_str(html_bytes, detect_encoding(html_bytes))
    return extract_plain_text(decoded, main_content=True, alt_texts=False, preserve_formatting=False, noscript=True)


def warc_extraction(warc_file: str = "data/CC/example.warc.gz"):
    output_file = "data/CC/example.extract.txt"
    output = open(output_file, "w")

    for record in ArchiveIterator(open(warc_file, "rb"), record_types=WarcRecordType.response):
        output.write(extract_text_from_html_bytes(record.reader.read()))

    output.close()


if __name__ == "__main__":
    warc_extraction()
