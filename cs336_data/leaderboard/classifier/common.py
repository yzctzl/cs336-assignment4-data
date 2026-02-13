import regex as re
import unicodedata


RE_DIGITS = re.compile(r"\d+")
RE_SPACES = re.compile(r"\s+")


def text_cleaner(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.split())


def normalize_text(text: str) -> str:
    # Normalization Form Komposition Composition
    text = unicodedata.normalize("NFKC", text.lower())

    clean_chars = []
    for char in text:
        cat = unicodedata.category(char)
        if cat.startswith("P") or cat.startswith("S"):
            clean_chars.append(" ")
        elif cat == "Mn":
            continue
        else:
            clean_chars.append(char)

    text = "".join(clean_chars)
    # number to 0
    # text = RE_DIGITS.sub("0", text)
    # space fold
    text = RE_SPACES.sub(" ", text).strip()

    return text
