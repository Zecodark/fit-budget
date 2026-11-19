"""Shopping list calculation (PRD §3.5.5)."""

from __future__ import annotations

import math
from typing import Any

from app.services.optimizer.checker import FoodSpec


def build_shopping_list(
    days: list[dict[str, Any]],
    foods_by_id: dict[str, FoodSpec],
) -> list[dict[str, Any]]:
    totals: dict[str, int] = {}
    for d in days:
        for slot in d.get("slots", []):
            for it in slot.get("items", []):
                fid = it["food_id"]
                totals[fid] = totals.get(fid, 0) + int(it["grams"])

    out: list[dict[str, Any]] = []
    for fid, edible_g in sorted(totals.items(), key=lambda kv: foods_by_id[kv[0]].name):
        if edible_g <= 0:
            continue
        f = foods_by_id[fid]
        purchase_g = math.ceil(edible_g * 100 / f.edible_pct)
        packages = math.ceil(purchase_g / f.package_g)
        est_cost = packages * f.price_idr
        out.append(
            {
                "food_id": fid,
                "name": f.name,
                "total_edible_g": edible_g,
                "purchase_g": purchase_g,
                "package_g": f.package_g,
                "packages": packages,
                "est_cost_idr": est_cost,
            }
        )
    return out

