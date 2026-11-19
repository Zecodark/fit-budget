"use client";

import { FeatureBanner } from "@/components/FeatureBanner";

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
    <div className="space-y-5">
      <FeatureBanner kind="strength" title="Jadwal latihan">Susun 2–4 sesi per minggu sesuai peralatan dan waktu pemulihan Anda.</FeatureBanner>
      <div className="rounded-xl border border-line bg-panel p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold">Atur rencana</h2>
          {plan ? (
            <span className="rounded-full bg-accent-wash px-3 py-1 text-xs font-semibold text-accent-ink">
              Status: {plan.status} (v{plan.version})
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="wo-week" className="block text-xs font-semibold text-secondary mb-1">
              Senin Minggu Latihan
            </label>
            <input
              id="wo-week"
              type="date"
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              className="rounded border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <button
            type="button"
            disabled={generating || consultBlocked}
            onClick={handleGenerate}
            data-testid="generate-workout-btn"
            className="rounded bg-accent-action px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {generating ? "Menyusun..." : "Generate Jadwal Gym"}
          </button>
          {plan && plan.status === "draft" ? (
            <button
              type="button"
              onClick={handleConfirm}
              className="rounded bg-positive-action px-4 py-2 text-xs font-semibold text-white hover:bg-positive-hover"
            >
              Konfirmasi Jadwal
            </button>
          ) : null}
        </div>
      </div>

      {consultBlocked ? <ConsultBlockBanner /> : null}
      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}

      {plan?.warnings && plan.warnings.length > 0 ? (
        <div className="rounded-lg border border-warning-line bg-warning-soft p-4 text-xs text-warning space-y-1">
          <div className="font-semibold">⚠ Peringatan Penjadwalan &amp; Pemulihan:</div>
          {plan.warnings.map((w: any, i: number) => (
            <div key={`${w.code}-${i}`}>
              <strong>{w.code}:</strong> {w.message}
            </div>
          ))}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-line bg-panel p-6 text-sm text-muted">
          Memuat jadwal latihan...
        </div>
      ) : plan ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plan.sessions.map((s: any) => (
            <div key={s.id} className="rounded-xl border border-line bg-panel p-4 space-y-3">
              <div className="flex items-center justify-between gap-2 border-b border-line pb-2">
                <div>
                  <div className="text-sm font-bold text-content">
                    {s.template_code} — {s.date}
                  </div>
                  <div className="text-[11px] text-muted">Estimasi durasi: {s.estimated_minutes} menit</div>
                </div>
                <span className="rounded bg-raised px-2 py-0.5 text-xs font-medium text-secondary">
                  {s.status}
                </span>
              </div>

              <div className="flex flex-wrap gap-1.5 text-xs">
                <button
                  type="button"
                  onClick={() => handleSessionStatus(s.id, "completed")}
                  className="rounded bg-positive-action px-2.5 py-1 text-white font-medium"
                >
                  ✓ Selesai
                </button>
                <button
                  type="button"
                  onClick={() => handleSessionStatus(s.id, "skipped")}
                  className="rounded bg-warning-soft px-2.5 py-1 text-warning font-medium"
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
                  className="rounded border border-line-strong px-2 py-1 text-xs flex-1"
                />
                <button
                  type="button"
                  onClick={() => handleMoveSession(s.id)}
                  className="rounded border border-accent-line bg-accent-soft px-2.5 py-1 text-xs font-medium text-accent-ink"
                >
                  Pindah Tanggal
                </button>
              </div>

              <ul className="space-y-2.5 text-xs pt-1">
                {s.exercises.map((ex: any) => (
                  <li key={ex.id} className="rounded border border-line p-2.5 space-y-1">
                    <div className="font-semibold text-content">
                      {ex.position}. {ex.name}{" "}
                      <span className="text-[11px] font-normal text-muted">({ex.pattern})</span>
                    </div>
                    <div className="text-secondary">
                      {ex.sets} set × {ex.reps_min}–{ex.reps_max} {ex.unit} • Istirahat {ex.rest_s} dtk
                    </div>
                    <p className="text-[11px] text-muted">{ex.instructions}</p>
                    {ex.alternatives && ex.alternatives.length > 0 ? (
                      <div className="flex flex-wrap items-center gap-1 pt-1">
                        <span className="text-[11px] text-muted">Alternatif:</span>
                        {ex.alternatives.map((alt: any) => (
                          <button
                            key={alt.exercise_id}
                            type="button"
                            onClick={() => handleSwapExercise(s.id, ex.id, alt.exercise_id)}
                            className="rounded border border-line-strong px-1.5 py-0.5 text-[11px] hover:bg-raised"
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
        <div className="rounded-xl border border-line bg-panel p-6 text-sm text-muted">
          Belum ada jadwal latihan. Klik <strong>Generate Jadwal Gym</strong> di atas untuk membuat jadwal.
        </div>
      )}
    </div>
  );
}

