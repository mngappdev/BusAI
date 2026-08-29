"""Resolving what a passenger actually says into a place on the map.

The kiosk serves a Singapore crowd that says "CGH" for Changi General Hospital,
"白沙" for White Sands, and "eh how to go Tampines Mall ah". OneMap's search is
English and literal, so all three used to miss.
"""

import json
import re
from pathlib import Path

import pytest

from bus_engine import BusSmartEngine

BASE_DIR = Path(__file__).resolve().parent.parent

# Singapore's bounding box, generously drawn.
SG_LAT = (1.15, 1.48)
SG_LON = (103.6, 104.1)


@pytest.fixture(scope="module")
def engine():
    return BusSmartEngine()


@pytest.fixture(scope="module")
def aliases():
    with open(BASE_DIR / "places_aliases.json", encoding="utf-8") as f:
        return json.load(f)["places"]


def top(engine, query):
    results = engine.resolve_place(query)
    return results[0] if results else None


# ─── Chinese ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query,expected_id", [
    ("樟宜综合医院", "changi-general-hospital"),
    ("白沙购物广场", "white-sands"),
    ("樟宜机场", "changi-airport"),
    ("新加坡中央医院", "singapore-general-hospital"),
    ("滨海湾金沙", "marina-bay-sands"),
])
def test_chinese_names_resolve(engine, query, expected_id):
    hit = top(engine, query)
    assert hit and hit["id"] == expected_id, f"{query} -> {hit and hit['id']}"


# ─── Abbreviations locals actually use ────────────────────────────────────

@pytest.mark.parametrize("query,expected_id", [
    ("cgh", "changi-general-hospital"),
    ("sgh", "singapore-general-hospital"),
    ("ttsh", "tan-tock-seng-hospital"),
    ("kkh", "kk-womens-and-childrens-hospital"),
    ("nuh", "national-university-hospital"),
    ("mbs", "marina-bay-sands"),
])
def test_local_abbreviations_resolve(engine, query, expected_id):
    hit = top(engine, query)
    assert hit and hit["id"] == expected_id, f"{query} -> {hit and hit['id']}"


# ─── Singlish ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("query,expected_id", [
    ("eh i wanna go CGH lah", "changi-general-hospital"),
    ("how to go tampines mall ah", "tampines-mall"),
    ("take me to white sands hor", "white-sands"),
    ("i want go changi airport leh", "changi-airport"),
    ("go bugis junction lor", "bugis-junction"),
    ("带我去白沙购物广场", "white-sands"),
    ("我要去樟宜机场", "changi-airport"),
    ("去牛车水吧", "chinatown"),
    ("我要去樟宜机场怎么走", "changi-airport"),
    ("到淡滨尼购物中心", "tampines-mall"),
])
def test_singlish_and_lead_ins_are_stripped(engine, query, expected_id):
    hit = top(engine, query)
    assert hit and hit["id"] == expected_id, f"{query} -> {hit and hit['id']}"


# ─── The counter-examples that decide whether this is safe ────────────────
# Particle stripping runs only after a clean match fails. Reversing that order
# eats the "one" in One Raffles Place and the "can" in Canberra.

@pytest.mark.parametrize("query,expected_id", [
    ("one raffles place", "one-raffles-place"),
    ("canberra", "canberra-mrt"),
])
def test_real_names_containing_particles_survive(engine, query, expected_id):
    hit = top(engine, query)
    assert hit and hit["id"] == expected_id, (
        f"{query} was mangled by particle stripping -> {hit and hit['id']}"
    )


def test_particles_are_only_stripped_when_a_clean_match_fails(engine):
    """Same word, two roles: 'one' is a particle in the first, a name in the second."""
    assert top(engine, "go tampines mall one")["id"] == "tampines-mall"
    assert top(engine, "one raffles place")["id"] == "one-raffles-place"


# ─── Word-form normalisation ──────────────────────────────────────────────

@pytest.mark.parametrize("query,expected_id", [
    ("pasir ris stn", "pasir-ris-mrt"),
    ("pasir ris mrt", "pasir-ris-mrt"),
    ("pasir ris int", "pasir-ris-bus-interchange"),
    ("pasir ris poly", "pasir-ris-polyclinic"),
    ("changi hosp", "changi-general-hospital"),
])
def test_common_short_forms_resolve(engine, query, expected_id):
    hit = top(engine, query)
    assert hit and hit["id"] == expected_id, f"{query} -> {hit and hit['id']}"


# ─── Ranking ──────────────────────────────────────────────────────────────

def test_exact_alias_outranks_partial_match(engine):
    results = engine.resolve_place("tampines mall")
    assert results[0]["id"] == "tampines-mall"
    assert results[0]["score"] > (results[1]["score"] if len(results) > 1 else 0)


def test_results_carry_why_they_matched(engine):
    hit = top(engine, "cgh")
    assert hit["matched_alias"] == "cgh"
    assert hit["score"] > 0


def test_limit_is_respected(engine):
    assert len(engine.resolve_place("tampines", limit=2)) <= 2


# ─── Robustness ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("query", ["", "   ", None, "zzzzzzzz nonexistent place"])
def test_unresolvable_input_returns_empty_without_throwing(engine, query):
    assert engine.resolve_place(query) == []


def test_case_and_punctuation_are_ignored(engine):
    for query in ["CGH", "c.g.h.", "  Cgh  ", "C G H"]:
        hit = top(engine, query)
        assert hit and hit["id"] == "changi-general-hospital", f"{query!r} missed"


# ─── Data integrity ───────────────────────────────────────────────────────

def test_every_place_has_the_required_fields(aliases):
    for place in aliases:
        for field in ("id", "name_en", "name_zh", "lat", "lon", "category", "aliases"):
            assert field in place, f"{place.get('id')} is missing {field}"
        assert place["aliases"], f"{place['id']} has no aliases"


def test_all_coordinates_are_inside_singapore(aliases):
    for place in aliases:
        assert SG_LAT[0] <= place["lat"] <= SG_LAT[1], f"{place['id']} latitude {place['lat']}"
        assert SG_LON[0] <= place["lon"] <= SG_LON[1], f"{place['id']} longitude {place['lon']}"


def test_ids_are_unique(aliases):
    ids = [p["id"] for p in aliases]
    assert len(ids) == len(set(ids)), "duplicate place id"


def test_no_alias_maps_to_two_places(aliases, engine):
    """An ambiguous alias silently sends people to the wrong place."""
    owner = {}
    for place in aliases:
        for alias in place["aliases"]:
            key = engine.normalize_query(alias)
            assert key not in owner or owner[key] == place["id"], (
                f"alias {alias!r} is claimed by both {owner.get(key)} and {place['id']}"
            )
            owner[key] = place["id"]


def test_ids_are_slugs(aliases):
    for place in aliases:
        assert re.fullmatch(r"[a-z0-9-]+", place["id"]), f"{place['id']} is not a slug"


def test_the_curated_list_is_actually_curated(aliases):
    """A handful of entries is not the agreed scope."""
    assert len(aliases) >= 150, f"only {len(aliases)} places"
    categories = {p["category"] for p in aliases}
    for expected in ("hospital", "mall", "mrt", "airport", "government", "landmark"):
        assert expected in categories, f"no {expected} entries"


# ─── The demo journey must keep working ───────────────────────────────────

def test_changi_airport_still_lands_on_the_demo_destination(engine):
    """index.html used to hardcode this; the alias table takes over."""
    hit = top(engine, "changi airport")
    assert hit["id"] == "changi-airport"
    assert abs(hit["lat"] - 1.3575) < 0.02
    assert abs(hit["lon"] - 103.9885) < 0.02


# ─── HTTP endpoint ────────────────────────────────────────────────────────

def test_endpoint_resolves_chinese_and_singlish():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    for query, expected_id in [
        ("樟宜综合医院", "changi-general-hospital"),
        ("eh i wanna go CGH lah", "changi-general-hospital"),
        ("white sands", "white-sands"),
    ]:
        body = client.get("/api/v1/resolve-place", params={"q": query}).json()
        assert body["results"], f"{query} returned nothing"
        assert body["results"][0]["id"] == expected_id


def test_endpoint_returns_empty_results_for_nonsense():
    from fastapi.testclient import TestClient
    from main import app

    body = TestClient(app).get("/api/v1/resolve-place", params={"q": "zzzz"}).json()
    assert body["results"] == []


def test_endpoint_rejects_an_empty_query():
    from fastapi.testclient import TestClient
    from main import app

    assert TestClient(app).get("/api/v1/resolve-place", params={"q": ""}).status_code == 422
