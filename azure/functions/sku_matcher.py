"""
sku_matcher.py — deterministic-first SKU resolution engine.

Pure-Python, framework-free so it is unit-testable outside the Azure Functions
runtime (`python3 sku_matcher.py` runs the self-test at the bottom).

Pipeline (see docs/adr/004 + 005 and the plan):

    parse_raw_name(raw)  → ParsedTire (structured attributes)
    canonical_key(parsed) → "brand|model|W|P|D|load|speed|homolog|runflat|xl"
    match(raw_name, catalog) → MatchResult (decision + ranked candidates)

Design rules that matter for the domain:
  * Tyre SIZE (width/profile/diameter) is a HARD gate — a size mismatch
    disqualifies a candidate outright.
  * HOMOLOGATION tokens (*, MO, N0, LR, …) are part of the canonical key, NOT
    fuzzy noise. A homologation mismatch is capped below FLOOR so a "*" vs
    non-"*" pair can never auto-bind — it is forced into the admin queue.
    This is the "dropped-asterisk looks cheapest" trap the platform must catch.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Optional


def _env_float(name: str, default: float) -> float:
    """Read a 0..1 threshold from the environment, falling back to *default*."""
    try:
        return float(os.environ[name])
    except (KeyError, TypeError, ValueError):
        return default


# ── Decision thresholds (0..1). Overridable via env vars in the Function. ──────
AUTO = _env_float("SKU_MATCH_AUTO", 0.92)     # top score ≥ AUTO  → eligible to auto-bind
MARGIN = _env_float("SKU_MATCH_MARGIN", 0.08)  # top must beat runner-up by ≥ MARGIN
FLOOR = _env_float("SKU_MATCH_FLOOR", 0.70)    # below FLOOR → brand-new product candidate

# ── Vocabularies ───────────────────────────────────────────────────────────────

# Homologation / OEM-approval token → canonical enum label.
# Absence of any token is itself a value ("None").
HOMOLOGATION: dict[str, str] = {
    "*": "Star_BMW",
    "MO": "MO_Mercedes",
    "MO1": "MO_Mercedes",
    "MOE": "MOE_Mercedes",   # MO Extended (also runflat) — kept distinct
    "N0": "N0_Porsche",
    "N1": "N1_Porsche",
    "N2": "N1_Porsche",
    "AO": "AO_Audi",
    "AOE": "AO_Audi",
    "RO1": "AO_Audi",
    "LR": "LR_LandRover",
    "VOL": "VOL_Volvo",
    "MGT": "MGT_Maserati",
}

# Run-flat synonyms (FR = rim-flange protector, deliberately NOT here).
RUNFLAT_TOKENS = {
    "RUNFLAT", "RUNONFLAT", "ROF", "RFT", "SSR", "ZP", "ZPS", "DSST", "EMT",
}
RUNFLAT_PHRASES = ("RUN ON FLAT", "RUN FLAT", "RUN-FLAT")

EXTRALOAD_TOKENS = {"XL", "EXTRALOAD"}
EXTRALOAD_PHRASES = ("EXTRA LOAD", "EXTRA-LOAD")

# Brand canonical → recognised aliases (incl. Cyrillic transliteration).
BRAND_ALIASES: dict[str, list[str]] = {
    "Michelin":     ["MICHELIN", "МИШЛЕН", "МИШЛИН", "MICH", "MICHLN"],
    "Continental":  ["CONTINENTAL", "КОНТИНЕНТАЛЬ", "CONTI", "CONT"],
    "Bridgestone":  ["BRIDGESTONE", "БРИДЖСТОУН", "BRIDGE", "BSTONE", "BS"],
    "Nokian":       ["NOKIAN", "НОКИАН", "NOK"],
    "Pirelli":      ["PIRELLI", "ПИРЕЛЛИ", "PIR"],
    "Goodyear":     ["GOODYEAR", "ГУДЪЕР", "GDYR", "GY"],
}
# alias → canonical brand (longest-first so "MICHELIN" wins before "MICH")
_BRAND_LOOKUP: list[tuple[str, str]] = sorted(
    ((alias, brand) for brand, aliases in BRAND_ALIASES.items() for alias in aliases),
    key=lambda t: -len(t[0]),
)

SPEED_LETTERS = set("HQRSTUVWYZ")  # common passenger speed-rating symbols

# size like 225/45 R17, 225-45-17, 225 45 17, 285/40R23
_SIZE_RE = re.compile(r"(\d{3})\s*[/\- ]\s*(\d{2})\s*[/\- ]?\s*[Rr]?\s*(\d{2})\b")
# load+speed like 91Y, 103W, 115Y (after size is removed)
_INDEX_RE = re.compile(r"\b(\d{2,3})\s?([A-Z]{1,2})\b")


@dataclass
class ParsedTire:
    brand: str = ""
    model: str = ""
    width: Optional[int] = None
    profile: Optional[int] = None
    diameter: Optional[int] = None
    load_index: Optional[int] = None
    speed_index: str = ""
    homologation: str = "None"
    runflat: bool = False
    extraload: bool = False
    raw: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Candidate:
    canonical_id: str
    canonical_name: str
    score: float
    size_match: bool
    homolog_match: bool
    runflat_match: bool


@dataclass
class MatchResult:
    decision: str          # ExactKey | Fuzzy | Ambiguous | NewCandidate
    method: str            # ExactKey | Fuzzy | None
    confidence: float
    canonical_id: Optional[str]
    canonical_name: Optional[str]
    parsed: dict = field(default_factory=dict)
    candidates: list[dict] = field(default_factory=list)


# ── Parsing ─────────────────────────────────────────────────────────────────────

def _strip_diacritics(s: str) -> str:
    # leave Cyrillic intact (we match it directly); only normalise combining marks
    return unicodedata.normalize("NFKC", s)


def parse_raw_name(raw: str) -> ParsedTire:
    """Extract structured tyre attributes from a free-text supplier name."""
    out = ParsedTire(raw=raw)
    work = _strip_diacritics(raw).upper()

    # homologation '*' is a literal token; isolate it before tokenising
    has_star = "*" in work
    work = work.replace("*", " ")

    # phrases first (multi-word) so they don't fragment
    for ph in RUNFLAT_PHRASES:
        if ph in work:
            out.runflat = True
            work = work.replace(ph, " ")
    for ph in EXTRALOAD_PHRASES:
        if ph in work:
            out.extraload = True
            work = work.replace(ph, " ")

    # size
    m = _SIZE_RE.search(work)
    if m:
        out.width, out.profile, out.diameter = (int(m.group(i)) for i in (1, 2, 3))
        work = work[: m.start()] + " " + work[m.end():]

    # load + speed index (only accept plausible speed letters)
    for im in _INDEX_RE.finditer(work):
        load_s, letters = im.group(1), im.group(2)
        if letters and letters[0] in SPEED_LETTERS and len(letters) <= 2:
            out.load_index = int(load_s)
            out.speed_index = letters
            work = work[: im.start()] + " " + work[im.end():]
            break

    # tokenise the remainder
    tokens = [t for t in re.split(r"[\s,/\-]+", work) if t]

    homolog = "None"
    residual: list[str] = []
    brand_found = ""
    for tok in tokens:
        if tok in HOMOLOGATION:
            homolog = HOMOLOGATION[tok]
            continue
        if tok in RUNFLAT_TOKENS:
            out.runflat = True
            continue
        if tok in EXTRALOAD_TOKENS:
            out.extraload = True
            continue
        # Drop standalone long digit runs — EAN-8/13 barcodes and supplier
        # article numbers are noise, not part of the model designation.
        if tok.isdigit() and len(tok) >= 6:
            continue
        residual.append(tok)

    if has_star and homolog == "None":
        homolog = "Star_BMW"
    out.homologation = homolog

    # brand: match the longest known alias anywhere in the residual stream
    residual_str = " ".join(residual)
    for alias, brand in _BRAND_LOOKUP:
        if re.search(rf"\b{re.escape(alias)}\b", residual_str):
            brand_found = brand
            residual_str = re.sub(rf"\b{re.escape(alias)}\b", " ", residual_str)
            break
    out.brand = brand_found

    # model = whatever readable text remains
    out.model = re.sub(r"\s+", " ", residual_str).strip().title()
    return out


def _model_key(model: str) -> str:
    """Space/case-insensitive model token: 'Pilot Sport 4 S' == 'Pilot Sport 4S'."""
    return re.sub(r"[^A-Z0-9]", "", model.upper())


def canonical_key(p: ParsedTire) -> str:
    return "|".join([
        (p.brand or "").upper(),
        _model_key(p.model),
        str(p.width or ""),
        str(p.profile or ""),
        str(p.diameter or ""),
        str(p.load_index or ""),
        (p.speed_index or "").upper(),
        p.homologation,
        "RF" if p.runflat else "",
        "XL" if p.extraload else "",
    ])


# ── Matching ─────────────────────────────────────────────────────────────────────

def _parsed_from_catalog(item: dict) -> ParsedTire:
    """Build a ParsedTire from a canonical-catalog dict (Dataverse / CSV shape)."""
    return ParsedTire(
        brand=item.get("brand", ""),
        model=item.get("model", ""),
        width=_as_int(item.get("width")),
        profile=_as_int(item.get("profile")),
        diameter=_as_int(item.get("diameter")),
        load_index=_as_int(item.get("load_index")),
        speed_index=item.get("speed_index", "") or "",
        homologation=item.get("homologation", "None") or "None",
        runflat=_as_bool(item.get("runflat")),
        extraload=_as_bool(item.get("extraload")),
    )


def _as_int(v) -> Optional[int]:
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _as_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes")


def match(raw_name: str, catalog: list[dict]) -> MatchResult:
    """Resolve *raw_name* against *catalog* (list of canonical dicts).

    Each catalog dict needs: id, name, brand, model, width, profile, diameter,
    load_index, speed_index, homologation, runflat, extraload.
    """
    from rapidfuzz import fuzz  # lazy: keeps parse-only use importable without it

    parsed = parse_raw_name(raw_name)
    raw_key = canonical_key(parsed)
    raw_model_key = _model_key(parsed.model)

    # Stage 1 — exact canonical key
    for item in catalog:
        if canonical_key(_parsed_from_catalog(item)) == raw_key:
            return MatchResult(
                decision="ExactKey", method="ExactKey", confidence=1.0,
                canonical_id=str(item.get("id", "")),
                canonical_name=item.get("name", ""),
                parsed=parsed.to_dict(),
                candidates=[],
            )

    # Stage 2 — weighted fuzzy rank with hard gates
    scored: list[Candidate] = []
    for item in catalog:
        cp = _parsed_from_catalog(item)
        size_match = (
            parsed.width == cp.width
            and parsed.profile == cp.profile
            and parsed.diameter == cp.diameter
        )
        if not size_match:
            continue  # HARD GATE: wrong size cannot be the same product

        brand_ok = (not parsed.brand) or (parsed.brand.upper() == cp.brand.upper())
        model_score = fuzz.token_set_ratio(raw_model_key, _model_key(cp.model)) / 100.0
        score = model_score * (1.0 if brand_ok else 0.6)

        # Price-defining discriminators: a mismatch on homologation (*, MO, N0…)
        # or run-flat is a DIFFERENT product. Cap the score below FLOOR so such a
        # pair can never auto-bind — it is forced to the AI/admin path. This is
        # the "dropped-asterisk looks cheapest" trap the platform must catch.
        homolog_match = parsed.homologation == cp.homologation
        runflat_match = parsed.runflat == cp.runflat
        if not homolog_match or not runflat_match:
            score = min(score, FLOOR - 0.01)

        scored.append(Candidate(
            canonical_id=str(item.get("id", "")),
            canonical_name=item.get("name", ""),
            score=round(score, 4),
            size_match=size_match,
            homolog_match=homolog_match,
            runflat_match=runflat_match,
        ))

    scored.sort(key=lambda c: c.score, reverse=True)
    cand_dicts = [asdict(c) for c in scored[:5]]

    # No same-size candidate exists anywhere → genuinely a brand-new product.
    if not scored:
        return MatchResult(
            decision="NewCandidate", method=None, confidence=0.0,
            canonical_id=None, canonical_name=None,
            parsed=parsed.to_dict(), candidates=[],
        )

    top = scored[0]
    runner = scored[1].score if len(scored) > 1 else 0.0
    if top.score >= AUTO and (top.score - runner) >= MARGIN:
        return MatchResult(
            decision="Fuzzy", method="Fuzzy", confidence=top.score,
            canonical_id=top.canonical_id, canonical_name=top.canonical_name,
            parsed=parsed.to_dict(), candidates=cand_dicts,
        )

    # Same-size candidate(s) exist but no confident, unambiguous winner:
    # hand the residue to Stage 3 (AI tie-break) and then the admin queue.
    # This covers abbreviations the parser doesn't expand (e.g. "PS4"), close
    # collisions, and the homologation-mismatch cap (the asterisk trap).
    return MatchResult(
        decision="Ambiguous", method=None, confidence=top.score,
        canonical_id=None, canonical_name=None,
        parsed=parsed.to_dict(), candidates=cand_dicts,
    )


# ── Self-test ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    catalog = [
        {"id": "c1", "name": "Michelin Pilot Sport 4 225/45 R17", "brand": "Michelin",
         "model": "Pilot Sport 4", "width": 225, "profile": 45, "diameter": 17,
         "load_index": 94, "speed_index": "Y", "homologation": "None",
         "runflat": False, "extraload": False},
        {"id": "c2", "name": "Michelin Pilot Sport 4 S 245/35 R20", "brand": "Michelin",
         "model": "Pilot Sport 4 S", "width": 245, "profile": 35, "diameter": 20,
         "load_index": 95, "speed_index": "Y", "homologation": "None",
         "runflat": False, "extraload": True},
        {"id": "c3", "name": "Michelin Latitude Sport 3 245/45 R20 RunFlat", "brand": "Michelin",
         "model": "Latitude Sport 3", "width": 245, "profile": 45, "diameter": 20,
         "load_index": 103, "speed_index": "W", "homologation": "None",
         "runflat": True, "extraload": True},
        {"id": "c4", "name": "Michelin Latitude Sport 3 245/45 R20 RunFlat * (BMW)", "brand": "Michelin",
         "model": "Latitude Sport 3", "width": 245, "profile": 45, "diameter": 20,
         "load_index": 103, "speed_index": "W", "homologation": "Star_BMW",
         "runflat": True, "extraload": True},
    ]

    tests = [
        "MICH PS4 225/45R17 91Y",                                   # → c1 ExactKey-ish (Fuzzy)
        "МИШЛЕН Pilot Sport 4 S 245/35 R20 95Y XL",                 # → c2 (Cyrillic + 4 S)
        "MICHELIN Latitude Sport 3 245/45R20 103W XL Run on Flat *",# → c4 (BMW)
        "MICHELIN Latitude Sport 3 245/45R20 103W XL Run on Flat",  # → c3 (no homolog)
        "Michelin Latitude Sport 3 245/45 R20 103W XL",             # → Ambiguous (no RF marker)
        "Some Unknown Brand FooBar 195/65 R15 91H",                 # → NewCandidate
    ]
    for t in tests:
        try:
            r = match(t, catalog)
            print(f"\nRAW: {t}")
            print(f"  parsed: {json.dumps(r.parsed, ensure_ascii=False)}")
            print(f"  decision={r.decision} method={r.method} conf={r.confidence} "
                  f"→ {r.canonical_name}")
        except ImportError:
            # rapidfuzz not installed → show parse only
            p = parse_raw_name(t)
            print(f"\nRAW: {t}\n  parsed: {json.dumps(p.to_dict(), ensure_ascii=False)}"
                  f"\n  key: {canonical_key(p)}")
