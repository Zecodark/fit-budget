"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiClientError } from "@/lib/api";
import { ErrorBanner, ProposalCard, ProposalData } from "@/components/StatusWidgets";

interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  proposals: ProposalData[];
  created_at: string;
}

interface AiStatus {
  enabled: boolean;
  provider: string;
  model: string | null;
  cloud_consent_required: boolean;
  cloud_consent_granted: boolean;
}

export default function ChatPage() {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [busyProposalId, setBusyProposalId] = useState<string | null>(null);
  const [error, setError] = useState<{ msg: string; code?: string; reqId?: string } | null>(null);
  const [actionBanner, setActionBanner] = useState<string | null>(null);

  const loadChat = useCallback(async () => {
    try {
      const st = await apiFetch<AiStatus>("/ai/status");
      setStatus(st);
      const hist = await apiFetch<{ messages: ChatMessageItem[] }>("/ai/messages");
      setMessages(hist.messages || []);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, code: err.code, reqId: err.requestId });
      }
    }
  }, []);

  useEffect(() => {
    loadChat();
  }, [loadChat]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || sending) return;
    setSending(true);
    setError(null);
    setActionBanner(null);
    try {
      await apiFetch("/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message: input.trim() }),
      });
      setInput("");
      await loadChat();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, code: err.code, reqId: err.requestId });
      } else {
        setError({ msg: "Gagal mengirim pesan ke Asisten AI." });
      }
    } finally {
      setSending(false);
    }
  };

  const handleConfirmProposal = async (proposal: ProposalData) => {
    setBusyProposalId(proposal.id);
    setError(null);
    setActionBanner(null);
    try {
      const res = await apiFetch<{ status: string; new_plan_version?: number }>(
        `/ai/proposals/${proposal.id}/confirm`,
        {
          method: "POST",
          body: JSON.stringify({ expected_base_version: proposal.base_version }),
        },
      );
      setActionBanner(
        `Usulan berhasil dikonfirmasi dan diterapkan (Versi Rencana Baru: v${res.new_plan_version ?? "-"}).`,
      );
      await loadChat();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, code: err.code, reqId: err.requestId });
      }
    } finally {
      setBusyProposalId(null);
    }
  };

  const handleRejectProposal = async (proposal: ProposalData) => {
    setBusyProposalId(proposal.id);
    setError(null);
    try {
      await apiFetch(`/ai/proposals/${proposal.id}/reject`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setActionBanner("Usulan perubahan ditolak.");
      await loadChat();
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, code: err.code, reqId: err.requestId });
      }
    } finally {
      setBusyProposalId(null);
    }
  };

  const aiDisabled = status ? !status.enabled || error?.code === "AI_UNAVAILABLE" : false;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Asisten FitBudget AI</h1>
          <p className="text-sm text-slate-600">
            Penjelasan rencana makan & latihan serta usulan penyesuaian terstruktur. Semua angka dihitung oleh mesin
            deterministik.
          </p>
        </div>
        {status ? (
          <span
            data-testid="ai-provider-badge"
            className={`rounded-full px-3 py-1 text-xs font-semibold border ${
              status.enabled
                ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                : "border-amber-300 bg-amber-50 text-amber-900"
            }`}
          >
            Provider: {status.provider} {status.enabled ? "(Aktif)" : "(Nonaktif)"}
          </span>
        ) : null}
      </div>

      {aiDisabled ? (
        <div
          role="alert"
          data-testid="ai-unavailable-banner"
          className="rounded-xl border border-amber-400 bg-amber-50 p-4 text-sm text-amber-950 space-y-2"
        >
          <div className="font-bold">⚠ Asisten AI Sedang Tidak Aktif (Mode Non-AI)</div>
          <p>
            Seluruh fitur utama FitBudget AI tetap berfungsi penuh tanpa AI. Gunakan tombol langsung di halaman{" "}
            <Link href="/meal-plan" className="font-semibold underline">
              Rencana Makan
            </Link>
            ,{" "}
            <Link href="/workout" className="font-semibold underline">
              Jadwal Latihan
            </Link>
            , atau{" "}
            <Link href="/tracker" className="font-semibold underline">
              Tracker Harian
            </Link>
            .
          </p>
        </div>
      ) : null}

      {status?.cloud_consent_required && !status?.cloud_consent_granted ? (
        <div
          role="alert"
          className="rounded-xl border border-indigo-300 bg-indigo-50 p-4 text-sm text-indigo-950 flex flex-wrap items-center justify-between gap-2"
        >
          <span>
            Penyedia AI cloud memerlukan persetujuan pengiriman konteks anonim. Aktifkan di Pengaturan Privasi.
          </span>
          <Link
            href="/settings"
            className="rounded bg-indigo-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-800"
          >
            Buka Pengaturan
          </Link>
        </div>
      ) : null}

      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}
      {actionBanner ? (
        <div
          role="status"
          data-testid="chat-action-banner"
          className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-950"
        >
          ✓ {actionBanner}
        </div>
      ) : null}

      {/* Message list */}
      <div
        data-testid="chat-messages-list"
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-4 min-h-[320px] max-h-[540px] overflow-y-auto"
      >
        {messages.length === 0 ? (
          <div className="text-center py-12 text-sm text-slate-500 space-y-2">
            <p>Belum ada percakapan. Contoh pertanyaan yang dapat Anda ajukan:</p>
            <div className="flex flex-wrap justify-center gap-2 pt-2">
              {[
                "Jelaskan rencana makan dan target gizi saya saat ini.",
                "Saya alergi telur, tolong ganti telur dari rencana makan saya.",
                "Ubah budget harian saya menjadi Rp 45.000.",
              ].map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  disabled={aiDisabled}
                  onClick={() => setInput(q)}
                  className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={`flex flex-col space-y-2 ${m.role === "user" ? "items-end" : "items-start"}`}
            >
              <div
                className={`max-w-2xl rounded-xl px-4 py-3 text-sm whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-emerald-700 text-white"
                    : "border border-slate-200 bg-slate-50 text-slate-900"
                }`}
              >
                <div className="text-[11px] font-semibold opacity-75 mb-1">
                  {m.role === "user" ? "Anda" : "Asisten FitBudget"}
                </div>
                <div>{m.content}</div>
              </div>
              {m.proposals && m.proposals.length > 0 ? (
                <div className="w-full max-w-xl space-y-2">
                  {m.proposals.map((p) => (
                    <ProposalCard
                      key={p.id}
                      proposal={p}
                      busy={busyProposalId === p.id}
                      onConfirm={handleConfirmProposal}
                      onReject={handleRejectProposal}
                    />
                  ))}
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>

      {/* Chat input form */}
      <form onSubmit={handleSend} className="flex gap-2">
        <label htmlFor="chat-input" className="sr-only">
          Pesan untuk Asisten AI
        </label>
        <input
          id="chat-input"
          data-testid="chat-input"
          type="text"
          disabled={aiDisabled || sending}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            aiDisabled
              ? "Asisten AI sedang tidak aktif..."
              : "Tanyakan tentang rencana makan/latihan atau minta perubahan..."
          }
          className="flex-1 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm disabled:bg-slate-100"
        />
        <button
          type="submit"
          data-testid="chat-send-btn"
          disabled={aiDisabled || sending || !input.trim()}
          className="rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-800 disabled:opacity-50"
        >
          {sending ? "Mengirim..." : "Kirim"}
        </button>
      </form>
    </div>
  );
}

