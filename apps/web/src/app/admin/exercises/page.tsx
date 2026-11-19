"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiClientError } from "@/lib/api";
import {
  CatalogExercise,
  EQUIPMENT_META,
  ExerciseEquipment,
  ExerciseModeFilter,
  filterExercises,
  formatMuscleLabel,
  formatPatternLabel,
  formatRepRange,
  MUSCLE_GROUP_LABELS,
  PATTERN_LABELS,
} from "@/lib/exercises";
import { ErrorBanner } from "@/components/StatusWidgets";

export default function AdminExercisesPage() {
  const [exercises, setExercises] = useState<CatalogExercise[]>([]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [pattern, setPattern] = useState<string>("horizontal_push");
  const [muscleGroup, setMuscleGroup] = useState("chest");
  const [equipment, setEquipment] = useState<ExerciseEquipment>("gym");
  const [difficulty, setDifficulty] = useState<1 | 2>(1);
  const [sets, setSets] = useState(3);
  const [repsMin, setRepsMin] = useState(8);
  const [repsMax, setRepsMax] = useState(12);
  const [unit, setUnit] = useState<"reps" | "seconds">("reps");
  const [restS, setRestS] = useState(60);
  const [instructions, setInstructions] = useState(
    "Jaga postur tubuh netral, lakukan gerakan terkontrol sesuai rentang gerak aman, dan atur pernapasan.",
  );
  const [reason, setReason] = useState("Penambahan variasi gerakan latihan katalog");

  // Catalog filters
  const [listMode, setListMode] = useState<ExerciseModeFilter>("all");
  const [listSearch, setListSearch] = useState("");

  const [banner, setBanner] = useState<string | null>(null);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  const loadExercises = useCallback(async () => {
    try {
      const res = await apiFetch<{ items: CatalogExercise[] }>("/exercises");
      setExercises(res.items || []);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }, []);

  useEffect(() => {
    loadExercises();
  }, [loadExercises]);

  const filteredList = useMemo(
    () =>
      filterExercises(exercises, {
        mode: listMode,
        gymSub: "all_gym",
        workoutSub: "bodyweight_only",
        search: listSearch,
      }),
    [exercises, listMode, listSearch],
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBanner(null);
    try {
      await apiFetch("/admin/exercises", {
        method: "POST",
        body: JSON.stringify({
          code: code.toUpperCase().trim(),
          name: name.trim(),
          pattern,
          muscle_group: muscleGroup,
          equipment,
          difficulty: Number(difficulty),
          rank: 50,
          sets: Number(sets),
          reps_min: Number(repsMin),
          reps_max: Number(repsMax),
          unit,
          rest_s: Number(restS),
          instructions: instructions.trim(),
          reason: reason.trim(),
        }),
      });
      setCode("");
      setName("");
      setBanner("Gerakan latihan baru berhasil disimpan & tercatat di audit log.");
      await loadExercises();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="route-intro flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-content">Katalog latihan (Gym &amp; Workout)</h1>
          <p className="text-sm text-muted">
            Kelola daftar gerakan Gym dan Workout rumahan, pola gerak, target set/repetisi, serta instruksi aman.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <Link href="/admin/foods" className="rounded-lg border border-line-strong bg-panel px-3 py-1.5">
            Katalog Pangan
          </Link>
          <Link href="/admin/prices" className="rounded-lg border border-line-strong bg-panel px-3 py-1.5">
            Harga Pangan
          </Link>
          <Link href="/admin/audit" className="rounded-lg border border-line-strong bg-panel px-3 py-1.5">
            Log Audit
          </Link>
        </div>
      </div>

      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}
      {banner ? (
        <div className="rounded-lg border border-positive-line bg-positive-soft p-3 text-sm text-positive">
          ✓ {banner}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <form
          onSubmit={handleCreate}
          className="rounded-xl border border-line bg-panel p-5 shadow-sm space-y-3"
        >
          <h2 className="text-base font-bold text-content">Tambah Gerakan Baru</h2>
          <div>
            <label htmlFor="ex-eq" className="block text-xs font-semibold text-secondary">
              Kategori / Peralatan (Gym vs Workout)
            </label>
            <select
              id="ex-eq"
              value={equipment}
              onChange={(e) => setEquipment(e.target.value as ExerciseEquipment)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            >
              <option value="gym">Gym — Barbell / Mesin / Cable</option>
              <option value="bodyweight">Workout — Tanpa Alat (Bodyweight / Rumahan)</option>
              <option value="dumbbell">Dumbbell — Bisa di Gym &amp; Rumahan</option>
            </select>
          </div>
          <div>
            <label htmlFor="ex-code" className="block text-xs font-semibold text-secondary">
              Kode Unik
            </label>
            <input
              id="ex-code"
              type="text"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Contoh: EX191"
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="ex-name" className="block text-xs font-semibold text-secondary">
              Nama Gerakan
            </label>
            <input
              id="ex-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Contoh: Incline Cable Fly"
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="ex-pat" className="block text-xs font-semibold text-secondary">
                Pola Gerakan
              </label>
              <select
                id="ex-pat"
                value={pattern}
                onChange={(e) => setPattern(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-1.5 text-xs sm:text-sm"
              >
                {Object.entries(PATTERN_LABELS).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="ex-muscle" className="block text-xs font-semibold text-secondary">
                Kelompok Otot
              </label>
              <select
                id="ex-muscle"
                value={muscleGroup}
                onChange={(e) => setMuscleGroup(e.target.value)}
                className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-1.5 text-xs sm:text-sm"
              >
                {Object.entries(MUSCLE_GROUP_LABELS).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="ex-diff" className="block text-xs font-semibold text-secondary">
                Kesulitan
              </label>
              <select
                id="ex-diff"
                value={difficulty}
                onChange={(e) => setDifficulty(Number(e.target.value) as 1 | 2)}
                className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-1.5 text-xs sm:text-sm"
              >
                <option value={1}>Pemula (1)</option>
                <option value={2}>Menengah (2)</option>
              </select>
            </div>
            <div>
              <label htmlFor="ex-unit" className="block text-xs font-semibold text-secondary">
                Satuan
              </label>
              <select
                id="ex-unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value as "reps" | "seconds")}
                className="mt-1 w-full rounded-lg border border-line-strong px-2.5 py-1.5 text-xs sm:text-sm"
              >
                <option value="reps">Repetisi (reps)</option>
                <option value="seconds">Durasi (seconds)</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-4 gap-2">
            <div>
              <label htmlFor="ex-sets" className="block text-[11px] font-semibold text-secondary">
                Set
              </label>
              <input
                id="ex-sets"
                type="number"
                min={1}
                max={10}
                value={sets}
                onChange={(e) => setSets(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-2 py-1.5 text-xs"
              />
            </div>
            <div>
              <label htmlFor="ex-rmin" className="block text-[11px] font-semibold text-secondary">
                Min
              </label>
              <input
                id="ex-rmin"
                type="number"
                min={1}
                max={600}
                value={repsMin}
                onChange={(e) => setRepsMin(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-2 py-1.5 text-xs"
              />
            </div>
            <div>
              <label htmlFor="ex-rmax" className="block text-[11px] font-semibold text-secondary">
                Max
              </label>
              <input
                id="ex-rmax"
                type="number"
                min={1}
                max={600}
                value={repsMax}
                onChange={(e) => setRepsMax(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-2 py-1.5 text-xs"
              />
            </div>
            <div>
              <label htmlFor="ex-rest" className="block text-[11px] font-semibold text-secondary">
                Istirahat
              </label>
              <input
                id="ex-rest"
                type="number"
                min={10}
                max={300}
                value={restS}
                onChange={(e) => setRestS(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-2 py-1.5 text-xs"
              />
            </div>
          </div>
          <div>
            <label htmlFor="ex-inst" className="block text-xs font-semibold text-secondary">
              Instruksi Aman
            </label>
            <textarea
              id="ex-inst"
              rows={2}
              required
              minLength={10}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-xs"
            />
          </div>
          <div>
            <label htmlFor="ex-reason" className="block text-xs font-semibold text-secondary">
              Alasan Audit (wajib)
            </label>
            <input
              id="ex-reason"
              type="text"
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-lg bg-positive-hover px-4 py-2 text-xs font-semibold text-white hover:bg-positive-hover"
          >
            Simpan Gerakan
          </button>
        </form>

        <div className="lg:col-span-2 rounded-xl border border-line bg-panel p-5 shadow-sm space-y-3 overflow-x-auto">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-bold text-content">
              Daftar Katalog Latihan ({filteredList.length} / {exercises.length})
            </h2>
            <div className="flex flex-wrap items-center gap-1.5">
              {(["all", "gym", "workout"] as ExerciseModeFilter[]).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setListMode(m)}
                  className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                    listMode === m
                      ? "border-accent-line bg-accent-soft text-accent-ink"
                      : "border-line bg-inset text-muted"
                  }`}
                >
                  {m === "all" ? "Semua" : m === "gym" ? "Gym" : "Workout"}
                </button>
              ))}
              <input
                type="text"
                value={listSearch}
                onChange={(e) => setListSearch(e.target.value)}
                placeholder="Cari gerakan..."
                className="rounded-lg border border-line-strong px-2.5 py-1 text-xs"
              />
            </div>
          </div>

          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="py-2">Kode</th>
                <th className="py-2">Nama</th>
                <th className="py-2">Kategori</th>
                <th className="py-2">Otot</th>
                <th className="py-2">Pola</th>
                <th className="py-2">Target</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {filteredList.map((ex) => {
                const eqMeta = EQUIPMENT_META[ex.equipment] || EQUIPMENT_META.gym;
                return (
                  <tr key={ex.id}>
                    <td className="py-2 font-mono">{ex.code}</td>
                    <td className="py-2 font-medium text-content">{ex.name}</td>
                    <td className="py-2">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${eqMeta.badgeClass}`}
                      >
                        {eqMeta.badge}
                      </span>
                    </td>
                    <td className="py-2">{formatMuscleLabel(ex.muscle_group)}</td>
                    <td className="py-2">{formatPatternLabel(ex.pattern)}</td>
                    <td className="py-2 text-secondary">
                      {ex.sets}× {formatRepRange(ex)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
