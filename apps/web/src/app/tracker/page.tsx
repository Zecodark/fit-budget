"use client";

import React, { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiClientError } from "@/lib/api";
import { formatDec1, formatIdr, formatInt } from "@/lib/errorMessages";
import { ErrorBanner } from "@/components/StatusWidgets";

interface CatalogFood {
  id: string;
  code: string;
  name_id: string;
  energy_kcal_per_100g: number;
  protein_g_per_100g: number;
  default_serving_g: number;
  current_price_idr_per_100g: number;
}

interface CatalogExercise {
  id: string;
  code: string;
  name_id: string;
  primary_muscle: string;
  rep_range_min: number;
  rep_range_max: number;
}

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
  const [workoutCompleted, setWorkoutCompleted] = useState(true);
  const [effortRating, setEffortRating] = useState<"easy" | "normal" | "hard">("normal");
  const [selectedExerciseId, setSelectedExerciseId] = useState("");
  const [setReps, setSetReps] = useState(10);
  const [setLoadKg, setSetLoadKg] = useState(0);
  const [workoutLogs, setWorkoutLogs] = useState<any[]>([]);
  const [progressionHint, setProgressionHint] = useState<string | null>(null);

  // Weight state
  const [weightKg, setWeightKg] = useState("72");
  const [applyToProfile, setApplyToProfile] = useState(true);
  const [weightLogs, setWeightLogs] = useState<any[]>([]);

  const loadCatalogs = useCallback(async () => {
    try {
      const fRes = await apiFetch<{ items: CatalogFood[] }>(`/foods?q=${encodeURIComponent(foodSearch)}`);
      setFoodsCatalog(fRes.items || []);
      if (!selectedFoodId && fRes.items?.length > 0) {
        setSelectedFoodId(fRes.items[0].id);
      }
      const eRes = await apiFetch<{ items: CatalogExercise[] }>("/exercises");
      setExercisesCatalog(eRes.items || []);
      if (!selectedExerciseId && eRes.items?.length > 0) {
        setSelectedExerciseId(eRes.items[0].id);
      }
    } catch {
      // ignore initial catalog load error if unauthenticated
    }
  }, [foodSearch, selectedFoodId, selectedExerciseId]);

  const loadLogs = useCallback(async () => {
    setError(null);
    try {
      const fl = await apiFetch<{ items: any[]; day_totals: any }>(`/logs/food?date=${selectedDate}`);
      setFoodLogs(fl.items || []);
      setDayTotals(fl.day_totals || null);

      const wl = await apiFetch<{ items: any[] }>(`/logs/workout?from=${selectedDate}&to=${selectedDate}`);
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
    loadCatalogs();
  }, [loadCatalogs]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const handleAddFoodLog = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBanner(null);
    try {
      const body: Record<string, any> = {
        logged_date: selectedDate,
        meal_slot: mealSlot,
        food_id: selectedFoodId,
        serving_grams: Number(grams),
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
    try {
      const res = await apiFetch<any>("/logs/workout", {
        method: "POST",
        body: JSON.stringify({
          logged_date: selectedDate,
          completed: workoutCompleted,
          effort_rating: effortRating,
          sets: selectedExerciseId
            ? [
                {
                  exercise_id: selectedExerciseId,
                  set_number: 1,
                  reps: Number(setReps),
                  load_kg: Number(setLoadKg),
                },
              ]
            : [],
        }),
      });
      setProgressionHint(res.progression_suggestion || null);
      setBanner("Catatan latihan berhasil disimpan.");
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
          logged_date: selectedDate,
          weight_kg: Number(weightKg),
          apply_to_profile: applyToProfile,
        }),
      });
      setBanner(
        res.new_nutrition_target
          ? `Berat badan ${formatDec1(res.weight_kg)} kg disimpan & target kalori diperbarui (${formatInt(res.new_nutrition_target.target_kcal)} kkal).`
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Pencatatan Harian (Tracker)</h1>
          <p className="text-sm text-slate-600">
            Catat asupan makanan, sesi latihan, dan perkembangan berat badan Anda.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="tracker-date" className="text-xs font-semibold text-slate-700">
            Tanggal:
          </label>
          <input
            id="tracker-date"
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          />
        </div>
      </div>

      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}
      {banner ? (
        <div
          role="status"
          data-testid="tracker-success-banner"
          className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-950"
        >
          ✓ {banner}
        </div>
      ) : null}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-200 pb-2">
        <button
          type="button"
          onClick={() => setTab("food")}
          data-testid="tab-food"
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            tab === "food" ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Makanan
        </button>
        <button
          type="button"
          onClick={() => setTab("workout")}
          data-testid="tab-workout"
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            tab === "workout" ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Latihan
        </button>
        <button
          type="button"
          onClick={() => setTab("weight")}
          data-testid="tab-weight"
          className={`rounded-lg px-4 py-2 text-sm font-semibold ${
            tab === "weight" ? "bg-emerald-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          Berat Badan
        </button>
      </div>

      {tab === "food" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <form
            onSubmit={handleAddFoodLog}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4"
          >
            <h2 className="text-base font-bold text-slate-900">Tambah Catatan Makanan</h2>
            <div>
              <label htmlFor="food-search" className="block text-xs font-semibold text-slate-700">
                Cari Bahan Pangan
              </label>
              <input
                id="food-search"
                type="text"
                value={foodSearch}
                onChange={(e) => setFoodSearch(e.target.value)}
                placeholder="Contoh: tempe, ayam, nasi..."
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label htmlFor="food-select" className="block text-xs font-semibold text-slate-700">
                Pilih Bahan Pangan
              </label>
              <select
                id="food-select"
                value={selectedFoodId}
                onChange={(e) => setSelectedFoodId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {foodsCatalog.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name_id} ({formatInt(f.energy_kcal_per_100g)} kkal, {formatDec1(f.protein_g_per_100g)}g prot /
                    100g)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="meal-slot" className="block text-xs font-semibold text-slate-700">
                Waktu Makan
              </label>
              <select
                id="meal-slot"
                value={mealSlot}
                onChange={(e) => setMealSlot(e.target.value as any)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="breakfast">Sarapan</option>
                <option value="lunch">Makan Siang</option>
                <option value="dinner">Makan Malam</option>
                <option value="snack">Selingan / Camilan</option>
              </select>
            </div>

            <div>
              <label htmlFor="food-grams" className="block text-xs font-semibold text-slate-700">
                Berat Porsi (gram)
              </label>
              <input
                id="food-grams"
                type="number"
                min={1}
                max={2000}
                value={grams}
                onChange={(e) => setGrams(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label htmlFor="actual-price" className="block text-xs font-semibold text-slate-700">
                Harga Aktual Dibayar (Rp, opsional)
              </label>
              <input
                id="actual-price"
                type="number"
                min={0}
                value={actualPriceIdr}
                onChange={(e) => setActualPriceIdr(e.target.value)}
                placeholder="Kosongkan untuk gunakan harga katalog"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <button
              type="submit"
              data-testid="submit-food-log"
              className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800"
            >
              Simpan Catatan Makanan
            </button>
          </form>

          <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-bold text-slate-900">Daftar Asupan ({selectedDate})</h2>
              {dayTotals ? (
                <div className="text-xs font-semibold text-slate-700" data-testid="food-day-totals">
                  Total: {formatInt(dayTotals.energy_kcal)} kkal • {formatDec1(dayTotals.protein_g)} g protein •{" "}
                  {formatIdr(dayTotals.cost_idr)}
                </div>
              ) : null}
            </div>

            {foodLogs.length === 0 ? (
              <p className="text-sm text-slate-500">Belum ada makanan yang dicatat pada tanggal ini.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs sm:text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-600">
                      <th className="py-2">Waktu</th>
                      <th className="py-2">Pangan</th>
                      <th className="py-2">Gram</th>
                      <th className="py-2">Energi</th>
                      <th className="py-2">Protein</th>
                      <th className="py-2">Biaya</th>
                      <th className="py-2">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {foodLogs.map((fl) => (
                      <tr key={fl.id}>
                        <td className="py-2 capitalize">{fl.meal_slot}</td>
                        <td className="py-2 font-medium">{fl.food_name}</td>
                        <td className="py-2">{formatInt(fl.serving_grams)} g</td>
                        <td className="py-2">{formatInt(fl.energy_kcal)} kkal</td>
                        <td className="py-2">{formatDec1(fl.protein_g)} g</td>
                        <td className="py-2">{formatIdr(fl.cost_idr)}</td>
                        <td className="py-2">
                          <button
                            type="button"
                            onClick={() => handleDeleteFoodLog(fl.id)}
                            className="text-rose-700 hover:underline text-xs font-medium"
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
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4"
          >
            <h2 className="text-base font-bold text-slate-900">Catat Sesi Latihan</h2>

            <label className="flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={workoutCompleted}
                onChange={(e) => setWorkoutCompleted(e.target.checked)}
              />
              Sesi latihan diselesaikan
            </label>

            <div>
              <label htmlFor="effort-select" className="block text-xs font-semibold text-slate-700">
                Tingkat Kesulitan (Effort Rating)
              </label>
              <select
                id="effort-select"
                value={effortRating}
                onChange={(e) => setEffortRating(e.target.value as any)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="easy">Mudah (Easy)</option>
                <option value="normal">Pas / Normal</option>
                <option value="hard">Berat (Hard)</option>
              </select>
            </div>

            <div>
              <label htmlFor="exercise-select" className="block text-xs font-semibold text-slate-700">
                Gerakan Utama
              </label>
              <select
                id="exercise-select"
                value={selectedExerciseId}
                onChange={(e) => setSelectedExerciseId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {exercisesCatalog.map((ex) => (
                  <option key={ex.id} value={ex.id}>
                    {ex.name_id} ({ex.rep_range_min}-{ex.rep_range_max} rep)
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="set-reps" className="block text-xs font-semibold text-slate-700">
                  Repetisi
                </label>
                <input
                  id="set-reps"
                  type="number"
                  min={1}
                  max={100}
                  value={setReps}
                  onChange={(e) => setSetReps(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label htmlFor="set-load" className="block text-xs font-semibold text-slate-700">
                  Beban (kg)
                </label>
                <input
                  id="set-load"
                  type="number"
                  min={0}
                  step="0.5"
                  value={setLoadKg}
                  onChange={(e) => setSetLoadKg(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            </div>

            <button
              type="submit"
              data-testid="submit-workout-log"
              className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800"
            >
              Simpan Catatan Latihan
            </button>
          </form>

          <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-slate-900">Riwayat Latihan ({selectedDate})</h2>
            {progressionHint ? (
              <div className="rounded-lg border border-sky-300 bg-sky-50 p-3 text-xs text-sky-950">
                <strong>Saran Progresi:</strong> {progressionHint}
              </div>
            ) : null}
            {workoutLogs.length === 0 ? (
              <p className="text-sm text-slate-500">Belum ada catatan latihan pada tanggal ini.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {workoutLogs.map((wl) => (
                  <li key={wl.id} className="rounded-lg border border-slate-200 p-3">
                    <div className="font-semibold">
                      {wl.logged_date} — {wl.completed ? "✓ Selesai" : "Belum Selesai"} (Effort:{" "}
                      {wl.effort_rating || "-"})
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}

      {tab === "weight" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <form
            onSubmit={handleAddWeightLog}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4"
          >
            <h2 className="text-base font-bold text-slate-900">Catat Berat Badan</h2>
            <div>
              <label htmlFor="weight-input" className="block text-xs font-semibold text-slate-700">
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
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <label className="flex items-center gap-2 text-xs text-slate-700">
              <input
                type="checkbox"
                checked={applyToProfile}
                onChange={(e) => setApplyToProfile(e.target.checked)}
              />
              Perbarui berat profil & hitung ulang target gizi otomatis
            </label>

            <button
              type="submit"
              data-testid="submit-weight-log"
              className="w-full rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800"
            >
              Simpan Berat Badan
            </button>
          </form>

          <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-slate-900">Riwayat Berat Badan</h2>
            {weightLogs.length === 0 ? (
              <p className="text-sm text-slate-500">Belum ada catatan berat badan.</p>
            ) : (
              <table className="w-full text-left text-xs sm:text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-600">
                    <th className="py-2">Tanggal</th>
                    <th className="py-2">Berat Badan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {weightLogs.map((w) => (
                    <tr key={w.id}>
                      <td className="py-2">{w.logged_date}</td>
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

