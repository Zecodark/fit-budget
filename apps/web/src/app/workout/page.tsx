"use client";

import { FeatureBanner } from "@/components/FeatureBanner";
import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";
import { ConsultBlockBanner, ErrorBanner } from "@/components/StatusWidgets";
import { ApiClientError, apiFetch } from "@/lib/api";
import { currentMondayIso } from "@/lib/errorMessages";
import {
  CatalogExercise,
  EQUIPMENT_META,
  ExerciseModeFilter,
  filterExercises,
  formatMuscleLabel,
  formatPatternLabel,
  formatRepRange,
  GymSubFilter,
  MUSCLE_GROUP_LABELS,
  WorkoutSubFilter,
} from "@/lib/exercises";

type EquipmentAccessMode = "gym_full" | "bodyweight_only" | "home_dumbbell";

const PLAN_MODE_OPTIONS: { value: EquipmentAccessMode; label: string; subtitle: string; btnLabel: string }[] = [
  {
    value: "gym_full",
    label: "Mode Gym",
    subtitle: "Barbell, Mesin, Cable & Dumbbell",
    btnLabel: "Generate Jadwal Gym",
  },
  {
    value: "bodyweight_only",
    label: "Mode Workout",
    subtitle: "Tanpa Alat / Rumahan (Bodyweight)",
    btnLabel: "Generate Jadwal Workout",
  },
  {
    value: "home_dumbbell",
    label: "Workout + Dumbbell",
    subtitle: "Rumahan dengan Dumbbell",
    btnLabel: "Generate Jadwal Dumbbell",
  },
];

export default function WorkoutPage() {
  const [activeTab, setActiveTab] = useState<"plan" | "catalog">("plan");
  const [weekStart, setWeekStart] = useState(currentMondayIso());
  const [workoutMode, setWorkoutMode] = useState<EquipmentAccessMode>("gym_full");
  const [plan, setPlan] = useState<any | null>(null);
  const [moveDates, setMoveDates] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [consultBlocked, setConsultBlocked] = useState(false);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  // Exercise catalog state
  const [catalog, setCatalog] = useState<CatalogExercise[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catMode, setCatMode] = useState<ExerciseModeFilter>("gym");
  const [gymSub, setGymSub] = useState<GymSubFilter>("all_gym");
  const [workoutSub, setWorkoutSub] = useState<WorkoutSubFilter>("bodyweight_only");
  const [muscleFilter, setMuscleFilter] = useState("");
  const [diffFilter, setDiffFilter] = useState<"all" | "1" | "2">("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    apiFetch("/workout-plans")
      .then((res) => {
        if (res.items && res.items.length > 0) {
          const latest = res.items[0];
          setPlan(latest);
          if (
            latest.equipment_access === "gym_full" ||
            latest.equipment_access === "bodyweight_only" ||
            latest.equipment_access === "home_dumbbell"
          ) {
            setWorkoutMode(latest.equipment_access);
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    apiFetch<{ items: CatalogExercise[] }>("/exercises")
      .then((res) => setCatalog(res.items || []))
      .catch(() => {})
      .finally(() => setCatalogLoading(false));
  }, []);

  const filteredCatalog = useMemo(
    () =>
      filterExercises(catalog, {
        mode: catMode,
        gymSub,
        workoutSub,
        muscleGroup: muscleFilter,
        difficulty: diffFilter,
        search,
      }),
    [catalog, catMode, gymSub, workoutSub, muscleFilter, diffFilter, search],
  );

  const gymCount = useMemo(
    () => catalog.filter((e) => e.equipment === "gym" || e.equipment === "dumbbell").length,
    [catalog],
  );
  const workoutCount = useMemo(() => catalog.filter((e) => e.equipment === "bodyweight").length, [catalog]);

  async function handleGenerate() {
    setError(null);
    setGenerating(true);
    try {
      const res = await apiFetch("/workout-plans/generate", {
        method: "POST",
        body: JSON.stringify({
          week_start: weekStart,
          equipment_access: workoutMode,
        }),
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

  const currentModeInfo = PLAN_MODE_OPTIONS.find((m) => m.value === workoutMode) || PLAN_MODE_OPTIONS[0];

  return (
    <div className="space-y-5">
      <FeatureBanner kind="strength" title="Latihan Gym & Workout">
        Susun 2–4 sesi per minggu untuk mode Gym atau Workout rumahan, dan jelajahi katalog lengkap gerakan latihan.
      </FeatureBanner>

      {/* Main page tabs */}
      <div className="flex flex-wrap gap-2 border-b border-line pb-2">
        <button
          type="button"
          onClick={() => setActiveTab("plan")}
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            activeTab === "plan" ? "bg-accent-action text-white" : "bg-raised text-secondary hover:bg-line"
          }`}
        >
          Jadwal Mingguan
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("catalog")}
          data-testid="tab-exercise-catalog"
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            activeTab === "catalog" ? "bg-accent-action text-white" : "bg-raised text-secondary hover:bg-line"
          }`}
        >
          Katalog Gerakan Gym &amp; Workout ({catalog.length})
        </button>
      </div>

      {activeTab === "plan" ? (
        <div className="space-y-5">
          <div className="rounded-xl border border-line bg-panel p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold">Atur rencana latihan</h2>
              {plan ? (
                <span className="rounded-full bg-accent-wash px-3 py-1 text-xs font-semibold text-accent-ink">
                  Status: {plan.status} (v{plan.version})
                  {plan.equipment_access
                    ? ` • ${
                        plan.equipment_access === "gym_full"
                          ? "Gym"
                          : plan.equipment_access === "bodyweight_only"
                            ? "Workout Tanpa Alat"
                            : "Workout Dumbbell"
                      }`
                    : ""}
                </span>
              ) : null}
            </div>

            {/* Mode selector: Gym vs Workout */}
            <div className="space-y-1.5">
              <span className="block text-xs font-semibold text-secondary">Pilih Jenis Latihan</span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {PLAN_MODE_OPTIONS.map((opt) => {
                  const active = workoutMode === opt.value;
                  return (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setWorkoutMode(opt.value)}
                      className={`rounded-lg border p-3 text-left transition ${
                        active
                          ? "border-accent-line bg-accent-soft text-accent-ink"
                          : "border-line bg-inset text-secondary hover:bg-raised"
                      }`}
                    >
                      <div className="text-xs font-bold">{opt.label}</div>
                      <div className="text-[11px] opacity-80 mt-0.5">{opt.subtitle}</div>
                    </button>
                  );
                })}
              </div>
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
                {generating ? "Menyusun..." : currentModeInfo.btnLabel}
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
                <div
                  key={s.id}
                  data-testid="workout-session-card"
                  className="rounded-xl border border-line bg-panel p-4 space-y-3"
                >
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
                    {s.exercises.map((ex: any) => {
                      const eqKey = (ex.equipment || "gym") as "gym" | "bodyweight" | "dumbbell";
                      const eqMeta = EQUIPMENT_META[eqKey] || EQUIPMENT_META.gym;
                      return (
                        <li key={ex.id} className="rounded border border-line p-2.5 space-y-1">
                          <div className="flex flex-wrap items-center justify-between gap-1">
                            <div className="font-semibold text-content">
                              {ex.position}. {ex.name}
                            </div>
                            <span
                              className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${eqMeta.badgeClass}`}
                            >
                              {eqMeta.badge}
                            </span>
                          </div>
                          <div className="text-[11px] text-muted">
                            {formatPatternLabel(ex.pattern)}
                            {ex.muscle_group ? ` • ${formatMuscleLabel(ex.muscle_group)}` : ""}
                          </div>
                          <div className="text-secondary">
                            {ex.sets} set × {ex.reps_min}–{ex.reps_max} {ex.unit === "seconds" ? "detik" : "rep"} •
                            Istirahat {ex.rest_s} dtk
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
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-line bg-panel p-6 text-sm text-muted">
              Belum ada jadwal latihan. Pilih <strong>Mode Gym</strong> atau <strong>Mode Workout</strong> lalu klik{" "}
              <strong>{currentModeInfo.btnLabel}</strong> di atas.
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Catalog Filter Bar */}
          <div className="rounded-xl border border-line bg-panel p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-base font-bold text-content">Katalog Lengkap Gerakan Olahraga</h2>
                <p className="text-xs text-muted">
                  Dipisahkan antara gerakan Gym (barbell, mesin, cable, dumbbell) dan Workout rumahan (tanpa alat /
                  calisthenics).
                </p>
              </div>
              <span className="rounded-full bg-raised px-3 py-1 text-xs font-semibold text-secondary">
                Menampilkan {filteredCatalog.length} dari {catalog.length} gerakan
              </span>
            </div>

            {/* Gym vs Workout segmented tabs */}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setCatMode("gym")}
                className={`rounded-lg border px-4 py-2 text-xs font-semibold ${
                  catMode === "gym"
                    ? "border-accent-line bg-accent-action text-white"
                    : "border-line-strong bg-inset text-secondary hover:bg-raised"
                }`}
              >
                Gym ({gymCount})
              </button>
              <button
                type="button"
                onClick={() => setCatMode("workout")}
                className={`rounded-lg border px-4 py-2 text-xs font-semibold ${
                  catMode === "workout"
                    ? "border-positive-line bg-positive-action text-white"
                    : "border-line-strong bg-inset text-secondary hover:bg-raised"
                }`}
              >
                Workout / Rumahan ({workoutCount})
              </button>
              <button
                type="button"
                onClick={() => setCatMode("all")}
                className={`rounded-lg border px-4 py-2 text-xs font-semibold ${
                  catMode === "all"
                    ? "border-line-strong bg-raised text-content ring-1 ring-accent-line"
                    : "border-line-strong bg-inset text-secondary hover:bg-raised"
                }`}
              >
                Semua ({catalog.length})
              </button>
            </div>

            {/* Sub-filters */}
            {catMode === "gym" ? (
              <div className="flex flex-wrap gap-1.5">
                {[
                  { id: "all_gym", label: "Semua Gym (Alat + Dumbbell)" },
                  { id: "gym_only", label: "Mesin / Barbell / Cable" },
                  { id: "dumbbell", label: "Dumbbell" },
                ].map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    onClick={() => setGymSub(chip.id as GymSubFilter)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                      gymSub === chip.id
                        ? "border-accent-line bg-accent-soft text-accent-ink"
                        : "border-line bg-inset text-muted"
                    }`}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            ) : null}

            {catMode === "workout" ? (
              <div className="flex flex-wrap gap-1.5">
                {[
                  { id: "bodyweight_only", label: "Tanpa Alat (Bodyweight / Calisthenics)" },
                  { id: "with_dumbbell", label: "Workout + Dumbbell Rumahan" },
                ].map((chip) => (
                  <button
                    key={chip.id}
                    type="button"
                    onClick={() => setWorkoutSub(chip.id as WorkoutSubFilter)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium ${
                      workoutSub === chip.id
                        ? "border-positive-line bg-positive-soft text-positive"
                        : "border-line bg-inset text-muted"
                    }`}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            ) : null}

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label htmlFor="cat-search" className="block text-xs font-semibold text-secondary mb-1">
                  Cari Gerakan
                </label>
                <input
                  id="cat-search"
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Contoh: deadlift, push-up, plank..."
                  className="w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label htmlFor="cat-muscle" className="block text-xs font-semibold text-secondary mb-1">
                  Kelompok Otot
                </label>
                <select
                  id="cat-muscle"
                  value={muscleFilter}
                  onChange={(e) => setMuscleFilter(e.target.value)}
                  className="w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
                >
                  <option value="">Semua Kelompok Otot</option>
                  {Object.entries(MUSCLE_GROUP_LABELS).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="cat-diff" className="block text-xs font-semibold text-secondary mb-1">
                  Tingkat Kesulitan
                </label>
                <select
                  id="cat-diff"
                  value={diffFilter}
                  onChange={(e) => setDiffFilter(e.target.value as any)}
                  className="w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
                >
                  <option value="all">Semua Tingkat</option>
                  <option value="1">Pemula (Level 1)</option>
                  <option value="2">Menengah (Level 2)</option>
                </select>
              </div>
            </div>
          </div>

          {catalogLoading ? (
            <div className="rounded-xl border border-line bg-panel p-6 text-sm text-muted">
              Memuat katalog gerakan...
            </div>
          ) : filteredCatalog.length === 0 ? (
            <div className="rounded-xl border border-line bg-panel p-6 text-sm text-muted">
              Tidak ada gerakan yang cocok dengan filter saat ini.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredCatalog.map((ex) => {
                const eqMeta = EQUIPMENT_META[ex.equipment] || EQUIPMENT_META.gym;
                const trackerMode = ex.equipment === "bodyweight" ? "workout" : "gym";
                return (
                  <div
                    key={ex.id}
                    className="rounded-xl border border-line bg-panel p-4 flex flex-col justify-between gap-3"
                  >
                    <div className="space-y-2">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <h3 className="text-sm font-bold text-content">{ex.name}</h3>
                          <div className="text-[11px] text-muted">
                            {formatMuscleLabel(ex.muscle_group)} • {formatPatternLabel(ex.pattern)}
                          </div>
                        </div>
                        <span
                          className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${eqMeta.badgeClass}`}
                        >
                          {eqMeta.badge}
                        </span>
                      </div>

                      <div className="flex flex-wrap gap-1.5 text-[11px]">
                        <span className="rounded bg-raised px-2 py-0.5 text-secondary">
                          {ex.sets} set × {formatRepRange(ex)}
                        </span>
                        <span className="rounded bg-raised px-2 py-0.5 text-muted">
                          Istirahat {ex.rest_s} dtk
                        </span>
                        <span className="rounded bg-raised px-2 py-0.5 text-muted">
                          {ex.difficulty === 1 ? "Pemula" : "Menengah"}
                        </span>
                      </div>

                      <p className="text-xs text-muted leading-relaxed">{ex.instructions}</p>
                    </div>

                    <div className="pt-2 border-t border-line flex items-center justify-between text-xs">
                      <span className="font-mono text-[10px] text-muted">{ex.code}</span>
                      <Link
                        href={`/tracker?tab=workout&mode=${trackerMode}&exercise=${encodeURIComponent(ex.id)}`}
                        className="font-semibold text-accent-ink hover:underline"
                      >
                        Catat di Progres →
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
