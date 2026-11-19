"use client";

import { FeatureBanner } from "@/components/FeatureBanner";

import Link from "next/link";
import React, { useEffect, useState } from "react";
import { ConsultBlockBanner, ErrorBanner } from "@/components/StatusWidgets";
import { ApiClientError, apiFetch } from "@/lib/api";
import { formatDec1, formatInt } from "@/lib/errorMessages";

export default function NutritionPage() {
  const [target, setTarget] = useState<any | null>(null);
  const [profileBundle, setProfileBundle] = useState<any | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [ratio, setRatio] = useState<number>(1.6);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [prof, tgt, hist] = await Promise.all([
        apiFetch("/profile"),
        apiFetch("/nutrition/target"),
        apiFetch("/nutrition/target/history"),
      ]);
      setProfileBundle(prof);
      setTarget(tgt);
      setRatio(Number(tgt.protein_g_per_kg || 1.6));
      setHistory(hist.items || []);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleUpdateRatio() {
    setSaving(true);
    setError(null);
    try {
      await apiFetch("/profile", {
        method: "PATCH",
        body: JSON.stringify({ protein_g_per_kg: Number(ratio.toFixed(1)) }),
      });
      await loadAll();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-line bg-panel p-6 text-sm text-muted">
        Memuat estimasi kebutuhan energi &amp; protein...
      </div>
    );
  }

  if (!target) {
    return (
      <div className="rounded-xl border border-line bg-panel p-6 space-y-3">
        <h1 className="text-lg font-bold">Target Nutrisi Belum Tersedia</h1>
        <p className="text-sm text-muted">Lengkapi profil Anda terlebih dahulu untuk menghitung estimasi.</p>
        <Link href="/onboarding" className="inline-block rounded bg-accent-action px-4 py-2 text-xs font-semibold text-white">
          Lengkapi Profil
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <FeatureBanner kind="nutrition" title="Target nutrisi">Lihat estimasi energi dan protein harian berdasarkan profil Anda.</FeatureBanner>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-xl font-bold text-content">
            Target Energi &amp; Protein Harian <span className="text-xs font-normal text-muted">(Estimasi)</span>
          </h2>
          <p className="text-xs text-muted">
            Seluruh angka di bawah adalah <strong>estimasi</strong> matematis untuk orang dewasa sehat, bukan diagnosis medis.
          </p>
        </div>
        <Link href="/meal-plan" className="rounded bg-accent-action px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover">
          Susun Menu 7 Hari →
        </Link>
      </div>

      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}
      {profileBundle && !profileBundle.plan_generation_allowed ? <ConsultBlockBanner /> : null}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-line bg-panel p-4">
          <div className="text-xs text-muted">Estimasi REE (Mifflin–St Jeor)</div>
          <div data-testid="ree-value" className="text-2xl font-bold text-content mt-1">
            {formatDec1(target.ree_kcal)} kkal
          </div>
          <div className="text-[11px] text-muted mt-1">Energi istirahat harian</div>
        </div>
        <div className="rounded-xl border border-line bg-panel p-4">
          <div className="text-xs text-muted">Estimasi TDEE (× {formatDec1(target.activity_factor)})</div>
          <div data-testid="tdee-value" className="text-2xl font-bold text-content mt-1">
            {formatDec1(target.tdee_kcal)} kkal
          </div>
          <div className="text-[11px] text-muted mt-1">Penyesuaian tujuan: {target.goal_adjustment_pct}%</div>
        </div>
        <div className="rounded-xl border border-accent-line bg-accent-soft p-4">
          <div className="text-xs font-medium text-accent-ink">Target Energi Harian (Estimasi)</div>
          <div data-testid="energy-target-value" className="text-2xl font-bold text-accent-ink mt-1">
            {formatInt(target.energy_target_kcal)} kkal
          </div>
          <div className="text-[11px] text-accent-ink mt-1">Versi rumus: {target.formula_version}</div>
        </div>
        <div className="rounded-xl border border-positive-line bg-positive-soft p-4">
          <div className="text-xs font-medium text-positive">Target Protein Harian (Estimasi)</div>
          <div data-testid="protein-target-value" className="text-2xl font-bold text-positive mt-1">
            {formatInt(target.protein_target_g)} g
          </div>
          <div className="text-[11px] text-positive mt-1">{formatDec1(target.protein_g_per_kg)} g / kg BB</div>
        </div>
      </div>

      {target.warnings && target.warnings.length > 0 ? (
        <div className="rounded-lg border border-warning-line bg-warning-soft p-4 text-xs text-warning space-y-1">
          <div className="font-semibold">⚠ Catatan Keselamatan Perhitungan:</div>
          {target.warnings.map((w: any) => (
            <div key={w.code}>
              <strong>{w.code}:</strong> {w.message}
            </div>
          ))}
        </div>
      ) : null}

      <div className="rounded-xl border border-line bg-panel p-5 space-y-4">
        <h2 className="text-sm font-bold text-content">Sesuaikan Rasio Protein (1,4 – 2,0 g/kg BB)</h2>
        <div className="flex flex-wrap items-center gap-4">
          <label htmlFor="protein-slider" className="text-xs font-medium text-secondary">
            Rasio: <strong>{formatDec1(ratio)} g/kg</strong>
          </label>
          <input
            id="protein-slider"
            type="range"
            min={1.4}
            max={2.0}
            step={0.1}
            value={ratio}
            onChange={(e) => setRatio(Number(e.target.value))}
            className="w-48"
          />
          <button
            type="button"
            disabled={saving}
            onClick={handleUpdateRatio}
            className="rounded bg-accent-action px-3 py-1.5 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {saving ? "Menyimpan..." : "Simpan Rasio"}
          </button>
        </div>
        <div className="text-xs text-muted space-y-1 border-t border-line pt-3">
          <div>
            <strong>Rumus:</strong> REE = 10×BB + 6,25×TB − 5×Umur + s (+5 laki-laki, −161 perempuan); TDEE = REE ×
            faktor aktivitas.
          </div>
          <div>
            <strong>Asumsi:</strong> {(target.assumptions || []).join(" • ")}
          </div>
          <div>
            <strong>Sumber Ilmiah:</strong> Mifflin et al. (1990) [5], ISSN Position Stand Jäger et al. (2017) [6].
          </div>
          <div>
            <strong>Dihitung pada:</strong> {target.calculated_at}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-line bg-panel p-5 space-y-3">
        <h2 className="text-sm font-bold text-content">Riwayat Revisi Target ({history.length})</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="py-2 pr-3">Waktu</th>
                <th className="py-2 pr-3">REE</th>
                <th className="py-2 pr-3">TDEE</th>
                <th className="py-2 pr-3">Target Energi</th>
                <th className="py-2 pr-3">Target Protein</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id} className="border-b border-line">
                  <td className="py-2 pr-3">{h.created_at?.slice(0, 19).replace("T", " ")}</td>
                  <td className="py-2 pr-3">{formatDec1(h.ree_kcal)} kkal</td>
                  <td className="py-2 pr-3">{formatDec1(h.tdee_kcal)} kkal</td>
                  <td className="py-2 pr-3 font-semibold">{formatInt(h.energy_target_kcal)} kkal</td>
                  <td className="py-2 pr-3 font-semibold">{formatInt(h.protein_target_g)} g</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

