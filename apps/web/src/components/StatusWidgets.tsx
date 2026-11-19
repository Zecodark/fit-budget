/**
 * Reusable status & guardrail UI components (PRD §7.2, §7.3).
 * Never uses the word "terpenuhi" for PARTIAL or INFEASIBLE.
 */

import React from "react";
import { formatDec1, formatIdr } from "@/lib/errorMessages";

export interface UnmetConstraint {
  code: string;
  day: string;
  required: number;
  actual: number;
  unit: string;
}

export function StatusBadge({ status }: { status: "FEASIBLE" | "PARTIAL" | "INFEASIBLE" | string }) {
  if (status === "FEASIBLE") {
    return (
      <span
        data-testid="status-badge"
        className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-900 border border-emerald-300"
      >
        <span aria-hidden="true">✓</span> FEASIBLE (Sesuai Target & Budget)
      </span>
    );
  }
  if (status === "PARTIAL") {
    return (
      <span
        data-testid="status-badge"
        className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-900 border border-amber-300"
      >
        <span aria-hidden="true">⚠</span> PARTIAL (Sebagian Target Belum Tercapai)
      </span>
    );
  }
  return (
    <span
      data-testid="status-badge"
      className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-900 border border-rose-300"
    >
      <span aria-hidden="true">✕</span> INFEASIBLE (Belum Memenuhi Target)
    </span>
  );
}

const UNMET_LABELS: Record<string, string> = {
  BUDGET_EXCEEDED: "Biaya melebihi budget harian",
  ENERGY_BELOW_TARGET: "Energi di bawah rentang target",
  ENERGY_ABOVE_TARGET: "Energi di atas rentang target",
  PROTEIN_BELOW_TARGET: "Protein di bawah target",
  PROTEIN_ABOVE_LIMIT: "Protein melebihi batas atas 130%",
  VEGETABLE_BELOW_MIN: "Porsi sayur di bawah minimum 150 g",
  VARIETY_BELOW_MIN: "Variasi bahan pangan kurang dari 6 jenis",
  SLOT_SHARE_VIOLATION: "Distribusi energi antar waktu makan di luar rentang",
  MEAL_COMPOSITION_INVALID: "Makan siang/malam belum memiliki karbohidrat + protein",
  FOOD_REPEAT_LIMIT_RELAXED: "Batas pengulangan mingguan dilonggarkan",
};

export function MealPlanStatusPanel({
  resultStatus,
  unmetConstraints,
  minimumBudgetRequiredIdr,
  suggestions,
}: {
  resultStatus: "FEASIBLE" | "PARTIAL" | "INFEASIBLE" | string;
  unmetConstraints: UnmetConstraint[];
  minimumBudgetRequiredIdr?: number | null;
  suggestions?: string[];
}) {
  if (resultStatus === "FEASIBLE") {
    return (
      <div
        role="status"
        data-testid="plan-status-panel"
        className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-950"
      >
        <div className="font-semibold">✓ Rencana memenuhi seluruh kendala budget, energi, protein, dan variasi.</div>
      </div>
    );
  }

  if (resultStatus === "PARTIAL") {
    return (
      <div
        role="alert"
        data-testid="plan-status-panel"
        className="rounded-lg border border-amber-400 bg-amber-50 p-4 text-sm text-amber-950 space-y-2"
      >
        <div className="font-semibold">
          ⚠ Status PARTIAL — Sebagian target gizi atau komposisi belum tercapai dalam batas budget ini:
        </div>
        <ul className="list-disc pl-5 space-y-1">
          {unmetConstraints.map((u, idx) => (
            <li key={`${u.day}-${u.code}-${idx}`}>
              <span className="font-medium">{u.day}</span> — {UNMET_LABELS[u.code] || u.code} (target:{" "}
              {u.unit === "idr" ? formatIdr(u.required) : `${formatDec1(u.required)} ${u.unit}`}, aktual:{" "}
              {u.unit === "idr" ? formatIdr(u.actual) : `${formatDec1(u.actual)} ${u.unit}`})
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div
      role="alert"
      data-testid="plan-status-panel"
      className="rounded-lg border border-rose-400 bg-rose-50 p-4 text-sm text-rose-950 space-y-3"
    >
      <div className="font-semibold">
        ✕ Status INFEASIBLE — Rencana belum memenuhi target gizi pada batas budget saat ini.
      </div>
      {minimumBudgetRequiredIdr ? (
        <p>
          Estimasi budget harian minimum yang dibutuhkan:{" "}
          <strong data-testid="min-budget-required">{formatIdr(minimumBudgetRequiredIdr)}</strong> / hari.
        </p>
      ) : null}
      {unmetConstraints.length > 0 ? (
        <ul className="list-disc pl-5 space-y-1">
          {unmetConstraints.slice(0, 8).map((u, idx) => (
            <li key={`${u.day}-${u.code}-${idx}`}>
              <span className="font-medium">{u.day}</span> — {UNMET_LABELS[u.code] || u.code} (target:{" "}
              {u.unit === "idr" ? formatIdr(u.required) : `${formatDec1(u.required)} ${u.unit}`}, aktual:{" "}
              {u.unit === "idr" ? formatIdr(u.actual) : `${formatDec1(u.actual)} ${u.unit}`})
            </li>
          ))}
        </ul>
      ) : null}
      {suggestions && suggestions.length > 0 ? (
        <div>
          <div className="font-medium">Saran penyesuaian:</div>
          <ul className="list-disc pl-5 space-y-1">
            {suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function ErrorBanner({
  message,
  requestId,
  onRetry,
}: {
  message: string;
  requestId?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-rose-300 bg-rose-50 p-4 text-sm text-rose-900 flex flex-wrap items-center justify-between gap-2"
    >
      <div>
        <span className="font-semibold">✕ Kesalahan: </span>
        <span>{message}</span>
        {requestId ? <span className="ml-2 text-xs text-rose-700">(ID: {requestId})</span> : null}
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded bg-rose-700 px-3 py-1 text-xs font-medium text-white hover:bg-rose-800"
        >
          Coba Lagi
        </button>
      ) : null}
    </div>
  );
}

export function ConsultBlockBanner({ message }: { message?: string }) {
  return (
    <div
      role="alert"
      data-testid="consult-block-banner"
      className="rounded-lg border-2 border-amber-500 bg-amber-50 p-5 text-sm text-amber-950 space-y-2"
    >
      <div className="text-base font-bold">⚠ Konsultasi Tenaga Kesehatan Profesional Diperlukan</div>
      <p>
        {message ||
          "Berdasarkan skrining kesehatan atau indeks massa tubuh Anda, FitBudget AI tidak membuat rencana diet maupun latihan otomatis. Silakan berkonsultasi dengan dokter atau ahli gizi terdaftar. Anda tetap dapat melihat kalkulator estimasi dan pencatatan harian."}
      </p>
    </div>
  );
}

export interface ProposalData {
  id: string;
  type: "change_budget" | "exclude_food" | "reschedule_workout" | string;
  params: Record<string, any>;
  preview: Record<string, any>;
  base_plan_type?: string | null;
  base_version?: number | null;
  status: string;
  expires_at: string;
}

export function ProposalCard({
  proposal,
  onConfirm,
  onReject,
  busy = false,
}: {
  proposal: ProposalData;
  onConfirm: (proposal: ProposalData) => void;
  onReject: (proposal: ProposalData) => void;
  busy?: boolean;
}) {
  const typeLabel =
    proposal.type === "change_budget"
      ? "Ubah Budget Harian"
      : proposal.type === "exclude_food"
        ? "Kecualikan Bahan Pangan"
        : "Jadwalkan Ulang Sesi Latihan";

  return (
    <div
      data-testid="proposal-card"
      className="rounded-lg border border-indigo-300 bg-indigo-50/70 p-4 text-sm text-slate-900 space-y-2"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-indigo-950">Usulan Perubahan: {typeLabel}</span>
        <span className="rounded bg-indigo-200 px-2 py-0.5 text-xs font-medium text-indigo-900">
          Status: {proposal.status}
        </span>
      </div>
      <div className="text-xs text-slate-700 space-y-1">
        {proposal.type === "change_budget" ? (
          <p>
            Budget baru: <strong>{formatIdr(proposal.params.daily_budget_idr)}</strong> — Pratinjau status:{" "}
            <strong>{proposal.preview.result_status}</strong> (estimasi biaya mingguan{" "}
            {formatIdr(proposal.preview.week_cost_idr)})
          </p>
        ) : null}
        {proposal.type === "exclude_food" ? (
          <p>
            Kecualikan: <strong>{proposal.params.food_name}</strong> — Pratinjau status:{" "}
            <strong>{proposal.preview.result_status}</strong> (estimasi biaya mingguan{" "}
            {formatIdr(proposal.preview.week_cost_idr)})
          </p>
        ) : null}
        {proposal.type === "reschedule_workout" ? (
          <p>
            Pindahkan sesi dari <strong>{proposal.params.from_date}</strong> ke{" "}
            <strong>{proposal.params.to_date}</strong>
            {proposal.preview.recovery_warning ? " (Peringatan: jeda pemulihan berdekatan)" : ""}
          </p>
        ) : null}
      </div>
      {proposal.status === "pending" ? (
        <div className="flex gap-2 pt-1">
          <button
            type="button"
            disabled={busy}
            onClick={() => onConfirm(proposal)}
            data-testid="proposal-confirm-btn"
            className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            Konfirmasi & Terapkan
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onReject(proposal)}
            data-testid="proposal-reject-btn"
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            Tolak
          </button>
        </div>
      ) : null}
    </div>
  );
}

