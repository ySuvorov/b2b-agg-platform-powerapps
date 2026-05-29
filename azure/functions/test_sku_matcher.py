"""
test_sku_matcher.py — unit tests for the deterministic-first SKU resolver.

Covers the decision matrix the platform must get right (see ADR-004/005):
  * exact canonical-key match (incl. Cyrillic brand + EAN noise tolerance)
  * size as a HARD gate (no size / wrong size → no match)
  * the "dropped-asterisk" homologation trap → never auto-binds
  * run-flat as a price-defining discriminator
  * abbreviations the parser can't expand → Ambiguous (admin/AI), not a wrong bind

Run: `pytest azure/functions -q` (rapidfuzz is required for the match() tests).
"""

from __future__ import annotations

import pytest

import sku_matcher
from sku_matcher import canonical_key, match, parse_raw_name

# rapidfuzz powers the fuzzy stage; skip match()-level tests if it's absent
# (parse/key tests below are pure-Python and always run).
rapidfuzz = pytest.importorskip("rapidfuzz", reason="rapidfuzz needed for match()")


CATALOG = [
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


# ── Parsing (pure, no rapidfuzz) ────────────────────────────────────────────

def test_parse_size_load_speed():
    p = parse_raw_name("Michelin Pilot Sport 4 225/45 R17 94Y")
    assert (p.width, p.profile, p.diameter) == (225, 45, 17)
    assert p.load_index == 94 and p.speed_index == "Y"
    assert p.brand == "Michelin" and p.model == "Pilot Sport 4"
    assert p.homologation == "None" and p.runflat is False


def test_parse_star_is_homologation():
    p = parse_raw_name("Michelin Latitude Sport 3 245/45R20 103W XL Run on Flat *")
    assert p.homologation == "Star_BMW"
    assert p.runflat is True and p.extraload is True


def test_parse_cyrillic_brand_alias():
    p = parse_raw_name("МИШЛЕН Pilot Sport 4 S 245/35 R20 95Y XL")
    assert p.brand == "Michelin"
    assert p.extraload is True


def test_canonical_key_model_normalisation():
    # "Pilot Sport 4 S" and "Pilot Sport 4S" collapse to the same key segment
    a = parse_raw_name("Michelin Pilot Sport 4 S 245/35R20 95Y XL")
    b = parse_raw_name("Michelin Pilot Sport 4S 245/35R20 95Y XL")
    assert canonical_key(a) == canonical_key(b)


# ── Matching: exact key ─────────────────────────────────────────────────────

def test_exact_key_canonical_name():
    r = match("Michelin Pilot Sport 4 225/45 R17 94Y", CATALOG)
    assert r.decision == "ExactKey"
    assert r.method == "ExactKey"
    assert r.confidence == 1.0
    assert r.canonical_id == "c1"


def test_exact_key_with_cyrillic_brand_and_xl():
    r = match("МИШЛЕН Pilot Sport 4 S 245/35 R20 95Y XL", CATALOG)
    assert r.decision == "ExactKey"
    assert r.canonical_id == "c2"


def test_ean_noise_is_ignored():
    # A trailing EAN-13 must not break size/index parsing or the exact match.
    r = match("Michelin Pilot Sport 4 225/45 R17 94Y 3528700123456", CATALOG)
    assert r.decision == "ExactKey"
    assert r.canonical_id == "c1"


def test_runflat_exact_match_distinct_from_star():
    # RunFlat, no star → c3 (homologation None); never c4 (Star_BMW).
    r = match("Michelin Latitude Sport 3 245/45R20 103W XL RunFlat", CATALOG)
    assert r.decision == "ExactKey"
    assert r.canonical_id == "c3"


def test_star_exact_match_distinct_from_plain_runflat():
    r = match("Michelin Latitude Sport 3 245/45R20 103W XL RunFlat *", CATALOG)
    assert r.decision == "ExactKey"
    assert r.canonical_id == "c4"


# ── Matching: the homologation / run-flat trap (never auto-bind) ─────────────

def test_dropped_marker_never_autobinds():
    # Same size as c3 (RF) and c4 (RF+Star) but the raw carries NO run-flat and
    # NO homologation marker. It must NOT silently bind to either — forced to
    # the admin/AI queue. This is the "dropped-asterisk looks cheapest" trap.
    r = match("Michelin Latitude Sport 3 245/45 R20 103W XL", CATALOG)
    assert r.decision == "Ambiguous"
    assert r.canonical_id is None
    assert r.confidence < sku_matcher.FLOOR


# ── Matching: abbreviation the parser can't expand ──────────────────────────

def test_unexpanded_abbreviation_is_ambiguous_not_wrong_bind():
    # "PS4" is not expanded to "Pilot Sport 4"; with a same-size candidate (c1)
    # present, the resolver must defer (Ambiguous), never mis-auto-bind.
    r = match("MICH PS4 225/45R17 91Y", CATALOG)
    assert r.decision == "Ambiguous"
    assert r.canonical_id is None


# ── Matching: size hard gate ────────────────────────────────────────────────

def test_no_size_yields_new_candidate():
    r = match("Michelin Pilot Sport 4 94Y", CATALOG)  # no parseable size
    assert r.decision == "NewCandidate"
    assert r.canonical_id is None


def test_wrong_size_yields_new_candidate():
    r = match("Some Unknown Brand FooBar 195/65 R15 91H", CATALOG)  # size not in catalog
    assert r.decision == "NewCandidate"
    assert r.canonical_id is None
