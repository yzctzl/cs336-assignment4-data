import os
import re
import mmh3
import unicodedata

from collections import defaultdict
from functools import partial
from itertools import combinations
from multiprocessing import Pool
from pathlib import Path


# Precompile regex for punct and space
PUNCT_RE = re.compile(r"[^\w\s]")
SPACE_RE = re.compile(r"\s+")


def cluster_duplicates(pairs, ngrams_map, threshold):
    """
    Union-Find clustering: group duplicate files into clusters.

    For each candidate pair, verify Jaccard similarity and merge clusters.
    Returns set of duplicate files (non-root nodes in the forest).
    """
    parent = {}

    def find(i):
        """Find root with path compression: flatten tree structure."""
        # Traverse to root
        root = i
        while parent.get(root, root) != root:
            root = parent[root]

        # Path compression - make all nodes point directly to root
        while parent.get(i, i) != root:
            new_p = parent[i]
            parent[i] = root
            i = new_p
        return root

    # Process each candidate pair
    for f1, f2 in pairs:
        r1, r2 = find(f1), find(f2)

        # Skip if already in same cluster (optimization: avoid redundant Jaccard)
        if r1 == r2:
            continue

        # Verify Jaccard similarity between n-gram sets
        s1, s2 = ngrams_map[f1], ngrams_map[f2]
        inter = len(s1 & s2)
        union_size = len(s1) + len(s2) - inter

        # Merge clusters if similarity exceeds threshold
        if union_size > 0 and (inter / union_size) >= threshold:
            parent[r1] = r2  # Link cluster root r1 to r2

    # Return duplicates: files that are NOT their own root
    return {f for f in parent if find(f) != f}


def find_lsh_candidates(sigs, num_bands, num_hashes):
    """LSH bucketing to find candidate duplicate pairs."""
    if not sigs:
        return set()

    # Pre-calculate band boundaries
    r = num_hashes // num_bands
    bands = [slice(b * r, (b + 1) * r) for b in range(num_bands)]

    # Group paths into buckets by band signatures
    buckets = defaultdict(list)
    for path, sig in sigs.items():
        for i, b_slice in enumerate(bands):
            # Using hash() here keeps the dictionary keys small
            buckets[(i, hash(tuple(sig[b_slice])))].append(path)

    # Collect pairs from buckets with more than one path
    pairs = set()
    for bucket in buckets.values():
        if len(bucket) > 1:
            # Use sorted to ensure (A, B) is same as (B, A)
            for p1, p2 in combinations(sorted(bucket), 2):
                pairs.add((p1, p2))

    return pairs


def compute_minhash(ngrams, num_hashes):
    """Fast MinHash using mmh3 with seed-based hashing."""
    if not ngrams:
        return [0] * num_hashes

    mins = [0xFFFFFFFF] * num_hashes
    for ngram in ngrams:
        for seed in range(num_hashes):
            h = mmh3.hash(ngram, seed, signed=False)
            if h < mins[seed]:
                mins[seed] = h
    return mins


def extract_ngrams(text: str, n: int):
    """Extract word n-grams as set."""
    words = text.split()
    if len(words) < n:
        return set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def normalize_text(text):
    """NFD normalization + lowercase + remove accents/punct + normalize whitespace."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = PUNCT_RE.sub(" ", text)
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def build_ngrams(path: os.PathLike, n: int):
    """Worker: read file -> normalize -> extract ngrams (for Jaccard verification)."""
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = normalize_text(f.read())
    return path, extract_ngrams(text, n)


def build_signature(path: os.PathLike, n: int, num_hashes: int):
    """Worker: read file -> normalize -> extract ngrams -> compute signature."""
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = normalize_text(f.read())
    ngrams = extract_ngrams(text, n)
    sig = compute_minhash(ngrams, num_hashes)
    return path, sig


def parallel_stream_process(func, iterable, num_workers, chunksize=16, **kwargs):
    """Parallel streaming map: iterable -> {key: value}"""
    worker_func = partial(func, **kwargs) if kwargs else func

    results = {}
    with Pool(processes=num_workers) as pool:
        for key, value in pool.imap_unordered(worker_func, iterable, chunksize=chunksize):
            results[key] = value

    return results


def minhash_deduplication(
    input_files: list[os.PathLike],
    num_hashes: int,
    num_bands: int,
    ngrams: int,
    jaccard_threshold: float,
    output_directory: os.PathLike,
    num_workers: int = len(os.sched_getaffinity(0)),
):
    """MinHash deduplication"""
    out_dir = Path(output_directory)
    out_dir.mkdir(parents=True, exist_ok=True)

    # streaming build signatures in parallel
    signatures = parallel_stream_process(build_signature, input_files, num_workers, n=ngrams, num_hashes=num_hashes)

    # LSH bucketing
    candidate_pairs = find_lsh_candidates(signatures, num_bands, num_hashes)

    to_remove = set()
    if candidate_pairs:
        # compute n-grams only for candidate files
        candidate_files = {f for pair in candidate_pairs for f in pair}
        ngrams_map = parallel_stream_process(build_ngrams, candidate_files, num_workers, n=ngrams)

        # verify and cluster
        to_remove = cluster_duplicates(candidate_pairs, ngrams_map, jaccard_threshold)

    # copy non-duplicate files
    for path in input_files:
        if path not in to_remove:
            with open(path, "rb") as src:
                (out_dir / Path(path).name).write_bytes(src.read())
