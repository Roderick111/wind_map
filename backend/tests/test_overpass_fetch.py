"""Overpass bbox tiling tests."""

from wind_track.services.areas import Bbox
from wind_track.services.overpass_fetch import split_bbox


def test_split_bbox_grid():
    bbox = Bbox(0.0, 0.0, 2.0, 2.0)
    chunks = split_bbox(bbox, 2, 2)
    assert len(chunks) == 4
    assert chunks[0].min_lon == 0.0
    assert chunks[3].max_lat == 2.0