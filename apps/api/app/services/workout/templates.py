"""Workout templates and equipment/difficulty mappings (PRD §3.6.4–3.6.5)."""

from __future__ import annotations

ENGINE_VERSION = "workout-1.0.0"

TEMPLATE_PATTERNS: dict[str, list[str]] = {
    "FB-A": ["squat", "horizontal_push", "horizontal_pull", "core", "lunge"],
    "FB-B": ["hinge", "vertical_push", "vertical_pull", "core", "carry"],
    "UP-A": ["horizontal_push", "horizontal_pull", "vertical_push", "vertical_pull", "core"],
    "UP-B": ["horizontal_push", "horizontal_pull", "vertical_push", "vertical_pull", "core"],
    "LO-A": ["squat", "hinge", "lunge", "core", "carry"],
    "LO-B": ["squat", "hinge", "lunge", "core", "carry"],
}

EQUIPMENT_ALLOWED: dict[str, set[str]] = {
    "bodyweight_only": {"bodyweight"},
    "home_dumbbell": {"bodyweight", "dumbbell"},
    "gym_full": {"bodyweight", "dumbbell", "gym"},
}

DIFFICULTY_LEVEL: dict[str, int] = {
    "beginner": 1,
    "intermediate": 2,
}


def templates_for_k(k: int, iso_week: int) -> list[str]:
    if k == 2:
        return ["FB-A", "FB-B"]
    if k == 3:
        return ["FB-A", "FB-B", "FB-A"] if iso_week % 2 == 0 else ["FB-B", "FB-A", "FB-B"]
    return ["UP-A", "LO-A", "UP-B", "LO-B"]


def template_family(template_code: str) -> str:
    if template_code.startswith("UP"):
        return "upper"
    if template_code.startswith("LO"):
        return "lower"
    return "full"

