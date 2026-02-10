from fasttext.FastText import load_model

model = load_model("data/classifiers/wiki_vs_cc.ftz")


def classify_quality(text: str) -> tuple[str, float]:
    clean_text = " ".join(text.split())
    labels, probs = model.predict(clean_text, k=1)
    print(labels, probs)

    label = labels[0].removeprefix("__label__")
    score = probs[0]

    return (label, score)
