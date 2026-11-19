"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiClientError } from "@/lib/api";
import { ErrorBanner } from "@/components/StatusWidgets";

export default function AdminExercisesPage() {
  const [exercises, setExercises] = useState<any[]>([]);
  const [code, setCode] = useState("");
  const [nameId, setNameId] = useState("");
  const [pattern, setPattern] = useState<
    "squat" | "hinge" | "horizontal_push" | "vertical_push" | "horizontal_pull" | "vertical_pull" | "core" | "accessory"
  >("accessory");
  const [primaryMuscle, setPrimaryMuscle] = useState("biceps");
  const [equipment, setEquipment] = useState("dumbbell");
  const [instructionsId, setInstructionsId] = useState(
    "Berdiri tegak, jaga siku di samping tubuh, angkat beban terkendali dan turunkan perlahan.",
  );
  const [reason, setReason] = useState("Penambahan variasi gerakan latihan katalog");
  const [banner, setBanner] = useState<string | null>(null);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  const loadExercises = useCallback(async () => {
    try {
      const res = await apiFetch<{ items: any[] }>("/exercises");
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

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBanner(null);
    try {
      await apiFetch("/admin/exercises", {
        method: "POST",
        body: JSON.stringify({
          code: code.toUpperCase().trim(),
          name_id: nameId.trim(),
          movement_pattern: pattern,
          primary_muscle: primaryMuscle,
          equipment_required: [equipment],
          instructions_id: instructionsId,
          reason,
        }),
      });
      setCode("");
      setNameId("");
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
          <h1 className="text-2xl font-bold text-content">Katalog latihan</h1>
          <p className="text-sm text-muted">Kelola daftar gerakan latihan, pola gerak, dan kontraindikasi cedera.</p>
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
            <label htmlFor="ex-code" className="block text-xs font-semibold text-secondary">
              Kode Unik (UPPER_SNAKE)
            </label>
            <input
              id="ex-code"
              type="text"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Contoh: HAMMER_CURL_DB"
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
              value={nameId}
              onChange={(e) => setNameId(e.target.value)}
              placeholder="Contoh: Dumbbell Hammer Curl"
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="ex-pat" className="block text-xs font-semibold text-secondary">
              Pola Gerakan
            </label>
            <select
              id="ex-pat"
              value={pattern}
              onChange={(e) => setPattern(e.target.value as any)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            >
              <option value="squat">Squat</option>
              <option value="hinge">Hinge</option>
              <option value="horizontal_push">Horizontal Push</option>
              <option value="vertical_push">Vertical Push</option>
              <option value="horizontal_pull">Horizontal Pull</option>
              <option value="vertical_pull">Vertical Pull</option>
              <option value="core">Core</option>
              <option value="accessory">Accessory</option>
            </select>
          </div>
          <div>
            <label htmlFor="ex-muscle" className="block text-xs font-semibold text-secondary">
              Otot Utama
            </label>
            <input
              id="ex-muscle"
              type="text"
              required
              value={primaryMuscle}
              onChange={(e) => setPrimaryMuscle(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="ex-eq" className="block text-xs font-semibold text-secondary">
              Peralatan
            </label>
            <select
              id="ex-eq"
              value={equipment}
              onChange={(e) => setEquipment(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            >
              <option value="bodyweight">Tanpa Alat (bodyweight)</option>
              <option value="dumbbell">Dumbbell</option>
              <option value="resistance_band">Resistance Band</option>
              <option value="pullup_bar">Pull-up Bar</option>
              <option value="full_gym">Gym Lengkap (full_gym)</option>
            </select>
          </div>
          <div>
            <label htmlFor="ex-inst" className="block text-xs font-semibold text-secondary">
              Instruksi Aman (min. 10 karakter)
            </label>
            <textarea
              id="ex-inst"
              rows={2}
              required
              minLength={10}
              value={instructionsId}
              onChange={(e) => setInstructionsId(e.target.value)}
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

        <div className="lg:col-span-2 rounded-xl border border-line bg-panel p-5 shadow-sm overflow-x-auto">
          <h2 className="text-base font-bold text-content mb-3">Daftar Katalog Latihan ({exercises.length})</h2>
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="py-2">Kode</th>
                <th className="py-2">Nama</th>
                <th className="py-2">Pola</th>
                <th className="py-2">Otot</th>
                <th className="py-2">Alat</th>
                <th className="py-2">Kontraindikasi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {exercises.map((ex) => (
                <tr key={ex.id}>
                  <td className="py-2 font-mono">{ex.code}</td>
                  <td className="py-2 font-medium">{ex.name_id}</td>
                  <td className="py-2">{ex.movement_pattern}</td>
                  <td className="py-2">{ex.primary_muscle}</td>
                  <td className="py-2">{(ex.equipment_required || []).join(", ")}</td>
                  <td className="py-2 text-danger">{(ex.contraindications || []).join(", ") || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

