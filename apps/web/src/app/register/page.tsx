"use client";

import { MotionScene } from "@/components/MotionScene";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { ErrorBanner } from "@/components/StatusWidgets";
import { ApiClientError, apiFetch } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!/^(?=.*[A-Za-z])(?=.*\d).{10,}$/.test(password)) {
      setError({ msg: "Kata sandi minimal 10 karakter dan harus mengandung huruf serta angka." });
      return;
    }
    setLoading(true);
    try {
      await apiFetch("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.push("/onboarding");
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      } else {
        setError({ msg: "Gagal mendaftar. Coba lagi." });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-art" aria-hidden="true"><MotionScene /><strong>Mulai rencana Anda.</strong></div>
      <div className="panel auth-form space-y-5">
        <h1 className="text-xl font-bold text-content">Daftar Akun Baru</h1>
        <p className="text-xs text-muted">
          Untuk orang dewasa sehat berusia ≥ 18 tahun. Kata sandi minimal 10 karakter (huruf &amp; angka).
        </p>
        {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="reg-email" className="block text-xs font-semibold text-secondary mb-1">
              Email
            </label>
            <input
              id="reg-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
              placeholder="raka@contoh.com"
            />
          </div>
          <div>
            <label htmlFor="reg-password" className="block text-xs font-semibold text-secondary mb-1">
              Kata Sandi (≥ 10 karakter, huruf &amp; angka)
            </label>
            <input
              id="reg-password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-accent-action px-4 py-2.5 text-sm font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {loading ? "Mendaftarkan..." : "Daftar & Lanjut ke Onboarding"}
          </button>
        </form>
        <p className="text-xs text-muted text-center">
          Sudah punya akun?{" "}
          <Link href="/login" className="font-semibold text-accent-ink hover:underline">
            Masuk
          </Link>
        </p>
      </div>
    </div>
  );
}

