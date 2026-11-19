"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiClientError } from "@/lib/api";
import { ErrorBanner, ProposalCard, ProposalData } from "@/components/StatusWidgets";

interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  conversation_id: string;
  created_at: string;
}

interface AiStatus {
  available: boolean;
  provider: string;
  degraded_reason: string | null;
}

export default function ChatPage() {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [proposals, setProposals] = useState<ProposalData[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [busyProposalId, setBusyProposalId] = useState<string | null>(null);
  const [error, setError] = useState<{ msg: string; code?: string; reqId?: string } | null>(null);
  const [actionBanner, setActionBanner] = useState<string | null>(null);

  const loadChat = useCallback(async () => {
    try {
      const [st, history] = await Promise.all([
        apiFetch<AiStatus>("/ai/status"),
        apiFetch<{ items: ChatMessageItem[]; proposals: ProposalData[] }>("/ai/history"),
      ]);
      setStatus(st);
      setMessages(history.items);
      setProposals(history.proposals);
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
    if (!input.trim() || sending || !status?.available) return;
    setSending(true);
    setError(null);
    setActionBanner(null);
    try {
      await apiFetch("/ai/chat", {
        method: "POST",
        body: JSON.stringify({ message: input.trim(), conversation_id: messages.at(-1)?.conversation_id }),
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
      await apiFetch(
        `/ai/proposals/${proposal.id}/confirm`,
        {
          method: "POST",
          body: JSON.stringify({ base_version: proposal.base_version ?? 0 }),
        },
      );
      setActionBanner("Usulan berhasil dikonfirmasi dan diterapkan.");
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

  const needsCloudConsent = status?.degraded_reason === "ai_cloud_consent_required" || error?.code === "AI_CONSENT_REQUIRED";
  const aiDisabled = !status?.available || needsCloudConsent;

  return (
    <div className="space-y-6">
      <div className="route-intro flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-content">Asisten FitBudget AI</h1>
          <p className="text-sm text-muted">
            Penjelasan rencana makan & latihan serta usulan penyesuaian terstruktur. Semua angka dihitung oleh mesin
            deterministik.
          </p>
        </div>
        {status ? (
          <span
            data-testid="ai-provider-badge"
            className={`rounded-full px-3 py-1 text-xs font-semibold border ${
              status.available
                ? "border-positive-line bg-positive-soft text-positive"
                : "border-warning-line bg-warning-soft text-warning"
            }`}
          >
            Provider: {status.provider} {status.available ? "(Aktif)" : needsCloudConsent ? "(Menunggu persetujuan)" : "(Nonaktif)"}
          </span>
        ) : null}
      </div>

      {status && !status.available && !needsCloudConsent ? (
        <div
          role="alert"
          data-testid="ai-unavailable-banner"
          className="rounded-xl border border-warning-line bg-warning-soft p-4 text-sm text-warning space-y-2"
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

      {needsCloudConsent ? (
        <div
          role="alert"
          className="rounded-xl border border-accent-line bg-accent-soft p-4 text-sm text-accent-ink flex flex-wrap items-center justify-between gap-2"
        >
          <span>
            Untuk memakai Gemini, aktifkan Persetujuan AI Cloud di Pengaturan Privasi.
          </span>
          <Link
            href="/settings#ai-cloud-consent"
            className="rounded bg-accent-hover px-3 py-1.5 text-xs font-semibold text-white hover:bg-accent-hover"
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
          className="rounded-lg border border-positive-line bg-positive-soft p-3 text-sm text-positive"
        >
          ✓ {actionBanner}
        </div>
      ) : null}

      {/* Message list */}
      <div
        data-testid="chat-messages-list"
        className="rounded-xl border border-line bg-panel p-4 shadow-sm space-y-4 min-h-[320px] max-h-[540px] overflow-y-auto"
      >
        {messages.length === 0 ? (
          <div className="text-center py-12 text-sm text-muted space-y-2">
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
                  className="rounded-full border border-line-strong bg-inset px-3 py-1 text-xs text-secondary hover:bg-raised disabled:opacity-50"
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
                    ? "bg-positive-hover text-white"
                    : "border border-line bg-inset text-content"
                }`}
              >
                <div className="text-[11px] font-semibold opacity-75 mb-1">
                  {m.role === "user" ? "Anda" : "Asisten FitBudget"}
                </div>
                <div>{m.content}</div>
              </div>

            </div>
          ))
        )}
      </div>

      {proposals.length > 0 && (
        <section className="space-y-2" aria-label="Usulan perubahan">
          <h2 className="font-semibold">Usulan perubahan</h2>
          {proposals.map((proposal) => (
            <ProposalCard
              key={proposal.id}
              proposal={proposal}
              busy={busyProposalId !== null}
              onConfirm={handleConfirmProposal}
              onReject={handleRejectProposal}
            />
          ))}
        </section>
      )}

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
          className="min-w-0 flex-1 rounded-xl border border-line-strong bg-panel px-4 py-2.5 text-sm disabled:bg-raised"
        />
        <button
          type="submit"
          data-testid="chat-send-btn"
          disabled={aiDisabled || sending || !input.trim()}
          className="rounded-xl bg-positive-hover px-5 py-2.5 text-sm font-semibold text-white hover:bg-positive-hover disabled:opacity-50"
        >
          {sending ? "Mengirim..." : "Kirim"}
        </button>
      </form>
    </div>
  );
}

