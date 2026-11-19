"use client";

import React, { useEffect, useState } from "react";
import { ConsultBlockBanner, ErrorBanner } from "@/components/StatusWidgets";
import { ApiClientError, apiFetch } from "@/lib/api";
import { currentMondayIso } from "@/lib/errorMessages";

export default function WorkoutPage() {
  const [weekStart, setWeekStart] = useState(currentMondayIso());
  const [plan, setPlan] = useState<any | null>(null);
  const [moveDates, setMoveDates] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [consultBlocked, setConsultBlocked] = useState(false);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  useEffect(() => {
    apiFetch("/workout-plans")
      .then((res) => {
        if (res.items && res.items.length > 0) {
          setPlan(res.items[0]);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleGenerate() {
    setError(null);
    setGenerating(true);
    try {
      const res = await apiFetch("/workout-plans/generate", {
        method: "POST",
        body: JSON.stringify({ week_start: weekStart }),
      });
      setPlan(res);
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.code === "PROFESSIONAL_CONSULT_REQUIRED") {
          setConsultBlocked(true);
        } else {
          setError({ msg: err.message, reqId: err.requestId });
        }
      }
    } finally {
      setGenerating(false);
    }
  }

  async function handleMoveSession(sessionId: string) {
    if (!plan) return;
    const newDate = moveDates[sessionId];
    if (!newDate) return;
    setError(null);
    try {
      const updated = await apiFetch(`/workout-plans/${plan.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          base_version: plan.version,
          moves: [{ session_id: sessionId, new_date: newDate }],
        }),
      });
      setPlan(updated);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }

  async function handleSessionStatus(sessionId: string, status: "planned" | "completed" | "skipped") {
    setError(null);
    try {
      const updated = await apiFetch(`/workout-sessions/${sessionId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setPlan(updated);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }

  async function handleSwapExercise(sessionId: string, itemId: string, newExerciseId: string) {
    setError(null);
    try {
      const updated = await apiFetch(`/workout-sessions/${sessionId}/exercises/${itemId}`, {
        method: "PATCH",
        body: JSON.stringify({ exercise_id: newExerciseId }),
      });
      setPlan(updated);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }

  async function handleConfirm() {
    if (!plan) return;
    setError(null);
    try {
      const updated = await apiFetch(`/workout-plans/${plan.id}/confirm`, { method: "POST" });
      setPlan(updated);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Jadwal Latihan Mingguan (2–4 Sesi)</h1>
            <p className="text-xs text-slate-600">
              Pemilihan hari deterministik dengan aturan jeda pemulihan (recovery) dan filter ketersediaan alat.
            </p>
          </div>
          {plan ? (
            <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-900">
              Status: {plan.status} (v{plan.version})
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="wo-week" className="block text-xs font-semibold text-slate-700 mb-1">
              Senin Minggu Latihan
            </label>
            <input
              id="wo-week"
              type="date"
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <button
            type="button"
            disabled={generating || consultBlocked}
            onClick={handleGenerate}
            data-testid="generate-workout-btn"
            className="rounded bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {generating ? "Menyusun..." : "Generate Jadwal Gym"}
          </button>
          {plan && plan.status === "draft" ? (
            <button
              type="button"
              onClick={handleConfirm}
              className="rounded bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700"
            >
              Konfirmasi Jadwal
            </button>
          ) : null}
        </div>
      </div>

      {consultBlocked ? <ConsultBlockBanner /> : null}
      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}

      {plan?.warnings && plan.warnings.length > 0 ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-xs text-amber-950 space-y-1">
          <div className="font-semibold">⚠ Peringatan Penjadwalan &amp; Pemulihan:</div>
          {plan.warnings.map((w: any, i: number) => (
            <div key={`${w.code}-${i}`}>
              <strong>{w.code}:</strong> {w.message}
            </div>
          ))}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          Memuat jadwal latihan...
        </div>
      ) : plan ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plan.sessions.map((s: any) => (
            <div key={s.id} className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
              <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
                <div>
                  <div className="text-sm font-bold text-slate-900">
                    {s.template_code} — {s.date}
                  </div>
                  <div className="text-[11px] text-slate-500">Estimasi durasi: {s.estimated_minutes} menit</div>
                </div>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-800">
                  {s.status}
                </span>
              </div>

              <div className="flex flex-wrap gap-1.5 text-xs">
                <button
                  type="button"
                  onClick={() => handleSessionStatus(s.id, "completed")}
                  className="rounded bg-emerald-600 px-2.5 py-1 text-white font-medium"
                >
                  ✓ Selesai
                </button>
                <button
                  type="button"
                  onClick={() => handleSessionStatus(s.id, "skipped")}
                  className="rounded bg-amber-600 px-2.5 py-1 text-white font-medium"
                >
                  Lewati
                </button>
              </div>

              <div className="flex items-center gap-1.5 text-xs">
                <label htmlFor={`move-${s.id}`} className="sr-only">
                  Tanggal baru sesi {s.date}
                </label>
                <input
                  id={`move-${s.id}`}
                  type="date"
                  value={moveDates[s.id] || ""}
                  onChange={(e) => setMoveDates((prev) => ({ ...prev, [s.id]: e.target.value }))}
                  className="rounded border border-slate-300 px-2 py-1 text-xs flex-1"
                />
                <button
                  type="button"
                  onClick={() => handleMoveSession(s.id)}
                  className="rounded border border-indigo-300 bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-800"
                >
                  Pindah Tanggal
                </button>
              </div>

              <ul className="space-y-2.5 text-xs pt-1">
                {s.exercises.map((ex: any) => (
                  <li key={ex.id} className="rounded border border-slate-200 p-2.5 space-y-1">
                    <div className="font-semibold text-slate-900">
                      {ex.position}. {ex.name}{" "}
                      <span className="text-[11px] font-normal text-slate-500">({ex.pattern})</span>
                    </div>
                    <div className="text-slate-700">
                      {ex.sets} set × {ex.reps_min}–{ex.reps_max} {ex.unit} • Istirahat {ex.rest_s} dtk
                    </div>
                    <p className="text-[11px] text-slate-600">{ex.instructions}</p>
                    {ex.alternatives && ex.alternatives.length > 0 ? (
                      <div className="flex flex-wrap items-center gap-1 pt-1">
                        <span className="text-[11px] text-slate-500">Alternatif:</span>
                        {ex.alternatives.map((alt: any) => (
                          <button
                            key={alt.exercise_id}
                            type="button"
                            onClick={() => handleSwapExercise(s.id, ex.id, alt.exercise_id)}
                            className="rounded border border-slate-300 px-1.5 py-0.5 text-[11px] hover:bg-slate-100"
                          >
                            Ganti ke {alt.name}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
          Belum ada jadwal latihan. Klik <strong>Generate Jadwal Gym</strong> di atas untuk membuat jadwal.
        </div>
      )}
    </div>
  );
}

