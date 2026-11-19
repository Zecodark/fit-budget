"""Deterministic dashboard aggregates and alerts (PRD §3.7, §5.7)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def build_dashboard(
    *,
    week_start: date,
    target_energy_kcal: int,
    target_protein_g: int,
    daily_budget_idr: int,
    planned_by_date: dict[str, dict[str, Any]],  # date -> {energy_kcal, protein_g, cost_idr, repriced_cost_idr}
    actual_food_by_date: dict[str, dict[str, Any]],  # date -> {energy_kcal, protein_g, cost_idr, has_logs}
    workout_sessions: list[dict[str, Any]],  # [{date, status}]
    profile_updated_days_ago: int | None = None,
) -> dict[str, Any]:
    days_out: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []

    logged_days_e_pct: list[Decimal] = []
    logged_days_p_pct: list[Decimal] = []
    total_actual_cost = 0
    total_planned_cost = 0
    workouts_planned = 0
    workouts_completed = 0

    consec_low_protein = 0
    low_protein_flagged = False
    repriced_over = False

    ws_by_date: dict[str, dict[str, int]] = {}
    for s in workout_sessions:
        d = s["date"]
        bucket = ws_by_date.setdefault(d, {"planned": 0, "completed": 0, "skipped": 0})
        bucket["planned"] += 1
        workouts_planned += 1
        if s["status"] == "completed":
            bucket["completed"] += 1
            workouts_completed += 1
        elif s["status"] == "skipped":
            bucket["skipped"] += 1

    for i in range(7):
        d_str = (week_start + timedelta(days=i)).isoformat()
        pl = planned_by_date.get(d_str, {"energy_kcal": 0.0, "protein_g": 0.0, "cost_idr": 0, "repriced_cost_idr": 0})
        ac = actual_food_by_date.get(
            d_str, {"energy_kcal": 0.0, "protein_g": 0.0, "cost_idr": 0, "has_logs": False}
        )
        wo = ws_by_date.get(d_str, {"planned": 0, "completed": 0, "skipped": 0})

        total_planned_cost += int(pl["cost_idr"])
        total_actual_cost += int(ac["cost_idr"])

        if int(ac["cost_idr"]) > daily_budget_idr:
            alerts.append(
                {
                    "code": "BUDGET_OVERRUN",
                    "date": d_str,
                    "message": f"Biaya aktual Rp {int(ac['cost_idr']):,} melebihi budget harian Rp {daily_budget_idr:,}.".replace(
                        ",", "."
                    ),
                }
            )

        if ac.get("has_logs"):
            if target_energy_kcal > 0:
                logged_days_e_pct.append(Decimal(str(ac["energy_kcal"])) * Decimal(100) / Decimal(target_energy_kcal))
            if target_protein_g > 0:
                logged_days_p_pct.append(Decimal(str(ac["protein_g"])) * Decimal(100) / Decimal(target_protein_g))
            if Decimal(str(ac["protein_g"])) < Decimal("0.80") * Decimal(target_protein_g):
                consec_low_protein += 1
                if consec_low_protein >= 3 and not low_protein_flagged:
                    low_protein_flagged = True
                    alerts.append(
                        {
                            "code": "PROTEIN_LOW",
                            "date": d_str,
                            "message": "Asupan protein aktual di bawah 80% target selama 3 hari berurutan yang tercatat.",
                        }
                    )
            else:
                consec_low_protein = 0

        if int(pl.get("repriced_cost_idr", 0)) > daily_budget_idr and not repriced_over:
            repriced_over = True
            alerts.append(
                {
                    "code": "PLAN_OVER_BUDGET_AFTER_PRICE_CHANGE",
                    "date": d_str,
                    "message": "Harga bahan terbaru membuat rencana menu melebihi budget harian; pertimbangkan generate ulang.",
                }
            )

        days_out.append(
            {
                "date": d_str,
                "planned": {
                    "energy_kcal": float(pl["energy_kcal"]),
                    "protein_g": float(pl["protein_g"]),
                    "cost_idr": int(pl["cost_idr"]),
                },
                "actual": {
                    "energy_kcal": float(ac["energy_kcal"]),
                    "protein_g": float(ac["protein_g"]),
                    "cost_idr": int(ac["cost_idr"]),
                    "has_logs": bool(ac.get("has_logs", False)),
                },
                "workout": wo,
            }
        )

    # MISSED_WORKOUT: 2 consecutive sessions with status == skipped
    ordered_sessions = sorted(workout_sessions, key=lambda s: s["date"])
    for idx in range(len(ordered_sessions) - 1):
        if ordered_sessions[idx]["status"] == "skipped" and ordered_sessions[idx + 1]["status"] == "skipped":
            alerts.append(
                {
                    "code": "MISSED_WORKOUT",
                    "date": ordered_sessions[idx + 1]["date"],
                    "message": "Dua sesi latihan berurutan dilewati; sesuaikan jadwal bila diperlukan.",
                }
            )
            break

    if profile_updated_days_ago is not None and profile_updated_days_ago > 90:
        alerts.append(
            {
                "code": "PROFILE_STALE",
                "date": week_start.isoformat(),
                "message": "Data profil belum diperbarui lebih dari 90 hari.",
            }
        )

    def _avg(vals: list[Decimal]) -> float:
        if not vals:
            return 0.0
        return float((sum(vals) / Decimal(len(vals))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

    avg_e = _avg(logged_days_e_pct)
    avg_p = _avg(logged_days_p_pct)
    fmt_actual = f"Rp{total_actual_cost:,}".replace(",", ".")
    fmt_planned = f"Rp{total_planned_cost:,}".replace(",", ".")
    text_summary = (
        f"Rata-rata energi {round(avg_e)}% dan protein {round(avg_p)}% dari target; "
        f"biaya aktual {fmt_actual} dari rencana {fmt_planned}; "
        f"latihan selesai {workouts_completed} dari {workouts_planned} sesi."
    )

    return {
        "week_start": week_start.isoformat(),
        "targets": {
            "energy_kcal": target_energy_kcal,
            "protein_g": target_protein_g,
            "daily_budget_idr": daily_budget_idr,
        },
        "days": days_out,
        "summary": {
            "avg_energy_adherence_pct": avg_e,
            "avg_protein_adherence_pct": avg_p,
            "total_actual_cost_idr": total_actual_cost,
            "workouts_completed": workouts_completed,
            "workouts_planned": workouts_planned,
        },
        "alerts": alerts,
        "text_summary": text_summary,
    }

