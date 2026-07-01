"""Detect river quays from OSM street names and tags."""

from __future__ import annotations

import re
from typing import Any

from wind_track.db.connection import fetch_one, get_db, utc_now

QUAY_NAME = re.compile(r"^quai(\s+(du|de|des))?\s+", re.IGNORECASE)


def is_quay_street(name: str, tags: dict[str, str]) -> bool:
    """Return True when OSM element should be classified as quay."""
    if tags.get("man_made") in {"quay", "pier", "dock"}:
        return True
    if tags.get("waterway") in {"dock", "boatyard"}:
        return True
    if tags.get("harbour") == "yes":
        return True
    return bool(name and QUAY_NAME.match(name.strip()))


async def promote_quay_streets(area_slug: str) -> int:
    """Reclassify existing Quai-named streets as quay features."""
    async with get_db() as conn:
        area = await fetch_one(
            conn,
            "SELECT id FROM areas WHERE slug = ?",
            (area_slug,),
        )
        if not area:
            return 0
        area_id = area["id"]
        now = utc_now()
        cursor = await conn.execute(
            """UPDATE spatial_features
               SET feature_type = 'quay',
                   updated_at = ?,
                   properties_json = json_set(
                     COALESCE(properties_json, '{}'),
                     '$.river_distance_m', 3
                   )
               WHERE area_id = ?
                 AND feature_type = 'street_segment'
                 AND name IS NOT NULL
                 AND (
                   lower(name) LIKE 'quai %'
                   OR lower(name) LIKE 'quai du %'
                   OR lower(name) LIKE 'quai de %'
                   OR lower(name) LIKE 'quai des %'
                 )""",
            (now, area_id),
        )
        return cursor.rowcount or 0