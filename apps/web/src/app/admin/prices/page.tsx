"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiClientError } from "@/lib/api";
import { formatIdr } from "@/lib/errorMessages";
import { ErrorBanner } from "@/components/StatusWidgets";

export default function AdminPricesPage() {
  const [foods, setFoods] = useState<any[]>([]);
  const [foodId, setFoodId] = useState("");
  const [priceIdr, setPriceIdr] = useState(2500);
  const [source, setSource] = useState("manual_admin");
  const [reason, setReason] = useState("Pembaruan harga pasar mingguan");
  const [csvText, setCsvText] = useState(
    "food_code,region,price_idr_per_100g,source,recorded_at\nTEMPE,ID-Nasional,2600,pihip_manual,2026-06-01",
  );
  const [confirmLarge, setConfirmLarge] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  const loadFoods = useCallback(async () => {
    try {
      const res = await apiFetch<{ items: any[] }>("/foods");
      setFoods(res.items || []);
      if (!foodId && res.items?.length > 0) {
        setFoodId(res.items[0].id);
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }, [foodId]);

  useEffect(() => {
    loadFoods();
  }, [loadFoods]);

  const handleAddSinglePrice = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBanner(null);
    try {
      await apiFetch("/admin/prices", {
        method: "POST",
        body: JSON.stringify({
          food_id: foodId,
          region: "ID-Nasional",
          price_idr_per_100g: Number(priceIdr),
          source,
          reason,
        }),
      });
      setBanner("Harga baru berhasil disimpan (append-only) dan tercatat di audit log.");
      await loadFoods();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  const handleCsvImport = async (dryRun: boolean) => {
    setError(null);
    setBanner(null);
    try {
      const formData = new FormData();
      const blob = new Blob([csvText], { type: "text/csv" });
      formData.append("file", blob, "prices.csv");
      const url = `/admin/prices/import?dry_run=${dryRun}&confirm_large_changes=${confirmLarge}&reason=${encodeURIComponent(reason)}`;
      const res = await apiFetch<any>(url, {
        method: "POST",
        body: formData,
      });
      setImportResult(res);
      if (!dryRun && res.applied) {
        setBanner(`Impor CSV berhasil diterapkan (${res.valid_rows} baris).`);
        await loadFoods();
      }
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
          <h1 className="text-2xl font-bold text-content">Harga pangan</h1>
          <p className="text-sm text-muted">
            Riwayat harga bersifat append-only agar rencana makan yang telah dikonfirmasi tetap dapat direproduksi.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <Link href="/admin/foods" className="rounded-lg border border-line-strong bg-panel px-3 py-1.5">
            Katalog Pangan
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

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <form
          onSubmit={handleAddSinglePrice}
          className="rounded-xl border border-line bg-panel p-5 shadow-sm space-y-3"
        >
          <h2 className="text-base font-bold text-content">Tambah Harga Satuan</h2>
          <div>
            <label htmlFor="p-food" className="block text-xs font-semibold text-secondary">
              Bahan Pangan
            </label>
            <select
              id="p-food"
              value={foodId}
              onChange={(e) => setFoodId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
            >
              {foods.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.code} — {f.name_id} (Saat ini: {formatIdr(f.current_price_idr_per_100g)}/100g)
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="p-idr" className="block text-xs font-semibold text-secondary">
              Harga Baru (Rp per 100g)
            </label>
            <input
              id="p-idr"
              type="number"
              min={100}
              max={100000}
              required
              value={priceIdr}
              onChange={(e) => setPriceIdr(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="p-source" className="block text-xs font-semibold text-secondary">
              Sumber Harga
            </label>
            <input
              id="p-source"
              type="text"
              required
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="p-reason" className="block text-xs font-semibold text-secondary">
              Alasan Audit (wajib)
            </label>
            <input
              id="p-reason"
              type="text"
              required
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg bg-positive-hover px-4 py-2 text-xs font-semibold text-white hover:bg-positive-hover"
          >
            Simpan Harga Baru
          </button>
        </form>

        <div className="rounded-xl border border-line bg-panel p-5 shadow-sm space-y-3">
          <h2 className="text-base font-bold text-content">Impor Massal CSV (dengan Dry-Run)</h2>
          <label htmlFor="csv-textarea" className="block text-xs font-semibold text-secondary">
            Isi CSV (`food_code,region,price_idr_per_100g,source,recorded_at`)
          </label>
          <textarea
            id="csv-textarea"
            rows={5}
            value={csvText}
            onChange={(e) => setCsvText(e.target.value)}
            className="w-full rounded-lg border border-line-strong p-2 font-mono text-xs"
          />
          <label className="flex items-center gap-2 text-xs text-secondary">
            <input
              type="checkbox"
              checked={confirmLarge}
              onChange={(e) => setConfirmLarge(e.target.checked)}
            />
            Konfirmasi perubahan harga besar (&gt; 50%)
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleCsvImport(true)}
              className="rounded-lg border border-line-strong bg-raised px-3.5 py-2 text-xs font-semibold text-secondary hover:bg-line"
            >
              1. Pratinjau (Dry-Run)
            </button>
            <button
              type="button"
              onClick={() => handleCsvImport(false)}
              className="rounded-lg bg-accent-hover px-3.5 py-2 text-xs font-semibold text-white hover:bg-accent-hover"
            >
              2. Terapkan Impor CSV
            </button>
          </div>
          {importResult ? (
            <div className="rounded-lg border border-line bg-inset p-3 text-xs space-y-1">
              <div>
                Baris valid: <strong>{importResult.valid_rows}</strong> • Diterapkan:{" "}
                <strong>{String(importResult.applied)}</strong>
              </div>
              {importResult.warnings?.length > 0 ? (
                <div className="text-warning">
                  Peringatan lonjakan (&gt;50%): {importResult.warnings.length} baris
                </div>
              ) : null}
              {importResult.errors?.length > 0 ? (
                <div className="text-danger">Error: {JSON.stringify(importResult.errors)}</div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

