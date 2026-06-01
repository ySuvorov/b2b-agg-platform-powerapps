#!/usr/bin/env python3
"""
augment-training-data.py — expand sku-training-data.csv so every Label has >=10
examples (AI Builder Category classification requires the most-frequent tag to
have >=10 examples, and >=10 rows without it). The shipped CSV has 36 labels x 5.

Augmentation is MARKER-SAFE: it only swaps the brand token (spelling /
transliteration) and toggles case. It never alters size, load/speed, run-flat or
homologation markers ("*", "MO", "SSR", "RunFlat", ...), so the `*`/MO/non-marker
twin LABELS stay distinguishable in the text. This mirrors the real variation
axis the deterministic engine already handles (ADR-004): brand spelling noise.

Deterministic (no randomness): re-running overwrites the CSV with identical bytes.

Usage:
  python3 scripts/augment-training-data.py            # writes CSV (>=12/label)
  python3 scripts/augment-training-data.py --min 10   # custom floor
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "data/ai-builder/sku-training-data.csv"
MIN = 12
if "--min" in sys.argv:
    MIN = int(sys.argv[sys.argv.index("--min") + 1])

# brand spelling/transliteration groups (single-token brands)
BRAND_GROUPS = [
    ["Michelin", "MICH", "МИШЛЕН"],
    ["Continental", "CONT", "КОНТИНЕНТАЛЬ"],
]
ALIAS_TO_GROUP = {a.upper(): g for g in BRAND_GROUPS for a in g}


def brand_variants(text: str) -> list[str]:
    """Swap the leading brand token for each alias in its group (marker-safe)."""
    parts = text.split(" ", 1)
    if len(parts) != 2:
        return [text]
    first, rest = parts
    group = ALIAS_TO_GROUP.get(first.upper())
    if not group:
        return [text]
    return [f"{alias} {rest}" for alias in group]


def expand(base_texts: list[str], floor: int) -> list[str]:
    """Grow a label's variants to >= floor, deterministically, marker-safe."""
    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    # 1) originals
    for t in base_texts:
        add(t)
    # 2) brand-alias swaps
    for t in base_texts:
        for v in brand_variants(t):
            add(v)
    # 3) case variants of everything so far, until we clear the floor
    if len(out) < floor:
        for t in list(out):
            add(t.upper())
            if len(out) >= floor:
                break
    if len(out) < floor:
        for t in list(out):
            add(t.lower())
            if len(out) >= floor:
                break
    return out


def main() -> None:
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    # preserve label order of first appearance
    order: list[str] = []
    by_label: dict[str, list[str]] = {}
    for r in rows:
        text, label = r["Text"].strip(), r["Label"].strip()
        if not text or not label:
            continue
        if label not in by_label:
            by_label[label] = []
            order.append(label)
        if text not in by_label[label]:
            by_label[label].append(text)

    out_rows: list[tuple[str, str]] = []
    min_count = 10**9
    for label in order:
        variants = expand(by_label[label], MIN)
        min_count = min(min_count, len(variants))
        for v in variants:
            out_rows.append((v, label))

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Text", "Label"])
        for text, label in out_rows:
            w.writerow([text, label])

    print(f"wrote {len(out_rows)} rows, {len(order)} labels "
          f"(min {min_count}/label) -> {CSV_PATH.name}")


if __name__ == "__main__":
    main()
