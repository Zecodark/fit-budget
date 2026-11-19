"use client";

import { Apple, Check, Moon, Pencil, Plus, Sunrise, Sun, Trash2, Utensils } from "lucide-react";
import { FeatureBanner } from "@/components/FeatureBanner";

import React, { useEffect, useRef, useState } from "react";
import {
  ConsultBlockBanner,
  ErrorBanner,
  MealPlanStatusPanel,
  StatusBadge,
} from "@/components/StatusWidgets";
import { ApiClientError, apiFetch } from "@/lib/api";
import { SLOT_LABELS_ID, currentMondayIso, formatDec1, formatIdr, formatInt } from "@/lib/errorMessages";

const mealIcons = { breakfast: Sunrise, lunch: Sun, dinner: Moon, snack: Apple };
const weekday = new Intl.DateTimeFormat("id-ID", { weekday: "short", timeZone: "UTC" });
const shortDate = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "short", timeZone: "UTC" });

export default function MealPlanPage() {
  const [startDate, setStartDate] = useState(currentMondayIso());
  const [budgetIdr, setBudgetIdr] = useState<number>(45000);
  const [plan, setPlan] = useState<any | null>(null);
  const [plansHistory, setPlansHistory] = useState<any[]>([]);
  const [infeasibleDetails, setInfeasibleDetails] = useState<any | null>(null);
  const [editingMenu, setEditingMenu] = useState(false);
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
    <div className="meal-page space-y-5">
      <FeatureBanner kind="meals" title="Menu 7 hari">Susun porsi bahan pangan lokal sesuai target nutrisi dan anggaran harian Anda.</FeatureBanner>
      <div className="rounded-xl border border-line bg-panel p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold">Atur rencana</h2>
          {plan ? <StatusBadge status={plan.result_status} /> : null}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="mp-start" className="block text-xs font-semibold text-secondary mb-1">
              Tanggal Mulai
            </label>
            <input
              id="mp-start"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="rounded border border-line-strong px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label htmlFor="mp-budget" className="block text-xs font-semibold text-secondary mb-1">
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
              className="rounded border border-line-strong px-3 py-1.5 text-sm w-36"
            />
          </div>
          <button
            type="button"
            disabled={generating || consultBlocked}
            onClick={handleGenerate}
            data-testid="generate-meal-btn"
            className="rounded bg-accent-action px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {generating ? "Menyusun Menu..." : "Generate Menu 7 Hari"}
          </button>
          {generating && abortRef.current ? (
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="rounded border border-danger-line bg-danger-soft px-3 py-2 text-xs font-semibold text-danger"
            >
              Batal
            </button>
          ) : null}
          {plan && plan.status === "draft" && plan.result_status !== "INFEASIBLE" ? (
            <button
              type="button"
              onClick={handleConfirm}
              data-testid="confirm-meal-btn"
              className="rounded bg-positive-action px-4 py-2 text-xs font-semibold text-white hover:bg-positive-hover"
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
          <div className="rounded-lg border border-danger-line bg-danger-soft/70 px-4 py-2 text-xs font-semibold text-danger">
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
        <div className="rounded-xl border border-line bg-panel p-6 text-sm text-muted">
          Memuat rencana menu...
        </div>
      ) : displayPlan ? (
        <div className="menu-workspace">
          <nav className="menu-views" aria-label="Tampilan rencana">
            {([
              ["menu", "Menu harian"], ["shopping", "Daftar belanja"], ["versions", "Riwayat versi"],
            ] as const).map(([key, label]) => (
              <button key={key} type="button" aria-pressed={activeTab === key}
                onClick={() => { setActiveTab(key); setEditingMenu(false); }}>{label}</button>
            ))}
          </nav>
          <div className="weekly-cost">
            <div><small>Biaya menu 7 hari</small><strong>{formatIdr(displayPlan.week_totals?.cost_idr)}</strong></div>
            <span>Rata-rata per hari <b>{formatDec1(displayPlan.week_totals?.avg_energy_kcal)} kkal</b> · <b>{formatDec1(displayPlan.week_totals?.avg_protein_g)} g protein</b></span>
          </div>
          {activeTab === "menu" && activeDay ? (
            <div className="daily-menu">
              <div className="menu-calendar" aria-label="Pilih hari">
                {displayPlan.days.map((d: any, idx: number) => (
                  <button key={d.date} type="button" aria-pressed={idx === selectedDayIdx}
                    title={d.day_status} onClick={() => { setSelectedDayIdx(idx); setEditingMenu(false); }}>
                    <small>{weekday.format(new Date(d.date))}</small><strong>{shortDate.format(new Date(d.date))}</strong>
                  </button>
                ))}
              </div>
              <div className="menu-stats">
                {[
                  ["Biaya", formatIdr(activeDay.totals.cost_idr), "Anggaran " + formatIdr(displayPlan.budget_limit_idr)],
                  ["Energi", formatDec1(activeDay.totals.energy_kcal) + " kkal", "Target " + formatInt(displayPlan.targets?.energy_kcal) + " kkal"],
                  ["Protein", formatDec1(activeDay.totals.protein_g) + " g", "Target " + formatInt(displayPlan.targets?.protein_g) + " g"],
                  ["Sayur", formatInt(activeDay.totals.vegetable_g) + " g", "Porsi harian"],
                ].map(([label, value, detail]) => <div key={label}><small>{label}</small><strong>{value}</strong><span>{detail}</span></div>)}
              </div>
              <div className="meal-section-title">
                <div><h2>Susunan menu</h2><small>{shortDate.format(new Date(activeDay.date))} · {activeDay.day_status}</small></div>
                {!displayPlan.is_best_effort && activeDay.slots.some((slot: any) => slot.items.some((item: any) => item.id)) && (
                  <button type="button" className="action-secondary" aria-pressed={editingMenu} onClick={() => setEditingMenu(!editingMenu)}>
                    {editingMenu ? <Check size={15} /> : <Pencil size={15} />}{editingMenu ? "Selesai" : "Edit porsi"}
                  </button>
                )}
              </div>
              <div className="meal-groups">
                {activeDay.slots.map((slot: any) => {
                  const Icon = mealIcons[slot.slot as keyof typeof mealIcons] ?? Utensils;
                  return <section key={slot.slot} className="meal-group">
                    <header><span className="slot-icon"><Icon size={19} /></span>
                      <h3>{SLOT_LABELS_ID[slot.slot] || slot.slot}</h3>
                      <small>{slot.items.length} bahan</small>
                    </header>
                    {slot.items.length === 0 ? <p className="meal-empty">Belum ada bahan.</p> : (
                      <ul>{slot.items.map((it: any) => (
                        <li key={it.id || `${slot.slot}-${it.food_id}`}>
                          <div className="ingredient"><strong>{it.food_name}</strong><span>{formatDec1(it.energy_kcal)} kkal · {formatDec1(it.protein_g)} g protein</span></div>
                          <div className="ingredient-portion"><strong>{it.grams} g</strong><span>{formatIdr(it.cost_idr)}</span></div>
                          {editingMenu && !displayPlan.is_best_effort && it.id && <div className="ingredient-actions">
                            <button type="button" aria-label={`Tambah 10 g ${it.food_name}`} onClick={() => handleAdjustGrams(it.id, it.grams + 10)}><Plus size={14} />10 g</button>
                            <button type="button" aria-label={`Hapus ${it.food_name}`} onClick={() => handleRemoveItem(it.id)}><Trash2 size={15} />Hapus</button>
                          </div>}
                        </li>
                      ))}</ul>
                    )}
                  </section>;
                })}
              </div>
            </div>
          ) : null}

          {activeTab === "shopping" ? (
            <div className="overflow-x-auto">
              <p className="text-xs text-muted mb-3">
                Daftar belanja dihitung per kemasan penuh (memperhitungkan persentase bagian dapat dimakan / edible)
                dan ditampilkan terpisah dari biaya harian proporsional.
              </p>
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-line text-muted">
                    <th className="py-2 pr-3">Bahan Pangan</th>
                    <th className="py-2 pr-3">Total Bersih (7 hari)</th>
                    <th className="py-2 pr-3">Ukuran Kemasan</th>
                    <th className="py-2 pr-3">Jumlah Kemasan</th>
                    <th className="py-2 pr-3">Estimasi Biaya Beli</th>
                  </tr>
                </thead>
                <tbody>
                  {(displayPlan.shopping_list || []).map((sh: any) => (
                    <tr key={sh.food_id} className="border-b border-line">
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
                  className="flex flex-wrap items-center justify-between gap-2 rounded border border-line p-2.5"
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
                    className="rounded border border-accent-line bg-accent-soft px-2.5 py-1 text-accent-ink"
                  >
                    Buka Versi Ini
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <div className="rounded-xl border border-line bg-panel p-6 text-sm text-muted">
          Belum ada rencana menu 7 hari. Klik tombol <strong>Generate Menu 7 Hari</strong> di atas untuk membuat rencana.
        </div>
      )}
    </div>
  );
}

