import Link from "next/link";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 py-8">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <span className="inline-block rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-800">
          FitBudget AI v2.0
        </span>
        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">
          Perencanaan Gizi, Menu 7 Hari Sesuai Budget &amp; Jadwal Gym
        </h1>
        <p className="text-sm text-slate-600 leading-relaxed">
          Semua perhitungan energi (Mifflin–St Jeor), target protein, optimasi menu 7 hari berbasis{" "}
          <strong>batas budget harian (OR-Tools CP-SAT)</strong>, dan penjadwalan latihan dihitung secara
          deterministik oleh backend dan dapat diverifikasi tanpa AI.
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link
            href="/register"
            className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Mulai Sekarang (Daftar)
          </Link>
          <Link
            href="/login"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-800 hover:bg-slate-100"
          >
            Masuk ke Akun
          </Link>
          <Link
            href="/dashboard"
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm font-semibold text-indigo-800 hover:bg-indigo-100"
          >
            Buka Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
