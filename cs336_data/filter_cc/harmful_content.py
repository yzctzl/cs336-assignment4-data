# pyright: reportGeneralTypeIssues=none
from typing import Any

from fasttext.FastText import load_model
from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.filter_cc.extract_text import extract_text_from_html_bytes

nsfw_model = load_model("data/classifiers/jigsaw_fasttext_bigrams_nsfw_final.bin")
hate_model = load_model("data/classifiers/jigsaw_fasttext_bigrams_hatespeech_final.bin")

def classify_nsfw(text: str) -> tuple[Any, float]:
    r = nsfw_model.predict(text.replace("\n", ""), k=3)
    label = r[0][0].removeprefix("__label__")
    return (label, r[1][0])


def classify_toxic(text: str) -> tuple[Any, float]:
    r = hate_model.predict(text.replace("\n", ""), k=3)
    label = r[0][0].removeprefix("__label__")
    return (label, r[1][0])


def warc_harmful(warc_file: str = "data/CC/example.warc.gz"):
    count = 20
    for record in ArchiveIterator(
        open(warc_file, "rb"),
        record_types=WarcRecordType.response
    ):
        extracted = extract_text_from_html_bytes(record.reader.read())
        print(extracted)
        print(classify_nsfw(extracted))
        print(classify_toxic(extracted))
        count -= 1
        if count == 0:
            break


if __name__ == "__main__":
    warc_harmful()
