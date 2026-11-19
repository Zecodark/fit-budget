"""Deterministic workout engine: day selection, recovery rules, exercise selection, duration (PRD §3.6)."""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.services.workout.templates import (
    DIFFICULTY_LEVEL,
    ENGINE_VERSION,
    EQUIPMENT_ALLOWED,
    TEMPLATE_PATTERNS,
    template_family,
    templates_for_k,
)


@dataclass(frozen=True)
class ExerciseSpec:
    id: str
    code: str
    name: str
    pattern: str
    muscle_group: str
    equipment: str
    difficulty: int
    rank: int
    sets: int
    reps_min: int
    reps_max: int
    unit: str
    rest_s: int
    instructions: str
    contraindication_notes: str


def _cyclic_gaps(days: tuple[int, ...]) -> list[int]:
    s = sorted(days)
    m = len(s)
    gaps = [s[i + 1] - s[i] for i in range(m - 1)]
    gaps.append(7 - s[-1] + s[0])
    return gaps


def _gap_variance(days: tuple[int, ...]) -> float:
    gaps = _cyclic_gaps(days)
    mean = 7.0 / len(gaps)
    return sum((g - mean) ** 2 for g in gaps) / len(gaps)


def recovery_ok(days: tuple[int, ...], templates: list[str]) -> bool:
    """Check recovery rules (PRD §3.6.3)."""
    s = sorted(days)
    k = len(s)
    if k in (2, 3) or all(template_family(t) == "full" for t in templates):
        return all(g >= 2 for g in _cyclic_gaps(s))
    # Upper / lower (k == 4): two sessions of the SAME family must be >= 2 days apart (cyclically).
    for i in range(k):
        for j in range(i + 1, k):
            if template_family(templates[i]) == template_family(templates[j]):
                diff = abs(s[j] - s[i])
                cyc = min(diff, 7 - diff)
                if cyc < 2:
                    return False
    return True


def select_workout_days(
    available_days: list[int],
    week_start: date,
) -> tuple[list[int], list[str], list[dict[str, str]]]:
    avail = tuple(sorted(set(available_days)))
    iso_week = week_start.isocalendar().week
    target_k = max(2, min(4, len(avail)))
    warnings: list[dict[str, str]] = []

    for k in range(target_k, 1, -1):
        tmpls = templates_for_k(k, iso_week)
        valid = [c for c in itertools.combinations(avail, k) if recovery_ok(c, tmpls)]
        if valid:
            if k < target_k:
                warnings.append(
                    {
                        "code": "SESSIONS_REDUCED",
                        "message": f"Jumlah sesi dikurangi menjadi {k} agar jeda pemulihan antar sesi terpenuhi.",
                    }
                )
            chosen = min(valid, key=lambda c: (round(_gap_variance(c), 9), c))
            return list(chosen), tmpls, warnings

    # k=2 also failed recovery -> pick pair with largest cyclic min distance + RECOVERY_WARNING
    tmpls = templates_for_k(2, iso_week)
    pairs = list(itertools.combinations(avail, 2))
    chosen = max(pairs, key=lambda c: (min(_cyclic_gaps(c)), tuple(-x for x in c)))
    if target_k > 2:
        warnings.append(
            {
                "code": "SESSIONS_REDUCED",
                "message": "Jumlah sesi dikurangi menjadi 2 karena hari tersedia berdekatan.",
            }
        )
    warnings.append(
        {
            "code": "RECOVERY_WARNING",
            "message": "Sesi latihan berurutan tanpa hari istirahat penuh; perhatikan pemulihan.",
        }
    )
    return list(chosen), tmpls, warnings


def estimate_duration_minutes(chosen: list[ExerciseSpec]) -> int:
    # durasi(n) = 5 + sum_{i<=n} sets_i * (work_s_i + rest_s_i) / 60
    work_rest_s = 0
    for ex in chosen:
        work_s = 40 if ex.unit == "reps" else ex.reps_max
        work_rest_s += ex.sets * (work_s + ex.rest_s)
    return int(math.ceil(5 + work_rest_s / 60.0))


def generate_workout_plan(
    *,
    exercises: list[ExerciseSpec],
    workout_days: list[int],
    session_minutes: int,
    experience_level: str,
    equipment_access: str,
    excluded_exercise_ids: set[str],
    week_start: date,
) -> dict[str, Any]:
    allowed_eq = EQUIPMENT_ALLOWED[equipment_access]
    max_diff = DIFFICULTY_LEVEL[experience_level]
    pool = [
        e
        for e in exercises
        if e.equipment in allowed_eq and e.difficulty <= max_diff and e.id not in excluded_exercise_ids
    ]
    by_pattern: dict[str, list[ExerciseSpec]] = {}
    for e in pool:
        by_pattern.setdefault(e.pattern, []).append(e)
    for p in by_pattern:
        by_pattern[p].sort(key=lambda e: (e.rank, e.code))

    days_idx, tmpls, warnings = select_workout_days(workout_days, week_start)
    warn_codes = {w["code"] for w in warnings}

    def _add_warn(code: str, msg: str) -> None:
        if code not in warn_codes:
            warn_codes.add(code)
            warnings.append({"code": code, "message": msg})

    sessions_out: list[dict[str, Any]] = []
    for wd, tcode in zip(days_idx, tmpls, strict=True):
        s_date = (week_start + timedelta(days=wd)).isoformat()
        is_ul_b = tcode in ("UP-B", "LO-B")
        picked: list[tuple[ExerciseSpec, list[ExerciseSpec]]] = []
        used_ids: set[str] = set()

        for pat in TEMPLATE_PATTERNS[tcode]:
            cands = [e for e in by_pattern.get(pat, []) if e.id not in used_ids]
            if not cands and pat == "vertical_pull":
                cands = [e for e in by_pattern.get("horizontal_pull", []) if e.id not in used_ids]
                if cands:
                    _add_warn(
                        "PATTERN_FALLBACK",
                        "Latihan tarikan vertikal diganti tarikan horizontal sesuai ketersediaan alat.",
                    )
            if not cands:
                _add_warn("PATTERN_UNAVAILABLE", f"Tidak ada latihan yang cocok untuk pola gerak {pat}.")
                continue
            primary = cands[1] if (is_ul_b and len(cands) >= 2) else cands[0]
            alts = [e for e in by_pattern.get(primary.pattern, []) if e.id != primary.id][:2]
            picked.append((primary, alts))
            used_ids.add(primary.id)

        # Pick largest n <= 5 with duration(n) <= session_minutes, minimum 3 (PRD §3.6.5)
        max_n = min(5, len(picked))
        min_n = min(3, max_n)
        chosen_n = min_n
        for n in range(max_n, min_n - 1, -1):
            if estimate_duration_minutes([p[0] for p in picked[:n]]) <= session_minutes:
                chosen_n = n
                break
        final_pairs = picked[:chosen_n]
        est_min = estimate_duration_minutes([p[0] for p in final_pairs])
        if est_min > session_minutes:
            _add_warn(
                "SESSION_TOO_LONG",
                f"Estimasi durasi sesi ({est_min} menit) melebihi preferensi ({session_minutes} menit).",
            )

        ex_list = []
        for pos, (ex, alts) in enumerate(final_pairs, start=1):
            ex_list.append(
                {
                    "position": pos,
                    "exercise_id": ex.id,
                    "name": ex.name,
                    "pattern": ex.pattern,
                    "sets": ex.sets,
                    "reps_min": ex.reps_min,
                    "reps_max": ex.reps_max,
                    "unit": ex.unit,
                    "rest_s": ex.rest_s,
                    "instructions": ex.instructions,
                    "alternatives": [{"exercise_id": a.id, "name": a.name} for a in alts],
                }
            )
        sessions_out.append(
            {
                "date": s_date,
                "template_code": tcode,
                "status": "planned",
                "estimated_minutes": est_min,
                "exercises": ex_list,
            }
        )

    return {
        "week_start": week_start.isoformat(),
        "sessions": sessions_out,
        "warnings": warnings,
        "engine_version": ENGINE_VERSION,
    }

