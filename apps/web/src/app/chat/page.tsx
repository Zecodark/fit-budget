"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiClientError } from "@/lib/api";
import { ErrorBanner, ProposalCard, ProposalData } from "@/components/StatusWidgets";

interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: string | null;
  explanation_source?: string;
  conversation_id: string;
  created_at: string;
}

interface ConversationSummary {
  conversation_id: string;
  title: string;
  message_count: number;
  last_message_at: string;
  last_preview: string;
}

interface AiStatus {
  available: boolean;
  provider: string;
  degraded_reason: string | null;
}

const QUICK_PROMPTS = [
  "Halo, bisa bantu apa saja?",
  "Jelaskan rencana makan dan target nutrisi saya saat ini.",
  "Jelaskan jadwal latihan Gym / Workout saya minggu ini.",
  "Bagaimana progres makan, latihan, dan berat badan saya 7 hari terakhir?",
  "Saya alergi telur, tolong ganti telur dari rencana makan saya.",
  "Ubah budget harian saya menjadi Rp 45.000.",
];

export default function ChatPage() {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [isNewSession, setIsNewSession] = useState(false);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [proposals, setProposals] = useState<ProposalData[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [busyProposalId, setBusyProposalId] = useState<string | null>(null);
  const [error, setError] = useState<{ msg: string; code?: string; reqId?: string } | null>(null);
  const [actionBanner, setActionBanner] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  const loadSessionHistory = useCallback(async (convId: string | null) => {
    if (!convId) {
      setMessages([]);
      setProposals([]);
      return;
    }
    const history = await apiFetch<{ items: ChatMessageItem[]; proposals: ProposalData[] }>(
      `/ai/history?conversation_id=${encodeURIComponent(convId)}`,
    );
    setMessages(history.items || []);
    setProposals(history.proposals || []);
  }, []);

  const loadChat = useCallback(
    async (preferredConvId?: string | null, forceNew = false) => {
      try {
        const [st, convRes] = await Promise.all([
          apiFetch<AiStatus>("/ai/status"),
          apiFetch<{ items: ConversationSummary[] }>("/ai/conversations").catch(() => ({ items: [] })),
        ]);
        setStatus(st);
        const list = convRes.items || [];
        setConversations(list);

        if (forceNew) {
          setIsNewSession(true);
          setActiveConvId(null);
          setMessages([]);
          setProposals([]);
          return;
        }

        const targetId =
          preferredConvId !== undefined
            ? preferredConvId
            : activeConvId && list.some((c) => c.conversation_id === activeConvId)
              ? activeConvId
              : list[0]?.conversation_id || null;

        setIsNewSession(targetId === null);
        setActiveConvId(targetId);
        await loadSessionHistory(targetId);
      } catch (err) {
        if (err instanceof ApiClientError) {
          setError({ msg: err.message, code: err.code, reqId: err.requestId });
        }
      }
    },
    [activeConvId, loadSessionHistory],
  );

  useEffect(() => {
    loadChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const handleSelectSession = async (convId: string) => {
    setError(null);
    setActionBanner(null);
    setIsNewSession(false);
    setActiveConvId(convId);
    try {
      await loadSessionHistory(convId);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, code: err.code, reqId: err.requestId });
      }
    }
  };

  const handleNewSession = () => {
    setError(null);
    setActionBanner(null);
    setIsNewSession(true);
    setActiveConvId(null);
    setMessages([]);
    setProposals([]);
  };

  const handleDeleteSession = async (convId: string) => {
    setError(null);
    try {
      await apiFetch(`/ai/conversations/${encodeURIComponent(convId)}`, { method: "DELETE" });
      const remaining = conversations.filter((c) => c.conversation_id !== convId);
      setConversations(remaining);
      if (activeConvId === convId) {
        const nextId = remaining[0]?.conversation_id || null;
        setActiveConvId(nextId);
        setIsNewSession(nextId === null);
        await loadSessionHistory(nextId);
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, code: err.code, reqId: err.requestId });
      }
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || sending || !status?.available) return;
    setSending(true);
    setError(null);
    setActionBanner(null);
    try {
      const payload: Record<string, any> = { message: input.trim() };
      if (!isNewSession && activeConvId) {
        payload.conversation_id = activeConvId;
      }
      const res = await apiFetch<{ conversation_id: string }>("/ai/chat", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setInput("");
      setIsNewSession(false);
      await loadChat(res.conversation_id, false);
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
      await apiFetch(`/ai/proposals/${proposal.id}/confirm`, {
        method: "POST",
        body: JSON.stringify({ base_version: proposal.base_version ?? 0 }),
      });
      setActionBanner("Usulan berhasil dikonfirmasi dan diterapkan.");
      await loadChat(activeConvId, false);
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
      await loadChat(activeConvId, false);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, code: err.code, reqId: err.requestId });
      }
    } finally {
      setBusyProposalId(null);
    }
  };

  const needsCloudConsent =
    status?.degraded_reason === "ai_cloud_consent_required" || error?.code === "AI_CONSENT_REQUIRED";
  const aiDisabled = !status?.available || needsCloudConsent;

  return (
    <div className="space-y-6">
      <div className="route-intro flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-content">Asisten FitBudget AI</h1>
          <p className="text-sm text-muted">
            Memahami seluruh segmen akun Anda: target nutrisi, rencana makan, jadwal Gym/Workout, dan catatan progres
            harian pada setiap sesi percakapan.
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
            Provider: {status.provider}{" "}
            {status.available ? "(Aktif)" : needsCloudConsent ? "(Menunggu persetujuan)" : "(Nonaktif)"}
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
          <span>Untuk memakai Gemini, aktifkan Persetujuan AI Cloud di Pengaturan Privasi.</span>
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

      {/* Session manager bar */}
      <div className="rounded-xl border border-line bg-panel p-3.5 shadow-sm space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-semibold text-secondary">
            Sesi Percakapan Anda ({conversations.length})
          </span>
          <button
            type="button"
            onClick={handleNewSession}
            data-testid="new-chat-session-btn"
            className="rounded-lg border border-accent-line bg-accent-soft px-3 py-1.5 text-xs font-semibold text-accent-ink hover:opacity-90"
          >
            + Sesi Baru
          </button>
        </div>
        {conversations.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {conversations.map((c) => {
              const selected = !isNewSession && activeConvId === c.conversation_id;
              return (
                <div
                  key={c.conversation_id}
                  className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs ${
                    selected
                      ? "border-accent-line bg-accent-soft text-accent-ink font-semibold"
                      : "border-line bg-inset text-secondary hover:bg-raised"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => handleSelectSession(c.conversation_id)}
                    className="max-w-[200px] truncate text-left"
                    title={c.title}
                  >
                    {c.title} ({c.message_count})
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteSession(c.conversation_id)}
                    aria-label={`Hapus sesi ${c.title}`}
                    className="text-muted hover:text-danger text-[11px] px-1"
                  >
                    ×
                  </button>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>

      {/* Message list */}
      <div
        data-testid="chat-messages-list"
        className="rounded-xl border border-line bg-panel p-4 shadow-sm space-y-4 min-h-[320px] max-h-[540px] overflow-y-auto"
      >
        {messages.length === 0 ? (
          <div className="text-center py-10 text-sm text-muted space-y-3">
            <p className="font-medium text-secondary">
              {isNewSession ? "Sesi percakapan baru siap dimulai." : "Belum ada percakapan."} Pilih contoh pertanyaan
              atau ketik pesan Anda:
            </p>
            <div className="flex flex-wrap justify-center gap-2 pt-1">
              {QUICK_PROMPTS.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  disabled={aiDisabled}
                  onClick={() => setInput(q)}
                  className="rounded-full border border-line-strong bg-inset px-3 py-1.5 text-xs text-secondary hover:bg-raised disabled:opacity-50"
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
              className={`flex flex-col space-y-1.5 ${m.role === "user" ? "items-end" : "items-start"}`}
            >
              <div
                className={`max-w-2xl rounded-xl px-4 py-3 text-sm whitespace-pre-wrap ${
                  m.role === "user"
                    ? "bg-positive-hover text-white"
                    : "border border-line bg-inset text-content"
                }`}
              >
                <div className="flex items-center justify-between gap-3 text-[11px] font-semibold opacity-75 mb-1">
                  <span>{m.role === "user" ? "Anda" : "Asisten FitBudget"}</span>
                  {m.role === "assistant" && m.explanation_source === "template" ? (
                    <span className="rounded bg-raised px-1.5 py-0.5 text-[10px] font-normal">Ringkasan Sistem</span>
                  ) : null}
                </div>
                <div>{m.content}</div>
              </div>
            </div>
          ))
        )}
        <div ref={endRef} />
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
              : "Tanyakan tentang nutrisi, menu makan, latihan Gym/Workout, progres, atau minta perubahan..."
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
