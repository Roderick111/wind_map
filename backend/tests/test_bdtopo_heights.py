"""BD TOPO height matching tests."""

from shapely.geometry import Point

from wind_track.services.bdtopo_heights import _bdtopo_height, match_bdtopo_heights


def test_bdtopo_height_validates_range():
    assert _bdtopo_height({"hauteur": 24.6}) == 24.6
    assert _bdtopo_height({"hauteur": 1.0}) is None
    assert _bdtopo_height({}) is None


def test_match_bdtopo_centroid_in_polygon():
    features = [
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001], [0, 0]]],
            },
            "properties": {"hauteur": 18.0},
        },
    ]
    centroid = Point(0.0005, 0.0005)
    matched = match_bdtopo_heights([(42, centroid)], features)
    assert matched == {42: 18.0}


def test_match_bdtopo_skips_invalid_height():
    features = [
        {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0.001, 0], [0.001, 0.001], [0, 0.001], [0, 0]]],
            },
            "properties": {"hauteur": 0.5},
        },
    ]
    centroid = Point(0.0005, 0.0005)
    assert match_bdtopo_heights([(1, centroid)], features) == {}