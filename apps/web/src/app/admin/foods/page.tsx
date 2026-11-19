"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiClientError } from "@/lib/api";
import { formatDec1, formatIdr, formatInt } from "@/lib/errorMessages";
import { ErrorBanner } from "@/components/StatusWidgets";

export default function AdminFoodsPage() {
  const [foods, setFoods] = useState<any[]>([]);
  const [code, setCode] = useState("");
  const [nameId, setNameId] = useState("");
  const [category, setCategory] = useState<"carb" | "protein_animal" | "protein_plant" | "vegetable" | "fruit" | "fat">(
    "protein_plant",
  );
  const [kcal, setKcal] = useState(150);
  const [protein, setProtein] = useState(15);
  const [carbs, setCarbs] = useState(10);
  const [fat, setFat] = useState(5);
  const [fiber, setFiber] = useState(3);
  const [reason, setReason] = useState("Penambahan bahan pangan katalog baru");
  const [banner, setBanner] = useState<string | null>(null);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  const loadFoods = useCallback(async () => {
    try {
      const res = await apiFetch<{ items: any[] }>("/foods");
      setFoods(res.items || []);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }, []);

  useEffect(() => {
    loadFoods();
  }, [loadFoods]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBanner(null);
    try {
      await apiFetch("/admin/foods", {
        method: "POST",
        body: JSON.stringify({
          code: code.toUpperCase().trim(),
          name_id: nameId.trim(),
          category,
          energy_kcal_per_100g: Number(kcal),
          protein_g_per_100g: Number(protein),
          carbs_g_per_100g: Number(carbs),
          fat_g_per_100g: Number(fat),
          fiber_g_per_100g: Number(fiber),
          reason,
        }),
      });
      setCode("");
      setNameId("");
      setBanner("Bahan pangan baru berhasil ditambahkan & tercatat di audit log.");
      await loadFoods();
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
          <h1 className="text-2xl font-bold text-content">Katalog pangan</h1>
          <p className="text-sm text-muted">Kelola data nutrisi bahan pangan per 100g bagian dapat dimakan.</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <Link href="/admin/prices" className="rounded-lg border border-line-strong bg-panel px-3 py-1.5">
            Harga Pangan
          </Link>
          <Link href="/admin/exercises" className="rounded-lg border border-line-strong bg-panel px-3 py-1.5">
            Katalog Latihan
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
          <h2 className="text-base font-bold text-content">Tambah Pangan Baru</h2>
          <div>
            <label htmlFor="food-code" className="block text-xs font-semibold text-secondary">
              Kode Unik (UPPER_SNAKE)
            </label>
            <input
              id="food-code"
              type="text"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Contoh: EDAMAME"
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="food-name" className="block text-xs font-semibold text-secondary">
              Nama Pangan (Bahasa Indonesia)
            </label>
            <input
              id="food-name"
              type="text"
              required
              value={nameId}
              onChange={(e) => setNameId(e.target.value)}
              placeholder="Contoh: Edamame Rebus"
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="food-cat" className="block text-xs font-semibold text-secondary">
              Kategori
            </label>
            <select
              id="food-cat"
              value={category}
              onChange={(e) => setCategory(e.target.value as any)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            >
              <option value="carb">Karbohidrat (carb)</option>
              <option value="protein_animal">Protein Hewani (protein_animal)</option>
              <option value="protein_plant">Protein Nabati (protein_plant)</option>
              <option value="vegetable">Sayuran (vegetable)</option>
              <option value="fruit">Buah (fruit)</option>
              <option value="fat">Lemak / Pelengkap (fat)</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="f-kcal" className="block text-xs font-semibold text-secondary">
                Energi (kkal/100g)
              </label>
              <input
                id="f-kcal"
                type="number"
                required
                value={kcal}
                onChange={(e) => setKcal(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label htmlFor="f-prot" className="block text-xs font-semibold text-secondary">
                Protein (g/100g)
              </label>
              <input
                id="f-prot"
                type="number"
                step="0.1"
                required
                value={protein}
                onChange={(e) => setProtein(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label htmlFor="f-carb" className="block text-xs font-semibold text-secondary">
                Karbo (g/100g)
              </label>
              <input
                id="f-carb"
                type="number"
                step="0.1"
                required
                value={carbs}
                onChange={(e) => setCarbs(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label htmlFor="f-fat" className="block text-xs font-semibold text-secondary">
                Lemak (g/100g)
              </label>
              <input
                id="f-fat"
                type="number"
                step="0.1"
                required
                value={fat}
                onChange={(e) => setFat(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-line-strong px-2 py-1 text-sm"
              />
            </div>
          </div>
          <div>
            <label htmlFor="f-fiber" className="block text-xs font-semibold text-secondary">
              Serat (g/100g)
            </label>
            <input
              id="f-fiber"
              type="number"
              step="0.1"
              required
              value={fiber}
              onChange={(e) => setFiber(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-line-strong px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label htmlFor="f-reason" className="block text-xs font-semibold text-secondary">
              Alasan Audit (wajib)
            </label>
            <input
              id="f-reason"
              type="text"
              required
              minLength={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-lg bg-positive-hover px-4 py-2 text-xs font-semibold text-white hover:bg-positive-hover"
          >
            Simpan Bahan Pangan
          </button>
        </form>

        <div className="lg:col-span-2 rounded-xl border border-line bg-panel p-5 shadow-sm overflow-x-auto">
          <h2 className="text-base font-bold text-content mb-3">Daftar Katalog Pangan ({foods.length})</h2>
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="py-2">Kode</th>
                <th className="py-2">Nama</th>
                <th className="py-2">Kategori</th>
                <th className="py-2">Kkal/100g</th>
                <th className="py-2">Prot/100g</th>
                <th className="py-2">Harga/100g</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {foods.map((f) => (
                <tr key={f.id}>
                  <td className="py-2 font-mono">{f.code}</td>
                  <td className="py-2 font-medium">{f.name_id}</td>
                  <td className="py-2">{f.category}</td>
                  <td className="py-2">{formatInt(f.energy_kcal_per_100g)}</td>
                  <td className="py-2">{formatDec1(f.protein_g_per_100g)} g</td>
                  <td className="py-2">{formatIdr(f.current_price_idr_per_100g)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

