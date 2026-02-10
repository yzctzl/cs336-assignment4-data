import regex as re
from fastwarc.warc import ArchiveIterator, WarcRecordType
from nltk.tokenize import word_tokenize
from numpy import mean

from cs336_data.filter_cc.extract_text import extract_text_from_html_bytes
from cs336_data.filter_cc.identify_language import identify_language

_NLTK_SUPPORTED_LANGUAGES = {
    "cs": "czech",
    "da": "danish",
    "nl": "dutch",
    "en": "english",
    "et": "estonian",
    "fi": "finnish",
    "fr": "french",
    "de": "german",
    "el": "greek",
    "it": "italian",
    "no": "norwegian",
    "pl": "polish",
    "pt": "portuguese",
    "ru": "russian",
    "sl": "slovene",
    "es": "spanish",
    "sv": "swedish",
    "tr": "turkish",
}

_WORD_PATTERN = re.compile(r'\w+')

def gopher_quality_filter(text: str, langid: str = "en", nltk_token: bool = True) -> bool:
    if not nltk_token:
        words = _WORD_PATTERN.findall(text)
    else:
        words = word_tokenize(text, language=_NLTK_SUPPORTED_LANGUAGES[langid])

    # rule 1: Contain less than 50 or more than 100,000 words
    if len(words) < 50 or len(words) > 100000:
        return False

    # rule 2: Have a mean word length outside the range of 3 to 10 characters
    mean_lenth = mean([len(word) for word in words])
    if mean_lenth < 3 or mean_lenth > 10:
        return False

    # rule 3: Have more than 30% of lines ending with an ellipsis ("...").
    lines = text.splitlines()
    ellipsis_count = sum(line.strip().endswith("...") for line in lines)
    if ellipsis_count >= len(lines) * 0.3:
        return False

    # rule 4: Contain less than 80% of words with at least one alphabetic character
    more_than_one = sum(1 for word in words if any(c.isalpha() for c in word))
    alpha_ratio = more_than_one / len(words)
    if alpha_ratio < 0.8:
        return False

    return True


def warc_quality(warc_file: str = "data/CC/example.warc.gz"):
    count = 200
    for record in ArchiveIterator(open(warc_file, "rb"), record_types=WarcRecordType.response):
        extracted = extract_text_from_html_bytes(record.reader.read())
        langid, _ = identify_language(extracted)
        if langid not in _NLTK_SUPPORTED_LANGUAGES:
            continue
        print(extracted)
        print(gopher_quality_filter(extracted))
        count -= 1
        if count == 0:
            break


if __name__ == "__main__":
    warc_quality()
