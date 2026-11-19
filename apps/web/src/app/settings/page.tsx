"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, ApiClientError } from "@/lib/api";
import { ErrorBanner } from "@/components/StatusWidgets";

export default function SettingsPage() {
  const router = useRouter();
  const [cloudConsent, setCloudConsent] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [deletePassword, setDeletePassword] = useState("");
  const [banner, setBanner] = useState<string | null>(null);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);

  const loadSettings = useCallback(async () => {
    try {
      const st = await apiFetch<{ cloud_consent_granted: boolean }>("/ai/status");
      setCloudConsent(Boolean(st.cloud_consent_granted));
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleToggleCloudConsent = async (granted: boolean) => {
    setError(null);
    setBanner(null);
    try {
      await apiFetch("/consent", {
        method: "POST",
        body: JSON.stringify({ consent_type: "ai_cloud", granted }),
      });
      setCloudConsent(granted);
      setBanner(
        granted
          ? "Persetujuan pemrosesan AI cloud diaktifkan."
          : "Persetujuan pemrosesan AI cloud dicabut.",
      );
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  const handleExportData = async () => {
    setError(null);
    try {
      const data = await apiFetch<Record<string, any>>("/account/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fitbudget-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setBanner("Data akun berhasil diekspor (JSON).");
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBanner(null);
    try {
      await apiFetch("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setBanner("Kata sandi berhasil diperbarui.");
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  const handleDeleteAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await apiFetch("/account", {
        method: "DELETE",
        body: JSON.stringify({ password: deletePassword }),
      });
      router.push("/login");
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      }
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div className="route-intro">
        <h1 className="text-2xl font-bold text-content">Akun & privasi</h1>
        <p className="text-sm text-muted">
          Kelola persetujuan pemrosesan data, unduh salinan data Anda, ubah kata sandi, atau hapus akun secara permanen.
        </p>
      </div>

      {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}
      {banner ? (
        <div className="rounded-lg border border-positive-line bg-positive-soft p-3 text-sm text-positive">
          ✓ {banner}
        </div>
      ) : null}

      {/* Consent management */}
      <section className="rounded-xl border border-line bg-panel p-5 shadow-sm space-y-3">
        <h2 className="text-base font-bold text-content">Persetujuan Pemrosesan Data</h2>
        <p className="text-xs text-muted">
          Sesuai UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP), nama dan alamat email Anda tidak pernah
          dikirim ke penyedia AI eksternal.
        </p>
        <label className="flex items-center justify-between gap-4 rounded-lg border border-line p-3 text-sm">
          <div>
            <div className="font-semibold text-content">Persetujuan AI Cloud (`ai_cloud`)</div>
            <div className="text-xs text-muted">
              Izinkan pengiriman ringkasan target gizi dan rencana makan anonim ke penyedia AI cloud jika diaktifkan.
            </div>
          </div>
          <input
            type="checkbox"
            checked={cloudConsent}
            onChange={(e) => handleToggleCloudConsent(e.target.checked)}
            className="h-4 w-4"
          />
        </label>
      </section>

      {/* Data portability export */}
      <section className="rounded-xl border border-line bg-panel p-5 shadow-sm space-y-3">
        <h2 className="text-base font-bold text-content">Ekspor Data Pribadi (Portabilitas Data)</h2>
        <p className="text-xs text-muted">
          Unduh seluruh profil, riwayat persetujuan, rencana makan, jadwal latihan, catatan harian, dan riwayat chat
          dalam format JSON.
        </p>
        <button
          type="button"
          onClick={handleExportData}
          data-testid="export-account-btn"
          className="rounded-lg bg-inset px-4 py-2 text-xs font-semibold text-white hover:bg-raised"
        >
          Unduh Data Saya (.json)
        </button>
      </section>

      {/* Change password */}
      <form
        onSubmit={handleChangePassword}
        className="rounded-xl border border-line bg-panel p-5 shadow-sm space-y-4"
      >
        <h2 className="text-base font-bold text-content">Ubah Kata Sandi</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="current-pw" className="block text-xs font-semibold text-secondary">
              Kata Sandi Saat Ini
            </label>
            <input
              id="current-pw"
              type="password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="new-pw" className="block text-xs font-semibold text-secondary">
              Kata Sandi Baru (min. 8 karakter)
            </label>
            <input
              id="new-pw"
              type="password"
              required
              minLength={8}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
            />
          </div>
        </div>
        <button
          type="submit"
          className="rounded-lg bg-positive-hover px-4 py-2 text-xs font-semibold text-white hover:bg-positive-hover"
        >
          Simpan Kata Sandi Baru
        </button>
      </form>

      {/* Delete account */}
      <form
        onSubmit={handleDeleteAccount}
        className="rounded-xl border border-danger-line bg-danger-soft/50 p-5 shadow-sm space-y-3"
      >
        <h2 className="text-base font-bold text-danger">Hapus Akun & Seluruh Data Permanen</h2>
        <p className="text-xs text-danger">
          Tindakan ini akan menghapus akun dan seluruh data Anda secara permanen dari basis data dan tidak dapat
          dibatalkan.
        </p>
        <div>
          <label htmlFor="delete-pw" className="block text-xs font-semibold text-danger">
            Konfirmasi Kata Sandi Anda
          </label>
          <input
            id="delete-pw"
            type="password"
            required
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
            className="mt-1 w-full max-w-xs rounded-lg border border-danger-line bg-panel px-3 py-2 text-sm"
          />
        </div>
        <button
          type="submit"
          data-testid="delete-account-btn"
          className="rounded-lg bg-danger-action px-4 py-2 text-xs font-semibold text-white hover:bg-danger-hover"
        >
          Hapus Akun Saya Secara Permanen
        </button>
      </form>
    </div>
  );
}

