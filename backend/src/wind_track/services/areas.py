"""Analysis area definitions."""

from __future__ import annotations

from dataclasses import dataclass

from wind_track.services.geo import make_polygon


@dataclass(frozen=True)
class Bbox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @property
    def center_lon(self) -> float:
        return (self.min_lon + self.max_lon) / 2

    @property
    def center_lat(self) -> float:
        return (self.min_lat + self.max_lat) / 2

    def overpass_str(self) -> str:
        return f"{self.min_lat},{self.min_lon},{self.max_lat},{self.max_lon}"


PRESQUILE_BBOX = Bbox(
    min_lon=4.8270,
    min_lat=45.7535,
    max_lon=4.8430,
    max_lat=45.7685,
)

LYON_FULL_BBOX = Bbox(
    min_lon=4.7720,
    min_lat=45.7070,
    max_lon=4.9150,
    max_lat=45.8080,
)

AREA_DEFINITIONS: dict[str, dict] = {
    "pilot_presquile": {
        "name": "Presqu'île",
        "area_type": "pilot_zone",
        "bbox": PRESQUILE_BBOX,
        "default_zoom": 15.5,
    },
    "lyon_full": {
        "name": "Lyon",
        "area_type": "city",
        "bbox": LYON_FULL_BBOX,
        "default_zoom": 12.5,
    },
}


def boundary_geom_for_bbox(bbox: Bbox) -> str:
    """Return GeoJSON polygon for bbox."""
    return make_polygon([
        (bbox.min_lon, bbox.min_lat),
        (bbox.max_lon, bbox.min_lat),
        (bbox.max_lon, bbox.max_lat),
        (bbox.min_lon, bbox.max_lat),
        (bbox.min_lon, bbox.min_lat),
    ])


LYON_VECTOR_ZONES = [
    {
        "name": "Part-Dieu CBD",
        "zone_type": "high_rise_cluster",
        "status": "vector_preferred",
        "priority": 1,
        "reason": {
            "note": "Tall slab towers — scalar model limited; vector field preferred",
            "handling": "vector_preferred",
        },
        "bbox": Bbox(min_lon=4.848, min_lat=45.758, max_lon=4.862, max_lat=45.768),
    },
    {
        "name": "Confluence",
        "zone_type": "open_modern_district",
        "status": "scalar_only",
        "priority": 2,
        "reason": {"note": "Open modern district at river confluence"},
        "bbox": Bbox(min_lon=4.818, min_lat=45.732, max_lon=4.835, max_lat=45.748),
    },
]

PRESQUILE_VECTOR_ZONES = [
    {
        "name": "Quais du Rhône",
        "zone_type": "river_bridge_zone",
        "status": "scalar_only",
        "priority": 1,
        "reason": {"note": "Rhone quays and bridges — crosswind exposure"},
        "bbox": Bbox(min_lon=4.8395, min_lat=45.754, max_lon=4.8432, max_lat=45.768),
    },
    {
        "name": "Quais de Saône",
        "zone_type": "river_bridge_zone",
        "status": "scalar_only",
        "priority": 2,
        "reason": {"note": "Saone quays and Vieux Lyon river edge"},
        "bbox": Bbox(min_lon=4.827, min_lat=45.757, max_lon=4.8305, max_lat=45.768),
    },
    {
        "name": "Places & open Presqu'île",
        "zone_type": "open_modern_district",
        "status": "scalar_only",
        "priority": 3,
        "reason": {"note": "Bellecour, Terreaux, Jacobins squares"},
        "bbox": Bbox(min_lon=4.832, min_lat=45.757, max_lon=4.839, max_lat=45.764),
    },
]

AREA_VECTOR_ZONES: dict[str, list] = {
    "pilot_presquile": PRESQUILE_VECTOR_ZONES,
    "lyon_full": PRESQUILE_VECTOR_ZONES + LYON_VECTOR_ZONES,
}