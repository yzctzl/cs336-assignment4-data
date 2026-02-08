import difflib

import regex as re
from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.filter_cc.extract_text import extract_text_from_html_bytes

patterns = {
    "EMAIL_ADDRESS": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "PHONE_NUMBER": r"(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}",
    "IP_ADDRESS": r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}"
          r"(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
}

def mask_pii(text: str) -> str:
    for tag, pattern in patterns.items():
        text = re.sub(pattern, f"|||{tag}|||", text)
    return text


def mask_emails(text: str) -> tuple[str, int]:
    key = "EMAIL_ADDRESS"
    return re.subn(patterns[key], f"|||{key}|||", text)


def mask_phone_numbers(text: str) -> tuple[str, int]:
    key = "PHONE_NUMBER"
    return re.subn(patterns[key], f"|||{key}|||", text)


def mask_ips(text: str) -> tuple[str, int]:
    key = "IP_ADDRESS"
    return re.subn(patterns[key], f"|||{key}|||", text)


def warc_mask(warc_file: str = "data/CC/example.warc.gz"):
    count = 20
    for record in ArchiveIterator(
        open(warc_file, "rb"),
        record_types=WarcRecordType.response
    ):
        extracted = extract_text_from_html_bytes(record.reader.read())
        masked = mask_pii(extracted)
        for diff in difflib.ndiff(masked.splitlines(), extracted.splitlines()):
            print(diff)
        count -= 1
        if count == 0:
            break


if __name__ == "__main__":
    warc_mask()
