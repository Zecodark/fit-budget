"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { ErrorBanner } from "@/components/StatusWidgets";
import { ApiClientError, apiFetch } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.includes("@") || password.length < 1) {
      setError({ msg: "Masukkan email dan kata sandi yang valid." });
      return;
    }
    setLoading(true);
    try {
      await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      const me = await apiFetch("/auth/me");
      if (me.consent_required || !me.profile_complete) {
        router.push("/onboarding");
      } else {
        router.push("/dashboard");
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      } else {
        setError({ msg: "Gagal masuk. Periksa koneksi Anda." });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md py-8">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <h1 className="text-xl font-bold text-slate-900">Masuk ke FitBudget AI</h1>
        {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="block text-xs font-semibold text-slate-700 mb-1">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="nama@contoh.com"
            />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-xs font-semibold text-slate-700 mb-1">
              Kata Sandi
            </label>
            <input
              id="login-password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {loading ? "Memproses..." : "Masuk"}
          </button>
        </form>
        <p className="text-xs text-slate-600 text-center">
          Belum punya akun?{" "}
          <Link href="/register" className="font-semibold text-indigo-600 hover:underline">
            Daftar di sini
          </Link>
        </p>
      </div>
    </div>
  );
}

