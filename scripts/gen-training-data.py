#!/usr/bin/env python3
"""
gen-training-data.py
====================
Generates data/ai-builder/sku-training-data.csv for the AI Builder Custom Text
Classification model (the "second-opinion" AI in the layered SKU matcher).

Deterministic + reproducible: reads the canonical catalog and emits several
realistic raw-name variants per product (orthographic noise, Cyrillic brand,
curated abbreviations, and — for OEM/run-flat products — the homologation
tokens). Each row is "Text,Label" where Label is the canonical b2b_name.

This replaces the previously hand-maintained CSV (which lived untracked under
the Koofr-synced path and was lost). Re-run any time the catalog changes:

    python3 scripts/gen-training-data.py
"""

from __future__ import annotations

import csv
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEED = REPO / "data" / "seed"
OUT_DIR = REPO / "data" / "ai-builder"
OUT = OUT_DIR / "sku-training-data.csv"

# Brand → Cyrillic transliteration used by Russian suppliers.
CYRILLIC = {
    "Michelin": "МИШЛЕН", "Continental": "КОНТИНЕНТАЛЬ",
    "Bridgestone": "БРИДЖСТОУН", "Nokian": "НОКИАН",
    "Pirelli": "ПИРЕЛЛИ", "Goodyear": "ГУДЪЕР",
}
# Brand short codes.
BRAND_ABBR = {
    "Michelin": "MICH", "Continental": "CONT", "Bridgestone": "BRIDGE",
    "Nokian": "NOK", "Pirelli": "PIR", "Goodyear": "GY",
}
# Curated model abbreviations (only emit an abbrev variant when known — keeps quality high).
MODEL_ABBR = {
    "Pilot Sport 4": "PS4", "Pilot Sport 4 S": "PS4 S", "CrossClimate 2": "CC2",
    "Alpin 6": "A6", "Latitude Sport 3": "LS3", "PremiumContact 6": "PC6",
    "WinterContact TS860": "WC TS860", "AllSeasonContact 2": "ASC2",
    "Turanza T005": "T005", "Blizzak LM005": "LM005", "Weather Control A005": "WC A005",
    "Hakkapeliitta 10": "Hakka 10", "Wetproof": "WP",
}
# Run-flat spelling variants to sprinkle in.
RF_FORMS = ["RunFlat", "Run on Flat", "ROF", "SSR"]
HOMOLOG_TOKEN = {
    "Star_BMW": "*", "MO_Mercedes": "MO", "MOE_Mercedes": "MOE",
    "N0_Porsche": "N0", "N1_Porsche": "N1", "AO_Audi": "AO",
    "LR_LandRover": "LR", "VOL_Volvo": "VOL", "MGT_Maserati": "MGT",
}


def _size_forms(w, p, d) -> list[str]:
    return [f"{w}/{p} R{d}", f"{w}/{p}R{d}", f"{w}-{p}-{d}", f"{w} {p} {d}"]


def variants(row: dict) -> list[str]:
    brand = row["b2b_brand"]
    model = row["b2b_model"]
    w, p, d = row["b2b_width"], row["b2b_profile"], row["b2b_diameter"]
    load, speed = row.get("b2b_load_index", ""), row.get("b2b_speed_index", "")
    homolog = (row.get("b2b_homologation", "") or "None")
    runflat = str(row.get("b2b_runflat", "")).lower() in ("1", "true", "yes")
    xl = str(row.get("b2b_extraload", "")).lower() in ("1", "true", "yes")

    sizes = _size_forms(w, p, d)
    idx = f"{load}{speed}".strip()
    suffix_tokens: list[str] = []
    if xl:
        suffix_tokens.append("XL")
    if runflat:
        suffix_tokens.append(RF_FORMS[0])
    if homolog != "None":
        suffix_tokens.append(HOMOLOG_TOKEN.get(homolog, ""))
    suffix = " ".join(t for t in suffix_tokens if t)

    out: list[str] = []
    # 1. clean canonical-ish
    out.append(f"{brand} {model} {sizes[0]} {idx} {suffix}".strip())
    # 2. no-space size, brand abbrev
    out.append(f"{BRAND_ABBR.get(brand, brand)} {model} {sizes[1]} {idx} {suffix}".strip())
    # 3. dash size
    out.append(f"{brand} {model} {sizes[2]} {suffix}".strip())
    # 4. Cyrillic brand
    out.append(f"{CYRILLIC.get(brand, brand)} {model} {sizes[0]} {idx} {suffix}".strip())
    # 5. curated abbreviation (brand abbrev + model abbrev)
    if model in MODEL_ABBR:
        rf_alt = RF_FORMS[3] if runflat else ""  # SSR
        alt_suffix = " ".join(t for t in [("XL" if xl else ""),
                              rf_alt, HOMOLOG_TOKEN.get(homolog, "") if homolog != "None" else ""] if t)
        out.append(f"{BRAND_ABBR.get(brand, brand)} {MODEL_ABBR[model]} {sizes[1]} {idx} {alt_suffix}".strip())
    # de-dup, collapse double spaces
    seen, uniq = set(), []
    for v in out:
        v = " ".join(v.split())
        if v and v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((SEED / "canonicalproduct.csv").open(encoding="utf-8")))
    n_text = 0
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Text", "Label"])
        for r in rows:
            for v in variants(r):
                w.writerow([v, r["b2b_name"]])
                n_text += 1
    print(f"{OUT.relative_to(REPO)}: {n_text} rows for {len(rows)} canonical products")


if __name__ == "__main__":
    main()
