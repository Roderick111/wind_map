"""PMTiles manifest tests."""

from wind_track.services.tiles.generate import tile_manifest


def test_tile_manifest_missing():
    manifest = tile_manifest("nonexistent_area")
    assert manifest["ready"] is False
    assert manifest["base_pmtiles"] is False