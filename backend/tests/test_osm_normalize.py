"""OSM normalization tests."""

from wind_track.services.osm_normalize import (
    _parse_osm_number,
    classify_osm_element,
    dedupe_features,
)


def test_parse_osm_number_french_decimal():
    assert _parse_osm_number("8,40 m") == 8.4
    assert _parse_osm_number("12,5") == 12.5


def test_classify_tunnel_french_width():
    element = {
        "type": "way",
        "id": 99,
        "geometry": [
            {"lon": 4.84, "lat": 45.76},
            {"lon": 4.841, "lat": 45.761},
        ],
        "tags": {"tunnel": "yes", "highway": "primary", "width": "8,40"},
    }
    feat = classify_osm_element(element)
    assert feat is not None
    assert feat["properties"]["width_m"] == 8.4


def test_classify_street():
    element = {
        "type": "way",
        "id": 100,
        "geometry": [
            {"lon": 4.835, "lat": 45.76},
            {"lon": 4.836, "lat": 45.761},
        ],
        "tags": {"highway": "residential", "name": "Rue test"},
    }
    feat = classify_osm_element(element)
    assert feat is not None
    assert feat["feature_type"] == "street_segment"
    assert feat["name"] == "Rue test"
    assert feat["properties"]["width_m"] == 8


def test_classify_quai_as_quay():
    element = {
        "type": "way",
        "id": 150,
        "geometry": [
            {"lon": 4.835, "lat": 45.758},
            {"lon": 4.836, "lat": 45.759},
        ],
        "tags": {"highway": "unclassified", "name": "Quai Saint-Antoine"},
    }
    feat = classify_osm_element(element)
    assert feat is not None
    assert feat["feature_type"] == "quay"
    assert feat["properties"]["river_distance_m"] == 3


def test_classify_bridge():
    element = {
        "type": "way",
        "id": 200,
        "geometry": [
            {"lon": 4.84, "lat": 45.758},
            {"lon": 4.841, "lat": 45.759},
        ],
        "tags": {"bridge": "yes", "highway": "primary", "name": "Pont test"},
    }
    feat = classify_osm_element(element)
    assert feat is not None
    assert feat["feature_type"] == "bridge"


def test_classify_building_with_levels():
    element = {
        "type": "way",
        "id": 300,
        "geometry": [
            {"lon": 4.835, "lat": 45.76},
            {"lon": 4.836, "lat": 45.76},
            {"lon": 4.836, "lat": 45.761},
            {"lon": 4.835, "lat": 45.761},
            {"lon": 4.835, "lat": 45.76},
        ],
        "tags": {"building": "yes", "building:levels": "5"},
    }
    feat = classify_osm_element(element)
    assert feat is not None
    assert feat["feature_type"] == "building"
    assert feat["properties"]["height_m"] == 15.0
    assert feat["properties"]["height_source"] == "osm_levels"


def test_dedupe():
    features = [
        {"source_object_id": "way/1", "feature_type": "street_segment"},
        {"source_object_id": "way/1", "feature_type": "street_segment"},
    ]
    assert len(dedupe_features(features)) == 1