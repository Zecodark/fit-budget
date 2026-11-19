"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiClientError } from "@/lib/api";
import { formatDec1, formatIdr, formatInt } from "@/lib/errorMessages";
import { ErrorBanner } from "@/components/StatusWidgets";

interface DayItem {
  date: string;
  energy_kcal: { target: number; planned: number; actual: number };
  protein_g: { target: number; planned: number; actual: number };
  cost_idr: { budget: number; planned: number; actual: number };
  workout_planned: boolean;
  workout_completed: boolean;
}

interface DashboardSummary {
  week_start: string;
  week_end: string;
  days: DayItem[];
  week_totals: {
    energy_kcal: { target: number; planned: number; actual: number };
    protein_g: { target: number; planned: number; actual: number };
    cost_idr: { budget: number; planned: number; actual: number };
  };
  adherence: {
    food_logged_days: number;
    energy_within_10pct_days: number;
    protein_met_days: number;
    budget_met_days: number;
    workouts_planned: number;
    workouts_completed: number;
  };
  weight_trend: {
    latest_kg: number | null;
    delta_7d_kg: number | null;
    points: { date: string; weight_kg: number }[];
  };
  alerts: {
    code: string;
    severity: "info" | "warn" | "error";
    message: string;
    action_url: string;
  }[];
  text_summary: string;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<DashboardSummary>("/dashboard/summary");
      setData(res);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      } else {
        setError({ msg: "Gagal memuat ringkasan dashboard." });
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard Mingguan</h1>
          <p className="text-sm text-slate-600">
            Perbandingan Target vs Rencana vs Realisasi Aktual 7 Hari Terakhir
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/tracker"
            className="rounded-lg bg-emerald-700 px-3.5 py-2 text-xs font-semibold text-white hover:bg-emerald-800"
          >
            + Catat Hari Ini
          </Link>
          <Link
            href="/meal-plan"
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Rencana Makan
          </Link>
          <Link
            href="/workout"
            className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Jadwal Latihan
          </Link>
        </div>
      </div>

      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} onRetry={loadSummary} /> : null}

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="h-28 animate-pulse rounded-xl bg-slate-200" />
          ))}
        </div>
      ) : data ? (
        <>
          {/* Alerts list */}
          {data.alerts.length > 0 ? (
            <section aria-label="Peringatan dan Rekomendasi" className="space-y-2" data-testid="dashboard-alerts">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">
                Peringatan & Rekomendasi ({data.alerts.length})
              </h2>
              <div className="space-y-2">
                {data.alerts.map((al, i) => {
                  const style =
                    al.severity === "error"
                      ? "border-rose-300 bg-rose-50 text-rose-950"
                      : al.severity === "warn"
                        ? "border-amber-300 bg-amber-50 text-amber-950"
                        : "border-sky-300 bg-sky-50 text-sky-950";
                  const icon = al.severity === "error" ? "✕" : al.severity === "warn" ? "⚠" : "ℹ";
                  return (
                    <div
                      key={`${al.code}-${i}`}
                      data-testid={`alert-${al.code}`}
                      className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3.5 text-sm ${style}`}
                    >
                      <div>
                        <span className="font-bold mr-1.5" aria-hidden="true">
                          {icon}
                        </span>
                        <span className="font-semibold">[{al.code}]</span> {al.message}
                      </div>
                      <Link
                        href={al.action_url}
                        className="rounded bg-slate-900 px-3 py-1 text-xs font-semibold text-white hover:bg-slate-800"
                      >
                        Tindak Lanjuti
                      </Link>
                    </div>
                  );
                })}
              </div>
            </section>
          ) : null}

          {/* Accessible text summary (PRD §3.7) */}
          <div
            data-testid="dashboard-text-summary"
            className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-800"
          >
            <span className="font-semibold">Ringkasan Teks Aksesibel: </span>
            {data.text_summary}
          </div>

          {/* 4 KPI Cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-xs font-medium text-slate-500">Energi Mingguan (kkal)</div>
              <div className="mt-1 text-xl font-bold text-slate-900">
                {formatInt(data.week_totals.energy_kcal.actual)} / {formatInt(data.week_totals.energy_kcal.target)}
              </div>
              <div className="mt-1 text-xs text-slate-600">
                Rencana: {formatInt(data.week_totals.energy_kcal.planned)} kkal • Terpenuhi ±10%:{" "}
                {data.adherence.energy_within_10pct_days}/7 hari
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-xs font-medium text-slate-500">Protein Mingguan (gram)</div>
              <div className="mt-1 text-xl font-bold text-slate-900">
                {formatDec1(data.week_totals.protein_g.actual)} / {formatDec1(data.week_totals.protein_g.target)} g
              </div>
              <div className="mt-1 text-xs text-slate-600">
                Rencana: {formatDec1(data.week_totals.protein_g.planned)} g • Tercapai:{" "}
                {data.adherence.protein_met_days}/7 hari
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-xs font-medium text-slate-500">Pengeluaran vs Budget (7 Hari)</div>
              <div className="mt-1 text-xl font-bold text-slate-900">
                {formatIdr(data.week_totals.cost_idr.actual)}
              </div>
              <div className="mt-1 text-xs text-slate-600">
                Budget: {formatIdr(data.week_totals.cost_idr.budget)} • Rencana:{" "}
                {formatIdr(data.week_totals.cost_idr.planned)}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-xs font-medium text-slate-500">Latihan & Berat Badan</div>
              <div className="mt-1 text-xl font-bold text-slate-900">
                {data.adherence.workouts_completed} / {data.adherence.workouts_planned} Sesi
              </div>
              <div className="mt-1 text-xs text-slate-600">
                Berat terkini:{" "}
                {data.weight_trend.latest_kg !== null ? `${formatDec1(data.weight_trend.latest_kg)} kg` : "Belum ada"}
                {data.weight_trend.delta_7d_kg !== null
                  ? ` (${data.weight_trend.delta_7d_kg >= 0 ? "+" : ""}${formatDec1(data.weight_trend.delta_7d_kg)} kg)`
                  : ""}
              </div>
            </div>
          </div>

          {/* 7-day breakdown table + visual bars */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
            <h2 className="text-base font-bold text-slate-900">
              Rincian Harian ({data.week_start} s/d {data.week_end})
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs sm:text-sm border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-600">
                    <th className="py-2 pr-3">Tanggal</th>
                    <th className="py-2 px-3">Energi (Aktual / Rencana / Target)</th>
                    <th className="py-2 px-3">Protein (Aktual / Rencana / Target)</th>
                    <th className="py-2 px-3">Biaya (Aktual / Rencana / Budget)</th>
                    <th className="py-2 pl-3">Latihan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.days.map((d) => {
                    const kcalPct =
                      d.energy_kcal.target > 0
                        ? Math.min(100, Math.round((d.energy_kcal.actual / d.energy_kcal.target) * 100))
                        : 0;
                    const protPct =
                      d.protein_g.target > 0
                        ? Math.min(100, Math.round((d.protein_g.actual / d.protein_g.target) * 100))
                        : 0;
                    return (
                      <tr key={d.date}>
                        <td className="py-2.5 pr-3 font-medium text-slate-900 whitespace-nowrap">{d.date}</td>
                        <td className="py-2.5 px-3">
                          <div className="font-medium text-slate-800">
                            {formatInt(d.energy_kcal.actual)} / {formatInt(d.energy_kcal.planned)} /{" "}
                            {formatInt(d.energy_kcal.target)} kkal
                          </div>
                          <div className="mt-1 h-1.5 w-full rounded bg-slate-100">
                            <div className="h-1.5 rounded bg-emerald-600" style={{ width: `${kcalPct}%` }} />
                          </div>
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="font-medium text-slate-800">
                            {formatDec1(d.protein_g.actual)} / {formatDec1(d.protein_g.planned)} /{" "}
                            {formatDec1(d.protein_g.target)} g
                          </div>
                          <div className="mt-1 h-1.5 w-full rounded bg-slate-100">
                            <div className="h-1.5 rounded bg-sky-600" style={{ width: `${protPct}%` }} />
                          </div>
                        </td>
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          {formatIdr(d.cost_idr.actual)} / {formatIdr(d.cost_idr.planned)} /{" "}
                          {formatIdr(d.cost_idr.budget)}
                        </td>
                        <td className="py-2.5 pl-3 whitespace-nowrap">
                          {d.workout_completed ? (
                            <span className="inline-flex rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-900">
                              ✓ Selesai
                            </span>
                          ) : d.workout_planned ? (
                            <span className="inline-flex rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
                              Terjadwal
                            </span>
                          ) : (
                            <span className="text-slate-400">Istirahat</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

