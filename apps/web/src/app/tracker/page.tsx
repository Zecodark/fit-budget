"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch, ApiClientError } from "@/lib/api";
import { formatDec1, formatIdr, formatInt } from "@/lib/errorMessages";
import {
  CatalogExercise,
  EQUIPMENT_META,
  ExerciseModeFilter,
  filterExercises,
  formatMuscleLabel,
  formatRepRange,
  GymSubFilter,
  MUSCLE_GROUP_LABELS,
  WorkoutSubFilter,
} from "@/lib/exercises";
import { ErrorBanner } from "@/components/StatusWidgets";

interface CatalogFood {
  id: string;
  code: string;
  name: string;
  kcal_100g: number;
  protein_100g: number;
  min_g?: number;
  step_g?: number;
}

interface WorkoutLogItem {
  id: string;
  date: string;
  session_id: string | null;
  exercise_id: string;
  exercise_name: string;
  exercise_equipment?: "bodyweight" | "dumbbell" | "gym" | null;
  exercise_category?: "gym" | "workout" | "dumbbell" | null;
  exercise_muscle_group?: string | null;
  exercise_unit?: "reps" | "seconds" | null;
  sets: { reps?: number; weight_kg?: number; seconds?: number }[];
  effort_rating: number | null;
  progression_suggestion?: string | null;
}

const EFFORT_OPTIONS: { value: number; label: string }[] = [
  { value: 5, label: "Mudah (RPE 5 — masih banyak sisa tenaga)" },
  { value: 7, label: "Pas / Normal (RPE 7 — sisa 2–3 repetisi)" },
  { value: 8, label: "Cukup Berat (RPE 8 — sisa 1–2 repetisi)" },
  { value: 9, label: "Berat (RPE 9 — hampir maksimal)" },
  { value: 10, label: "Maksimal (RPE 10 — gagal otot)" },
];

export default function TrackerPage() {
  const todayStr = new Date().toISOString().slice(0, 10);
  const [tab, setTab] = useState<"food" | "workout" | "weight">("food");
  const [selectedDate, setSelectedDate] = useState(todayStr);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);
  const [banner, setBanner] = useState<string | null>(null);

  // Food state
  const [foodsCatalog, setFoodsCatalog] = useState<CatalogFood[]>([]);
  const [foodSearch, setFoodSearch] = useState("");
  const [selectedFoodId, setSelectedFoodId] = useState("");
  const [mealSlot, setMealSlot] = useState<"breakfast" | "lunch" | "dinner" | "snack">("lunch");
  const [grams, setGrams] = useState(150);
  const [actualPriceIdr, setActualPriceIdr] = useState<string>("");
  const [foodLogs, setFoodLogs] = useState<any[]>([]);
  const [dayTotals, setDayTotals] = useState<any>(null);

  // Workout state
  const [exercisesCatalog, setExercisesCatalog] = useState<CatalogExercise[]>([]);
  const [exerciseMode, setExerciseMode] = useState<ExerciseModeFilter>("gym");
  const [gymSub, setGymSub] = useState<GymSubFilter>("all_gym");
  const [workoutSub, setWorkoutSub] = useState<WorkoutSubFilter>("bodyweight_only");
  const [muscleFilter, setMuscleFilter] = useState<string>("");
  const [exerciseSearch, setExerciseSearch] = useState("");
  const [selectedExerciseId, setSelectedExerciseId] = useState("");
  const [setCount, setSetCount] = useState(3);
  const [setReps, setSetReps] = useState(10);
  const [setSeconds, setSetSeconds] = useState(30);
  const [setLoadKg, setSetLoadKg] = useState(10);
  const [effortRating, setEffortRating] = useState<number>(7);
  const [workoutLogs, setWorkoutLogs] = useState<WorkoutLogItem[]>([]);
  const [historyFilter, setHistoryFilter] = useState<"all" | "gym" | "workout">("all");
  const [progressionHint, setProgressionHint] = useState<string | null>(null);

  // Weight state
  const [weightKg, setWeightKg] = useState("72");
  const [applyToProfile, setApplyToProfile] = useState(true);
  const [weightLogs, setWeightLogs] = useState<any[]>([]);

  // Apply URL query parameters if user navigated from /workout catalog ("Catat di Progres")
  useEffect(() => {
    if (typeof window === "undefined") return;
    const sp = new URLSearchParams(window.location.search);
    const t = sp.get("tab");
    if (t === "food" || t === "workout" || t === "weight") {
      setTab(t);
    }
    const m = sp.get("mode");
    if (m === "gym" || m === "workout" || m === "all") {
      setExerciseMode(m);
      if (m === "workout") {
        setWorkoutSub("with_dumbbell");
      }
    }
    const exId = sp.get("exercise");
    if (exId) {
      setSelectedExerciseId(exId);
    }
  }, []);

  const loadFoods = useCallback(async () => {
    try {
      const fRes = await apiFetch<{ items: CatalogFood[] }>(`/foods?query=${encodeURIComponent(foodSearch)}`);
      const items = fRes.items || [];
      setFoodsCatalog(items);
      setSelectedFoodId((prev) => (prev && items.some((f) => f.id === prev) ? prev : items[0]?.id || ""));
    } catch {
      // ignore initial catalog load error if unauthenticated
    }
  }, [foodSearch]);

  const loadExercises = useCallback(async () => {
    try {
      const eRes = await apiFetch<{ items: CatalogExercise[] }>("/exercises");
      setExercisesCatalog(eRes.items || []);
    } catch {
      // ignore initial catalog load error if unauthenticated
    }
  }, []);

  const loadLogs = useCallback(async () => {
    setError(null);
    try {
      const fl = await apiFetch<{ items: any[]; day_totals: any }>(`/logs/food?date=${selectedDate}`);
      setFoodLogs(fl.items || []);
      setDayTotals(fl.day_totals || null);

      const wl = await apiFetch<{ items: WorkoutLogItem[] }>(`/logs/workout?date=${selectedDate}`);
      setWorkoutLogs(wl.items || []);

      const wtl = await apiFetch<{ items: any[] }>("/logs/weight");
      setWeightLogs(wtl.items || []);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }, [selectedDate]);

  useEffect(() => {
    loadFoods();
  }, [loadFoods]);

  useEffect(() => {
    loadExercises();
  }, [loadExercises]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const filteredExercises = useMemo(
    () =>
      filterExercises(exercisesCatalog, {
        mode: exerciseMode,
        gymSub,
        workoutSub,
        muscleGroup: muscleFilter,
        search: exerciseSearch,
      }),
    [exercisesCatalog, exerciseMode, gymSub, workoutSub, muscleFilter, exerciseSearch],
  );

  const gymTotalCount = useMemo(
    () => exercisesCatalog.filter((e) => e.equipment === "gym" || e.equipment === "dumbbell").length,
    [exercisesCatalog],
  );
  const workoutTotalCount = useMemo(
    () => exercisesCatalog.filter((e) => e.equipment === "bodyweight").length,
    [exercisesCatalog],
  );

  // Keep selectedExerciseId valid whenever filter changes
  useEffect(() => {
    if (filteredExercises.length === 0) {
      return;
    }
    if (!selectedExerciseId || !filteredExercises.some((e) => e.id === selectedExerciseId)) {
      const first = filteredExercises[0];
      setSelectedExerciseId(first.id);
      setSetCount(first.sets || 3);
      if (first.unit === "seconds") {
        setSetSeconds(first.reps_min || 30);
      } else {
        setSetReps(first.reps_min || 10);
      }
      if (first.equipment === "bodyweight") {
        setSetLoadKg(0);
      } else if (setLoadKg === 0) {
        setSetLoadKg(10);
      }
    }
  }, [filteredExercises, selectedExerciseId, setLoadKg]);

  const selectedExercise = useMemo(
    () => exercisesCatalog.find((e) => e.id === selectedExerciseId) || null,
    [exercisesCatalog, selectedExerciseId],
  );

  const handleSelectExercise = (id: string) => {
    setSelectedExerciseId(id);
    const ex = exercisesCatalog.find((e) => e.id === id);
    if (ex) {
      setSetCount(ex.sets || 3);
      if (ex.unit === "seconds") {
        setSetSeconds(ex.reps_min || 30);
      } else {
        setSetReps(ex.reps_min || 10);
      }
      if (ex.equipment === "bodyweight") {
        setSetLoadKg(0);
      } else if (setLoadKg === 0) {
        setSetLoadKg(10);
      }
    }
  };

  const filteredWorkoutLogs = useMemo(() => {
    if (historyFilter === "all") return workoutLogs;
    if (historyFilter === "gym") {
      return workoutLogs.filter((wl) => wl.exercise_equipment === "gym" || wl.exercise_equipment === "dumbbell");
    }
    return workoutLogs.filter((wl) => wl.exercise_equipment === "bodyweight");
  }, [workoutLogs, historyFilter]);

  const handleAddFoodLog = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBanner(null);
    try {
      const body: Record<string, any> = {
        date: selectedDate,
        meal_slot: mealSlot,
        food_id: selectedFoodId,
        grams: Number(grams),
      };
      if (actualPriceIdr.trim() !== "") {
        body.actual_price_idr = Number(actualPriceIdr);
      }
      await apiFetch("/logs/food", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setBanner("Catatan makanan berhasil disimpan.");
      setActualPriceIdr("");
      await loadLogs();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  const handleDeleteFoodLog = async (id: string) => {
    try {
      await apiFetch(`/logs/food/${id}`, { method: "DELETE" });
      await loadLogs();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  const handleAddWorkoutLog = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBanner(null);
    if (!selectedExercise) {
      setError({ msg: "Pilih gerakan latihan terlebih dahulu." });
      return;
    }
    try {
      const count = Math.max(1, Math.min(10, Number(setCount) || 1));
      const setsPayload = Array.from({ length: count }, () =>
        selectedExercise.unit === "seconds"
          ? {
              seconds: Math.max(1, Math.min(600, Number(setSeconds) || 30)),
              ...(Number(setLoadKg) > 0 ? { weight_kg: Number(setLoadKg) } : {}),
            }
          : {
              reps: Math.max(1, Math.min(100, Number(setReps) || 10)),
              weight_kg: Math.max(0, Number(setLoadKg) || 0),
            },
      );
      const res = await apiFetch<WorkoutLogItem>("/logs/workout", {
        method: "POST",
        body: JSON.stringify({
          date: selectedDate,
          exercise_id: selectedExercise.id,
          sets: setsPayload,
          effort_rating: Number(effortRating),
        }),
      });
      setProgressionHint(res.progression_suggestion || null);
      const eqBadge = EQUIPMENT_META[selectedExercise.equipment]?.badge || "Latihan";
      setBanner(`Catatan ${eqBadge} "${selectedExercise.name}" berhasil disimpan.`);
      await loadLogs();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  const handleDeleteWorkoutLog = async (id: string) => {
    try {
      await apiFetch(`/logs/workout/${id}`, { method: "DELETE" });
      await loadLogs();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  const handleAddWeightLog = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBanner(null);
    try {
      const res = await apiFetch<any>("/logs/weight", {
        method: "POST",
        body: JSON.stringify({
          date: selectedDate,
          weight_kg: Number(weightKg),
          apply_to_profile: applyToProfile,
        }),
      });
      setBanner(
        applyToProfile
          ? `Berat badan ${formatDec1(res.weight_kg)} kg disimpan & target kalori diperbarui otomatis.`
          : `Berat badan ${formatDec1(res.weight_kg)} kg berhasil dicatat.`,
      );
      await loadLogs();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="route-intro flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-content">Catatan progres</h1>
          <p className="text-sm text-muted">
            Catat asupan makanan, sesi Gym maupun Workout rumahan, serta perkembangan berat badan Anda.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="tracker-date" className="text-xs font-semibold text-secondary">
            Tanggal:
          </label>
          <input
            id="tracker-date"
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="rounded-lg border border-line-strong px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}
      {banner ? (
        <div
          role="status"
          data-testid="tracker-success-banner"
          className="rounded-lg border border-positive-line bg-positive-soft p-3 text-sm text-positive"
        >
          ✓ {banner}
        </div>
      ) : null}

      {/* Tabs */}
      <div className="route-tabs gap-2 border-b border-line pb-2">
        <button
          type="button"
          onClick={() => setTab("food")}
          data-testid="tab-food"
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            tab === "food" ? "bg-positive-hover text-white" : "bg-raised text-secondary hover:bg-line"
          }`}
        >
          Makanan
        </button>
        <button
          type="button"
          onClick={() => setTab("workout")}
          data-testid="tab-workout"
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            tab === "workout" ? "bg-positive-hover text-white" : "bg-raised text-secondary hover:bg-line"
          }`}
        >
          Latihan (Gym &amp; Workout)
        </button>
        <button
          type="button"
          onClick={() => setTab("weight")}
          data-testid="tab-weight"
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            tab === "weight" ? "bg-positive-hover text-white" : "bg-raised text-secondary hover:bg-line"
          }`}
        >
          Berat Badan
        </button>
      </div>

      {tab === "food" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <form
            onSubmit={handleAddFoodLog}
            className="rounded-xl border border-line bg-panel p-5 shadow-sm space-y-4"
          >
            <h2 className="text-base font-bold text-content">Tambah Catatan Makanan</h2>
            <div>
              <label htmlFor="food-search" className="block text-xs font-semibold text-secondary">
                Cari Bahan Pangan
              </label>
              <input
                id="food-search"
                type="text"
                value={foodSearch}
                onChange={(e) => setFoodSearch(e.target.value)}
                placeholder="Contoh: tempe, ayam, nasi..."
                className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label htmlFor="food-select" className="block text-xs font-semibold text-secondary">
                Pilih Bahan Pangan
              </label>
              <select
                id="food-select"
                value={selectedFoodId}
                onChange={(e) => setSelectedFoodId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
              >
                {foodsCatalog.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} ({formatInt(f.kcal_100g)} kkal, {formatDec1(f.protein_100g)}g prot / 100g)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="meal-slot" className="block text-xs font-semibold text-secondary">
                Waktu Makan
              </label>
              <select
                id="meal-slot"
                value={mealSlot}
                onChange={(e) => setMealSlot(e.target.value as any)}
                className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
              >
                <option value="breakfast">Sarapan</option>
                <option value="lunch">Makan Siang</option>
                <option value="dinner">Makan Malam</option>
                <option value="snack">Selingan / Camilan</option>
              </select>
            </div>

            <div>
              <label htmlFor="food-grams" className="block text-xs font-semibold text-secondary">
                Berat Porsi (gram)
              </label>
              <input
                id="food-grams"
                type="number"
                min={1}
                max={3000}
                value={grams}
                onChange={(e) => setGrams(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label htmlFor="actual-price" className="block text-xs font-semibold text-secondary">
                Harga Aktual Dibayar (Rp, opsional)
              </label>
              <input
                id="actual-price"
                type="number"
                min={0}
                value={actualPriceIdr}
                onChange={(e) => setActualPriceIdr(e.target.value)}
                placeholder="Kosongkan untuk gunakan harga katalog"
                className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
              />
            </div>

            <button
              type="submit"
              data-testid="submit-food-log"
              className="w-full rounded-lg bg-positive-hover px-4 py-2.5 text-sm font-semibold text-white hover:bg-positive-hover"
            >
              Simpan Catatan Makanan
            </button>
          </form>

          <div className="lg:col-span-2 rounded-xl border border-line bg-panel p-5 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-bold text-content">Daftar Asupan ({selectedDate})</h2>
              {dayTotals ? (
                <div className="text-xs font-semibold text-secondary" data-testid="food-day-totals">
                  Total: {formatInt(dayTotals.energy_kcal)} kkal • {formatDec1(dayTotals.protein_g)} g protein •{" "}
                  {formatIdr(dayTotals.cost_idr)}
                </div>
              ) : null}
            </div>

            {foodLogs.length === 0 ? (
              <p className="text-sm text-muted">Belum ada makanan yang dicatat pada tanggal ini.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs sm:text-sm">
                  <thead>
                    <tr className="border-b border-line text-muted">
                      <th className="py-2">Waktu</th>
                      <th className="py-2">Pangan</th>
                      <th className="py-2">Gram</th>
                      <th className="py-2">Energi</th>
                      <th className="py-2">Protein</th>
                      <th className="py-2">Biaya</th>
                      <th className="py-2">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {foodLogs.map((fl) => (
                      <tr key={fl.id}>
                        <td className="py-2 capitalize">{fl.meal_slot}</td>
                        <td className="py-2 font-medium">{fl.food_name}</td>
                        <td className="py-2">{formatInt(fl.grams)} g</td>
                        <td className="py-2">{formatInt(fl.energy_kcal)} kkal</td>
                        <td className="py-2">{formatDec1(fl.protein_g)} g</td>
                        <td className="py-2">{formatIdr(fl.cost_idr)}</td>
                        <td className="py-2">
                          <button
                            type="button"
                            onClick={() => handleDeleteFoodLog(fl.id)}
                            className="text-danger hover:underline text-xs font-medium"
                          >
                            Hapus
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {tab === "workout" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <form
            onSubmit={handleAddWorkoutLog}
            className="rounded-xl border border-line bg-panel p-5 shadow-sm space-y-4"
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-base font-bold text-content">Catat Sesi Latihan</h2>
              <span className="text-[11px] font-medium text-muted">
                {filteredExercises.length} gerakan tersedia
              </span>
            </div>

            {/* Category selector: Gym vs Workout vs Semua */}
            <div className="space-y-2">
              <span className="block text-xs font-semibold text-secondary">Pilih Kategori Latihan</span>
              <div className="grid grid-cols-3 gap-1.5" role="group" aria-label="Kategori Latihan">
                <button
                  type="button"
                  data-testid="mode-gym"
                  onClick={() => setExerciseMode("gym")}
                  className={`rounded-lg border px-2.5 py-2 text-xs font-semibold transition ${
                    exerciseMode === "gym"
                      ? "border-accent-line bg-accent-action text-white"
                      : "border-line-strong bg-inset text-secondary hover:bg-raised"
                  }`}
                >
                  Gym ({gymTotalCount})
                </button>
                <button
                  type="button"
                  data-testid="mode-workout"
                  onClick={() => setExerciseMode("workout")}
                  className={`rounded-lg border px-2.5 py-2 text-xs font-semibold transition ${
                    exerciseMode === "workout"
                      ? "border-positive-line bg-positive-action text-white"
                      : "border-line-strong bg-inset text-secondary hover:bg-raised"
                  }`}
                >
                  Workout ({workoutTotalCount})
                </button>
                <button
                  type="button"
                  data-testid="mode-all"
                  onClick={() => setExerciseMode("all")}
                  className={`rounded-lg border px-2.5 py-2 text-xs font-semibold transition ${
                    exerciseMode === "all"
                      ? "border-line-strong bg-raised text-content ring-1 ring-accent-line"
                      : "border-line-strong bg-inset text-secondary hover:bg-raised"
                  }`}
                >
                  Semua ({exercisesCatalog.length})
                </button>
              </div>

              {exerciseMode === "gym" ? (
                <div className="flex flex-wrap gap-1.5 pt-0.5">
                  {[
                    { id: "all_gym", label: "Semua Gym (Alat + Dumbbell)" },
                    { id: "gym_only", label: "Mesin / Barbell / Cable" },
                    { id: "dumbbell", label: "Dumbbell" },
                  ].map((chip) => (
                    <button
                      key={chip.id}
                      type="button"
                      onClick={() => setGymSub(chip.id as GymSubFilter)}
                      className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                        gymSub === chip.id
                          ? "border-accent-line bg-accent-soft text-accent-ink"
                          : "border-line bg-inset text-muted hover:text-secondary"
                      }`}
                    >
                      {chip.label}
                    </button>
                  ))}
                </div>
              ) : null}

              {exerciseMode === "workout" ? (
                <div className="flex flex-wrap gap-1.5 pt-0.5">
                  {[
                    { id: "bodyweight_only", label: "Tanpa Alat (Bodyweight)" },
                    { id: "with_dumbbell", label: "Workout + Dumbbell Rumahan" },
                  ].map((chip) => (
                    <button
                      key={chip.id}
                      type="button"
                      onClick={() => setWorkoutSub(chip.id as WorkoutSubFilter)}
                      className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                        workoutSub === chip.id
                          ? "border-positive-line bg-positive-soft text-positive"
                          : "border-line bg-inset text-muted hover:text-secondary"
                      }`}
                    >
                      {chip.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {/* Muscle group & Search filter */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div>
                <label htmlFor="muscle-filter" className="block text-xs font-semibold text-secondary">
                  Kelompok Otot
                </label>
                <select
                  id="muscle-filter"
                  value={muscleFilter}
                  onChange={(e) => setMuscleFilter(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-2 text-xs sm:text-sm"
                >
                  <option value="">Semua Otot</option>
                  {Object.entries(MUSCLE_GROUP_LABELS).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="exercise-search" className="block text-xs font-semibold text-secondary">
                  Cari Gerakan
                </label>
                <input
                  id="exercise-search"
                  type="text"
                  value={exerciseSearch}
                  onChange={(e) => setExerciseSearch(e.target.value)}
                  placeholder="Bench press, push-up..."
                  className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-2 text-xs sm:text-sm"
                />
              </div>
            </div>

            {/* Exercise dropdown */}
            <div>
              <label htmlFor="exercise-select" className="block text-xs font-semibold text-secondary">
                Pilih Gerakan {exerciseMode === "gym" ? "Gym" : exerciseMode === "workout" ? "Workout" : ""}
              </label>
              <select
                id="exercise-select"
                value={selectedExerciseId}
                onChange={(e) => handleSelectExercise(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
              >
                {filteredExercises.length === 0 ? (
                  <option value="">Tidak ada gerakan cocok — ubah filter</option>
                ) : (
                  filteredExercises.map((ex) => {
                    const eqTag = EQUIPMENT_META[ex.equipment]?.badge || ex.equipment;
                    return (
                      <option key={ex.id} value={ex.id}>
                        {ex.name} [{eqTag} • {formatMuscleLabel(ex.muscle_group)}] ({formatRepRange(ex)})
                      </option>
                    );
                  })
                )}
              </select>
            </div>

            {/* Selected exercise preview */}
            {selectedExercise ? (
              <div className="rounded-lg border border-line bg-inset p-3 text-xs space-y-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                      EQUIPMENT_META[selectedExercise.equipment]?.badgeClass || ""
                    }`}
                  >
                    {EQUIPMENT_META[selectedExercise.equipment]?.badge}
                  </span>
                  <span className="rounded-full bg-raised px-2 py-0.5 text-[10px] text-secondary">
                    {formatMuscleLabel(selectedExercise.muscle_group)}
                  </span>
                  <span className="text-[11px] text-muted">
                    Target: {selectedExercise.sets} set × {formatRepRange(selectedExercise)}
                  </span>
                </div>
                {selectedExercise.instructions ? (
                  <p className="text-[11px] text-muted leading-relaxed">{selectedExercise.instructions}</p>
                ) : null}
              </div>
            ) : null}

            {/* Sets, Reps/Seconds, Weight */}
            <div className="grid grid-cols-3 gap-2.5">
              <div>
                <label htmlFor="set-count" className="block text-xs font-semibold text-secondary">
                  Jumlah Set
                </label>
                <input
                  id="set-count"
                  type="number"
                  min={1}
                  max={10}
                  value={setCount}
                  onChange={(e) => setSetCount(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-2 text-sm"
                />
              </div>

              {selectedExercise?.unit === "seconds" ? (
                <div>
                  <label htmlFor="set-seconds" className="block text-xs font-semibold text-secondary">
                    Durasi (detik)
                  </label>
                  <input
                    id="set-seconds"
                    type="number"
                    min={1}
                    max={600}
                    value={setSeconds}
                    onChange={(e) => setSetSeconds(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-2 text-sm"
                  />
                </div>
              ) : (
                <div>
                  <label htmlFor="set-reps" className="block text-xs font-semibold text-secondary">
                    Repetisi
                  </label>
                  <input
                    id="set-reps"
                    type="number"
                    min={1}
                    max={100}
                    value={setReps}
                    onChange={(e) => setSetReps(Number(e.target.value))}
                    className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-2 text-sm"
                  />
                </div>
              )}

              <div>
                <label htmlFor="set-load" className="block text-xs font-semibold text-secondary">
                  {selectedExercise?.equipment === "bodyweight" ? "Beban + (kg)" : "Beban (kg)"}
                </label>
                <input
                  id="set-load"
                  type="number"
                  min={0}
                  max={500}
                  step="0.5"
                  value={setLoadKg}
                  onChange={(e) => setSetLoadKg(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-2 text-sm"
                />
              </div>
            </div>

            <div>
              <label htmlFor="effort-select" className="block text-xs font-semibold text-secondary">
                Tingkat Usaha (RPE 1–10)
              </label>
              <select
                id="effort-select"
                value={effortRating}
                onChange={(e) => setEffortRating(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
              >
                {EFFORT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="submit"
              disabled={!selectedExercise}
              data-testid="submit-workout-log"
              className="w-full rounded-lg bg-positive-hover px-4 py-2.5 text-sm font-semibold text-white hover:bg-positive-hover disabled:opacity-50"
            >
              Simpan Catatan Latihan
            </button>
          </form>

          <div className="lg:col-span-2 rounded-xl border border-line bg-panel p-5 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-bold text-content">Riwayat Latihan ({selectedDate})</h2>
              <div className="flex items-center gap-1.5 text-xs">
                {[
                  { id: "all", label: `Semua (${workoutLogs.length})` },
                  { id: "gym", label: "Gym" },
                  { id: "workout", label: "Workout" },
                ].map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setHistoryFilter(f.id as any)}
                    className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${
                      historyFilter === f.id
                        ? "border-accent-line bg-accent-soft text-accent-ink"
                        : "border-line bg-inset text-muted"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            {progressionHint ? (
              <div className="rounded-lg border border-info-line bg-info-soft p-3 text-xs text-info">
                <strong>Saran Progresi:</strong> {progressionHint}
              </div>
            ) : null}

            {filteredWorkoutLogs.length === 0 ? (
              <p className="text-sm text-muted">Belum ada catatan latihan pada tanggal ini.</p>
            ) : (
              <ul className="space-y-2.5 text-sm">
                {filteredWorkoutLogs.map((wl) => {
                  const eq = wl.exercise_equipment || "gym";
                  const meta = EQUIPMENT_META[eq] || EQUIPMENT_META.gym;
                  const firstSet = wl.sets?.[0];
                  const setsSummary = firstSet
                    ? firstSet.seconds != null
                      ? `${wl.sets.length} set × ${firstSet.seconds} detik${firstSet.weight_kg ? ` @ ${firstSet.weight_kg} kg` : ""}`
                      : `${wl.sets.length} set × ${firstSet.reps} rep${firstSet.weight_kg ? ` @ ${firstSet.weight_kg} kg` : " (bodyweight)"}`
                    : `${wl.sets?.length || 0} set`;

                  return (
                    <li
                      key={wl.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line p-3"
                    >
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-content">{wl.exercise_name}</span>
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${meta.badgeClass}`}
                          >
                            {meta.badge}
                          </span>
                          {wl.exercise_muscle_group ? (
                            <span className="rounded-full bg-raised px-2 py-0.5 text-[10px] text-muted">
                              {formatMuscleLabel(wl.exercise_muscle_group)}
                            </span>
                          ) : null}
                        </div>
                        <div className="text-xs text-secondary">
                          {setsSummary}
                          {wl.effort_rating ? ` • RPE ${wl.effort_rating}/10` : ""}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteWorkoutLog(wl.id)}
                        className="text-xs font-medium text-danger hover:underline"
                      >
                        Hapus
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      ) : null}

      {tab === "weight" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <form
            onSubmit={handleAddWeightLog}
            className="rounded-xl border border-line bg-panel p-5 shadow-sm space-y-4"
          >
            <h2 className="text-base font-bold text-content">Catat Berat Badan</h2>
            <div>
              <label htmlFor="weight-input" className="block text-xs font-semibold text-secondary">
                Berat Badan (kg)
              </label>
              <input
                id="weight-input"
                type="number"
                step="0.1"
                min={30}
                max={250}
                value={weightKg}
                onChange={(e) => setWeightKg(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
              />
            </div>

            <label className="flex items-center gap-2 text-xs text-secondary">
              <input
                type="checkbox"
                checked={applyToProfile}
                onChange={(e) => setApplyToProfile(e.target.checked)}
              />
              Perbarui berat profil &amp; hitung ulang target gizi otomatis
            </label>

            <button
              type="submit"
              data-testid="submit-weight-log"
              className="w-full rounded-lg bg-positive-hover px-4 py-2.5 text-sm font-semibold text-white hover:bg-positive-hover"
            >
              Simpan Berat Badan
            </button>
          </form>

          <div className="lg:col-span-2 rounded-xl border border-line bg-panel p-5 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-content">Riwayat Berat Badan</h2>
            {weightLogs.length === 0 ? (
              <p className="text-sm text-muted">Belum ada catatan berat badan.</p>
            ) : (
              <table className="w-full text-left text-xs sm:text-sm">
                <thead>
                  <tr className="border-b border-line text-muted">
                    <th className="py-2">Tanggal</th>
                    <th className="py-2">Berat Badan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {weightLogs.map((w) => (
                    <tr key={w.id}>
                      <td className="py-2">{w.date}</td>
                      <td className="py-2 font-semibold">{formatDec1(w.weight_kg)} kg</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
