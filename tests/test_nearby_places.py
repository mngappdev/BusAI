import pytest

from bus_engine import BusSmartEngine

PASIR_RIS_INT = (1.373696, 103.94845)


@pytest.fixture(scope="module")
def engine():
    return BusSmartEngine()


def test_returns_categories_and_places(engine):
    result = engine.nearby_places(*PASIR_RIS_INT)
    assert "categories" in result
    assert "places" in result
    assert len(result["categories"]) == 3
    assert len(result["places"]) > 0


def test_every_place_has_a_valid_category(engine):
    result = engine.nearby_places(*PASIR_RIS_INT)
    category_ids = {c["id"] for c in result["categories"]}
    for place in result["places"]:
        assert place["category"] in category_ids, f"{place['id']} has unknown category {place['category']}"


def test_every_category_has_at_least_one_place(engine):
    result = engine.nearby_places(*PASIR_RIS_INT)
    used_categories = {p["category"] for p in result["places"]}
    for cat in result["categories"]:
        assert cat["id"] in used_categories, f"category {cat['id']} has no places"


def test_places_carry_computed_distance_and_walk_time(engine):
    result = engine.nearby_places(*PASIR_RIS_INT)
    for place in result["places"]:
        assert isinstance(place["distance_m"], int)
        assert place["distance_m"] >= 0
        assert isinstance(place["walk_minutes"], int)
        assert place["walk_minutes"] >= 0


def test_distance_is_computed_from_the_given_location_not_hardcoded(engine):
    # Elias Community Club is far from the interchange but very close to itself.
    near_elias = engine.nearby_places(1.3806, 103.9427)
    elias = next(p for p in near_elias["places"] if p["id"] == "elias-cc")
    assert elias["distance_m"] < 50

    from_interchange = engine.nearby_places(*PASIR_RIS_INT)
    elias_far = next(p for p in from_interchange["places"] if p["id"] == "elias-cc")
    assert elias_far["distance_m"] > 500


def test_places_are_sorted_nearest_first_within_each_category(engine):
    result = engine.nearby_places(*PASIR_RIS_INT)
    by_category = {}
    for place in result["places"]:
        by_category.setdefault(place["category"], []).append(place["distance_m"])
    for cat_id, distances in by_category.items():
        assert distances == sorted(distances), f"{cat_id} places are not sorted by distance"


def test_every_place_has_a_precise_flag(engine):
    result = engine.nearby_places(*PASIR_RIS_INT)
    for place in result["places"]:
        assert isinstance(place["precise"], bool)


def test_pasir_ris_mall_is_essentially_zero_walk_from_the_interchange(engine):
    # The interchange is built inside Pasir Ris Mall itself.
    result = engine.nearby_places(*PASIR_RIS_INT)
    mall = next(p for p in result["places"] if p["id"] == "pasir-ris-mall")
    assert mall["distance_m"] < 100
