"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  ConsultBlockBanner,
  ErrorBanner,
  MealPlanStatusPanel,
  StatusBadge,
} from "@/components/StatusWidgets";
import { ApiClientError, apiFetch } from "@/lib/api";
import { SLOT_LABELS_ID, currentMondayIso, formatDec1, formatIdr, formatInt } from "@/lib/errorMessages";

export default function MealPlanPage() {
  const [startDate, setStartDate] = useState(currentMondayIso());
  const [budgetIdr, setBudgetIdr] = useState<number>(45000);
  const [plan, setPlan] = useState<any | null>(null);
  const [plansHistory, setPlansHistory] = useState<any[]>([]);
  const [infeasibleDetails, setInfeasibleDetails] = useState<any | null>(null);
  const [selectedDayIdx, setSelectedDayIdx] = useState(0);
  const [activeTab, setActiveTab] = useState<"menu" | "shopping" | "versions">("menu");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [consultBlocked, setConsultBlocked] = useState(false);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function loadInitial() {
    setLoading(true);
    try {
      const [prof, listRes] = await Promise.all([
        apiFetch("/profile").catch(() => null),
        apiFetch("/meal-plans").catch(() => ({ items: [] })),
      ]);
      if (prof?.preferences?.daily_budget_idr) {
        setBudgetIdr(prof.preferences.daily_budget_idr);
      }
      if (prof && !prof.plan_generation_allowed) {
        setConsultBlocked(true);
      }
      const items = listRes.items || [];
      setPlansHistory(items);
      if (items.length > 0) {
        const detail = await apiFetch(`/meal-plans/${items[0].id}`);
        setPlan(detail);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadInitial();
  }, []);

  async function handleGenerate() {
    setError(null);
    setInfeasibleDetails(null);
    setGenerating(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await apiFetch("/meal-plans/generate", {
        method: "POST",
        signal: ctrl.signal,
        body: JSON.stringify({
          start_date: startDate,
          daily_budget_idr: Number(budgetIdr),
        }),
      });
      setPlan(res);
      setSelectedDayIdx(0);
      const listRes = await apiFetch("/meal-plans");
      setPlansHistory(listRes.items || []);
    } catch (err: any) {
      if (err?.name === "AbortError") {
        setError({ msg: "Penyusunan menu dibatalkan oleh pengguna." });
      } else if (err instanceof ApiClientError) {
        if (err.code === "NO_FEASIBLE_PLAN") {
          setInfeasibleDetails(err.details);
        } else if (err.code === "PROFESSIONAL_CONSULT_REQUIRED") {
          setConsultBlocked(true);
        } else {
          setError({ msg: err.message, reqId: err.requestId });
        }
      } else {
        setError({ msg: "Gagal menyusun menu." });
      }
    } finally {
      setGenerating(false);
      abortRef.current = null;
    }
  }

  async function handleConfirm() {
    if (!plan) return;
    setError(null);
    try {
      const updated = await apiFetch(`/meal-plans/${plan.id}/confirm`, {
        method: "POST",
        body: JSON.stringify({ base_version: plan.version }),
      });
      setPlan(updated);
      const listRes = await apiFetch("/meal-plans");
      setPlansHistory(listRes.items || []);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }

  async function handleAdjustGrams(itemId: string, newGrams: number) {
    if (!plan || newGrams <= 0) return;
    setError(null);
    try {
      const updated = await apiFetch(`/meal-plans/${plan.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          base_version: plan.version,
          operations: [{ op: "set_grams", item_id: itemId, grams: newGrams }],
        }),
      });
      setPlan(updated);
      const listRes = await apiFetch("/meal-plans");
      setPlansHistory(listRes.items || []);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }

  async function handleRemoveItem(itemId: string) {
    if (!plan) return;
    setError(null);
    try {
      const updated = await apiFetch(`/meal-plans/${plan.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          base_version: plan.version,
          operations: [{ op: "remove_item", item_id: itemId }],
        }),
      });
      setPlan(updated);
      const listRes = await apiFetch("/meal-plans");
      setPlansHistory(listRes.items || []);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  }

  const displayPlan = infeasibleDetails?.best_effort || plan;
  const activeDay = displayPlan?.days?.[selectedDayIdx] || displayPlan?.days?.[0];

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Optimasi Menu 7 Hari (CP-SAT)</h1>
            <p className="text-xs text-slate-600">
              Menyusun porsi gram bahan mentah lokal (berat bersih/edible) dalam batas budget harian.
            </p>
          </div>
          {plan ? <StatusBadge status={plan.result_status} /> : null}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="mp-start" className="block text-xs font-semibold text-slate-700 mb-1">
              Tanggal Mulai
            </label>
            <input
              id="mp-start"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="mp-budget" className="block text-xs font-semibold text-slate-700 mb-1">
              Budget Harian (Rp)
            </label>
            <input
              id="mp-budget"
              type="number"
              min={10000}
              max={500000}
              step={1000}
              value={budgetIdr}
              onChange={(e) => setBudgetIdr(Number(e.target.value))}
              className="rounded border border-slate-300 px-3 py-1.5 text-sm w-36"
            />
          </div>
          <button
            type="button"
            disabled={generating || consultBlocked}
            onClick={handleGenerate}
            data-testid="generate-meal-btn"
            className="rounded bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {generating ? "Menyusun Menu..." : "Generate Menu 7 Hari"}
          </button>
          {generating && abortRef.current ? (
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="rounded border border-rose-300 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-800"
            >
              Batal
            </button>
          ) : null}
          {plan && plan.status === "draft" && plan.result_status !== "INFEASIBLE" ? (
            <button
              type="button"
              onClick={handleConfirm}
              data-testid="confirm-meal-btn"
              className="rounded bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700"
            >
              Konfirmasi &amp; Kunci Rencana (v{plan.version})
            </button>
          ) : null}
        </div>
      </div>

      {consultBlocked ? <ConsultBlockBanner /> : null}
      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}

      {infeasibleDetails ? (
        <div className="space-y-3">
          <MealPlanStatusPanel
            resultStatus="INFEASIBLE"
            unmetConstraints={infeasibleDetails.unmet_constraints || []}
            minimumBudgetRequiredIdr={infeasibleDetails.minimum_budget_required_idr}
            suggestions={infeasibleDetails.suggestions || []}
          />
          <div className="rounded-lg border border-rose-300 bg-rose-100/70 px-4 py-2 text-xs font-semibold text-rose-950">
            Menampilkan alternatif pendekatan terbaik (best effort) — <strong>belum memenuhi target</strong> dan tidak
            disimpan sebagai rencana terkonfirmasi.
          </div>
        </div>
      ) : plan ? (
        <MealPlanStatusPanel
          resultStatus={plan.result_status}
          unmetConstraints={plan.unmet_constraints || []}
        />
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-500">
          Memuat rencana menu...
        </div>
      ) : displayPlan ? (
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
            <div className="flex gap-2 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setActiveTab("menu")}
                className={`rounded px-3 py-1.5 ${
                  activeTab === "menu" ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"
                }`}
              >
                Rincian 7 Hari
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("shopping")}
                className={`rounded px-3 py-1.5 ${
                  activeTab === "shopping" ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"
                }`}
              >
                Daftar Belanja ({displayPlan.shopping_list?.length || 0})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("versions")}
                className={`rounded px-3 py-1.5 ${
                  activeTab === "versions" ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"
                }`}
              >
                Riwayat Versi ({plansHistory.length})
              </button>
            </div>
            <div className="text-xs text-slate-600">
              Total proporsional 7 hari: <strong>{formatIdr(displayPlan.week_totals?.cost_idr)}</strong> • Rata-rata{" "}
              <strong>{formatDec1(displayPlan.week_totals?.avg_energy_kcal)} kkal</strong> &amp;{" "}
              <strong>{formatDec1(displayPlan.week_totals?.avg_protein_g)} g protein</strong>
            </div>
          </div>

          {activeTab === "menu" && activeDay ? (
            <div className="space-y-4">
              <div className="flex flex-wrap gap-1.5">
                {displayPlan.days.map((d: any, idx: number) => (
                  <button
                    key={d.date}
                    type="button"
                    onClick={() => setSelectedDayIdx(idx)}
                    className={`rounded px-3 py-1.5 text-xs font-medium border ${
                      idx === selectedDayIdx
                        ? "border-indigo-600 bg-indigo-50 text-indigo-900"
                        : "border-slate-200 bg-white text-slate-700"
                    }`}
                  >
                    Hari {idx + 1} ({d.date.slice(5)}) — {d.day_status}
                  </button>
                ))}
              </div>

              <div className="rounded-lg bg-slate-50 p-3 text-xs flex flex-wrap items-center justify-between gap-2 border border-slate-200">
                <div>
                  Biaya hari ini: <strong>{formatIdr(activeDay.totals.cost_idr)}</strong> /{" "}
                  {formatIdr(displayPlan.budget_limit_idr)}
                </div>
                <div>
                  Energi: <strong>{formatDec1(activeDay.totals.energy_kcal)} kkal</strong> (target{" "}
                  {formatInt(displayPlan.targets?.energy_kcal)} kkal) • Protein:{" "}
                  <strong>{formatDec1(activeDay.totals.protein_g)} g</strong> (target{" "}
                  {formatInt(displayPlan.targets?.protein_g)} g) • Sayur:{" "}
                  <strong>{formatInt(activeDay.totals.vegetable_g)} g</strong>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {activeDay.slots.map((slot: any) => (
                  <div key={slot.slot} className="rounded-lg border border-slate-200 p-3 space-y-2">
                    <div className="text-xs font-bold uppercase tracking-wide text-indigo-800">
                      {SLOT_LABELS_ID[slot.slot] || slot.slot}
                    </div>
                    {slot.items.length === 0 ? (
                      <div className="text-xs text-slate-400">Tidak ada item pada waktu makan ini.</div>
                    ) : (
                      <ul className="space-y-2 text-xs">
                        {slot.items.map((it: any) => (
                          <li
                            key={it.id || `${slot.slot}-${it.food_id}`}
                            className="flex items-center justify-between gap-2 border-b border-slate-100 pb-1.5"
                          >
                            <div>
                              <div className="font-semibold text-slate-800">{it.food_name}</div>
                              <div className="text-[11px] text-slate-500">
                                {it.grams} g bersih • {formatDec1(it.energy_kcal)} kkal • {formatDec1(it.protein_g)} g
                                protein • {formatIdr(it.cost_idr)}
                              </div>
                            </div>
                            {!displayPlan.is_best_effort && it.id ? (
                              <div className="flex items-center gap-1">
                                <button
                                  type="button"
                                  aria-label={`Tambah 10g ${it.food_name}`}
                                  onClick={() => handleAdjustGrams(it.id, it.grams + 10)}
                                  className="rounded border border-slate-300 px-1.5 py-0.5 text-[11px] hover:bg-slate-100"
                                >
                                  +10g
                                </button>
                                <button
                                  type="button"
                                  aria-label={`Hapus ${it.food_name}`}
                                  onClick={() => handleRemoveItem(it.id)}
                                  className="rounded border border-rose-200 px-1.5 py-0.5 text-[11px] text-rose-700 hover:bg-rose-50"
                                >
                                  Hapus
                                </button>
                              </div>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {activeTab === "shopping" ? (
            <div className="overflow-x-auto">
              <p className="text-xs text-slate-600 mb-3">
                Daftar belanja dihitung per kemasan penuh (memperhitungkan persentase bagian dapat dimakan / edible)
                dan ditampilkan terpisah dari biaya harian proporsional.
              </p>
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500">
                    <th className="py-2 pr-3">Bahan Pangan</th>
                    <th className="py-2 pr-3">Total Bersih (7 hari)</th>
                    <th className="py-2 pr-3">Ukuran Kemasan</th>
                    <th className="py-2 pr-3">Jumlah Kemasan</th>
                    <th className="py-2 pr-3">Estimasi Biaya Beli</th>
                  </tr>
                </thead>
                <tbody>
                  {(displayPlan.shopping_list || []).map((sh: any) => (
                    <tr key={sh.food_id} className="border-b border-slate-100">
                      <td className="py-2 pr-3 font-medium">{sh.name}</td>
                      <td className="py-2 pr-3">{formatInt(sh.total_edible_g)} g</td>
                      <td className="py-2 pr-3">{formatInt(sh.package_g)} g</td>
                      <td className="py-2 pr-3 font-semibold">{sh.packages} pak</td>
                      <td className="py-2 pr-3 font-semibold">{formatIdr(sh.est_cost_idr)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {activeTab === "versions" ? (
            <ul className="space-y-2 text-xs">
              {plansHistory.map((p) => (
                <li
                  key={p.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-200 p-2.5"
                >
                  <div>
                    <strong>Versi {p.version}</strong> ({p.status}) — {p.result_status} • Mulai {p.start_date} • Budget{" "}
                    {formatIdr(p.budget_limit_idr)}
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      const d = await apiFetch(`/meal-plans/${p.id}`);
                      setInfeasibleDetails(null);
                      setPlan(d);
                      setActiveTab("menu");
                    }}
                    className="rounded border border-indigo-300 bg-indigo-50 px-2.5 py-1 text-indigo-800"
                  >
                    Buka Versi Ini
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-600">
          Belum ada rencana menu 7 hari. Klik tombol <strong>Generate Menu 7 Hari</strong> di atas untuk membuat rencana.
        </div>
      )}
    </div>
  );
}

