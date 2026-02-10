# pyright: reportGeneralTypeIssues=none
from typing import Any

from fasttext.FastText import load_model
from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.filter_cc.extract_text import extract_text_from_html_bytes

model = load_model("data/classifiers/lid.176.bin")


def identify_language(text: str) -> tuple[Any, float]:
    r = model.predict(text.replace("\n", ""), k=3)
    lingid = r[0][0].removeprefix("__label__")
    return (lingid, r[1][0])


def warc_lang(warc_file: str = "data/CC/example.warc.gz"):
    count = 20
    for record in ArchiveIterator(open(warc_file, "rb"), record_types=WarcRecordType.response):
        extracted = extract_text_from_html_bytes(record.reader.read())
        print(extracted)
        print(identify_language(extracted))
        count -= 1
        if count == 0:
            break


if __name__ == "__main__":
    warc_lang()
