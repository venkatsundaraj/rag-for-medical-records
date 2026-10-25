"""Validate the claims golden dataset before trusting any number built on it.

    python -m scripts.validate_claims data/golden/claims.jsonl

Checks, in order of severity:
  1. every non-comment line parses as JSON and has the required fields
  2. claim_ids are unique
  3. label is one of the three allowed values
  4. label <-> evidence consistency:
       supported / contradicted  ->  at least one evidence entry
       no_evidence               ->  evidence must be empty
  5. every evidence source file exists in data/corpus/
  6. every evidence quote appears VERBATIM in its source file
     (with a whitespace-normalized retry, so the report distinguishes
      "quote is wrong" from "quote is right but wrapped/spaced differently")

Exit code 0 = dataset clean. Anything else = fix before task 2.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

CORPUS_DIR = Path("data/corpus")
LABELS = {"supported", "contradicted", "no_evidence"}
REQUIRED_FIELDS = {"claim_id", "claim", "label", "evidence", "origin"}


def normalize(text: str) -> str:
    """Collapse all whitespace runs to single spaces.

    Markdown sources wrap lines; a quote copied from a rendered view may
    differ from the file only in where the newlines fall. Normalizing
    both sides tells us whether a mismatch is real or cosmetic.
    """
    return re.sub(r"\s+", " ", text)


def load_corpus() -> dict[str, str]:
    """Map file NAME -> content for every corpus file.

    Keyed by name (async.md) rather than path, since the dataset
    references bare names. Flags duplicate names, which would make
    a bare name ambiguous.
    """
    files: dict[str, str] = {}
    for path in sorted(CORPUS_DIR.rglob("*.md")):
        if path.name in files:
            print(f"WARNING: duplicate corpus filename {path.name} — evidence 'source' is ambiguous")
        files[path.name] = path.read_text(encoding="utf-8")
    return files


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    dataset_path = Path(sys.argv[1])

    corpus = load_corpus()
    print(f"corpus: {len(corpus)} files loaded from {CORPUS_DIR}/")

    errors: list[str] = []      # must fix
    warnings: list[str] = []    # should look at
    rows: list[dict] = []

    # -- 1. parse ------------------------------------------------------
    for lineno, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as e:
            errors.append(f"line {lineno}: invalid JSON ({e})")
            continue
        if not isinstance(row, dict):
            errors.append(f"line {lineno}: not a JSON object")  # the `null` lesson
            continue
        missing = REQUIRED_FIELDS - row.keys()
        if missing:
            errors.append(f"line {lineno}: missing fields {sorted(missing)}")
            continue
        rows.append(row)

    # -- 2. unique ids -------------------------------------------------
    id_counts = Counter(r["claim_id"] for r in rows)
    for cid, n in id_counts.items():
        if n > 1:
            errors.append(f"{cid}: claim_id appears {n} times")

    # -- 3..6. per-row checks ------------------------------------------
    for r in rows:
        cid, label, evidence = r["claim_id"], r["label"], r["evidence"]

        if label not in LABELS:
            errors.append(f"{cid}: unknown label {label!r}")
            continue

        if label == "no_evidence":
            if evidence:
                errors.append(f"{cid}: no_evidence but has {len(evidence)} evidence entries")
            continue  # nothing to look up for this class

        if not evidence:
            errors.append(f"{cid}: label is {label} but evidence is empty")
            continue

        for ev in evidence:
            source, quote = ev.get("source"), ev.get("quote", "")
            if source not in corpus:
                errors.append(f"{cid}: source file {source!r} not found in corpus")
                continue
            content = corpus[source]
            if quote in content:
                continue  # verbatim: the gold standard
            if normalize(quote) in normalize(content):
                warnings.append(
                    f"{cid}: quote matches {source} only after whitespace normalization "
                    f"— fine for the judge, but re-copy it from the file if you want verbatim"
                )
            else:
                errors.append(f"{cid}: quote NOT FOUND in {source}: {quote[:70]!r}...")

    # -- report --------------------------------------------------------
    counts = Counter(r["label"] for r in rows if r["label"] in LABELS)
    origins = Counter(r["origin"] for r in rows)
    print(f"\nrows: {len(rows)}")
    print("labels: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("origin: " + ", ".join(f"{k}={v}" for k, v in sorted(origins.items())))

    if warnings:
        print(f"\n--- {len(warnings)} warnings ---")
        for w in warnings:
            print(f"  ~ {w}")
    if errors:
        print(f"\n--- {len(errors)} ERRORS ---")
        for e in errors:
            print(f"  ✗ {e}")
        print("\nDataset NOT clean. Fix errors before building on it.")
        return 1

    print("\nDataset clean. Task 1 can close after your manual label review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())