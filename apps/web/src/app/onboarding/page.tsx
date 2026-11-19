"use client";

import { useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";
import { ConsultBlockBanner, ErrorBanner } from "@/components/StatusWidgets";
import { ApiClientError, apiFetch } from "@/lib/api";
import { WEEKDAY_NAMES_ID, formatIdr } from "@/lib/errorMessages";

const STEP_TITLES = [
  "1. Persetujuan Privasi",
  "2. Data Diri",
  "3. Tujuan & Skrining",
  "4. Preferensi Latihan",
  "5. Budget & Pangan",
];

const SCREENING_LABELS: { key: string; label: string }[] = [
  { key: "pregnant_or_breastfeeding", label: "Sedang hamil atau menyusui" },
  { key: "eating_disorder_history", label: "Memiliki riwayat gangguan makan (eating disorder)" },
  { key: "kidney_disease", label: "Memiliki penyakit ginjal" },
  { key: "serious_injury", label: "Memiliki cedera serius yang belum pulih" },
  { key: "other_medical_condition", label: "Memiliki kondisi medis lain yang memerlukan diet/latihan klinis" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [consentText, setConsentText] = useState("");
  const [dataProcessing, setDataProcessing] = useState(true);
  const [aiCloud, setAiCloud] = useState(false);

  const [ageYears, setAgeYears] = useState(22);
  const [sex, setSex] = useState<"male" | "female">("male");
  const [weightKg, setWeightKg] = useState(70);
  const [heightCm, setHeightCm] = useState(170);

  const [activityLevel, setActivityLevel] = useState<"sedentary" | "light" | "moderate" | "active">("light");
  const [goal, setGoal] = useState<"maintain" | "build_strength" | "lose_weight">("maintain");
  const [proteinRatio, setProteinRatio] = useState(1.6);
  const [screening, setScreening] = useState<Record<string, boolean>>({
    pregnant_or_breastfeeding: false,
    eating_disorder_history: false,
    kidney_disease: false,
    serious_injury: false,
    other_medical_condition: false,
  });

  const [workoutDays, setWorkoutDays] = useState<number[]>([0, 2, 4]);
  const [sessionMinutes, setSessionMinutes] = useState<30 | 45 | 60 | 75 | 90>(60);
  const [experienceLevel, setExperienceLevel] = useState<"beginner" | "intermediate">("beginner");
  const [equipmentAccess, setEquipmentAccess] = useState<"bodyweight_only" | "home_dumbbell" | "gym_full">("gym_full");

  const [dailyBudgetIdr, setDailyBudgetIdr] = useState(45000);
  const [excludedFoodIds, setExcludedFoodIds] = useState<string[]>([]);
  const [foods, setFoods] = useState<{ id: string; name: string }[]>([]);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<{ msg: string; reqId?: string } | null>(null);
  const [consultBlocked, setConsultBlocked] = useState(false);

  useEffect(() => {
    apiFetch("/consent")
      .then((res) => {
        setConsentText(res.text || "");
        if (res.current) {
          setDataProcessing(Boolean(res.current.data_processing));
          setAiCloud(Boolean(res.current.ai_cloud));
        }
      })
      .catch(() => {});
    apiFetch("/foods")
      .then((res) => setFoods(res.items || []))
      .catch(() => {});
    apiFetch("/profile")
      .then((res) => {
        const p = res.profile;
        const pr = res.preferences;
        setAgeYears(p.age_years);
        setSex(p.sex);
        setWeightKg(p.weight_kg);
        setHeightCm(p.height_cm);
        setActivityLevel(p.activity_level);
        setGoal(p.goal);
        setProteinRatio(p.protein_g_per_kg);
        setScreening(p.screening || {});
        setWorkoutDays(pr.workout_days || [0, 2, 4]);
        setSessionMinutes(pr.session_minutes || 60);
        setExperienceLevel(pr.experience_level || "beginner");
        setEquipmentAccess(pr.equipment_access || "gym_full");
        setDailyBudgetIdr(pr.daily_budget_idr || 45000);
        setExcludedFoodIds(pr.excluded_food_ids || []);
      })
      .catch(() => {});
  }, []);

  function toggleWorkoutDay(d: number) {
    setWorkoutDays((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort((a, b) => a - b),
    );
  }

  function toggleExcludedFood(fid: string) {
    setExcludedFoodIds((prev) => {
      if (prev.includes(fid)) return prev.filter((x) => x !== fid);
      if (prev.length >= 15) return prev;
      return [...prev, fid];
    });
  }

  async function handleFinish() {
    setError(null);
    if (!dataProcessing) {
      setError({ msg: "Persetujuan pemrosesan data dasar wajib dicentang." });
      setStep(0);
      return;
    }
    if (workoutDays.length < 2 || workoutDays.length > 6) {
      setError({ msg: "Pilih antara 2 hingga 6 hari latihan." });
      setStep(3);
      return;
    }
    setSaving(true);
    try {
      await apiFetch("/consent", {
        method: "POST",
        body: JSON.stringify({
          consent_version: "1.0",
          data_processing: dataProcessing,
          ai_cloud: aiCloud,
        }),
      });
      const res = await apiFetch("/profile", {
        method: "PUT",
        body: JSON.stringify({
          profile: {
            age_years: Number(ageYears),
            sex,
            weight_kg: Number(weightKg),
            height_cm: Number(heightCm),
            activity_level: activityLevel,
            goal,
            protein_g_per_kg: Number(proteinRatio),
            screening,
          },
          preferences: {
            daily_budget_idr: Number(dailyBudgetIdr),
            workout_days: workoutDays,
            session_minutes: Number(sessionMinutes),
            experience_level: experienceLevel,
            equipment_access: equipmentAccess,
            excluded_food_ids: excludedFoodIds,
            allergies: [],
            excluded_exercise_ids: [],
            region: "default",
          },
        }),
      });
      if (!res.plan_generation_allowed) {
        setConsultBlocked(true);
      } else {
        router.push("/nutrition");
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError({ msg: err.message, reqId: err.requestId });
      } else {
        setError({ msg: "Gagal menyimpan profil." });
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Onboarding Profil &amp; Preferensi</h1>
          <p className="text-xs text-slate-600 mt-1">
            Lengkapi 5 langkah berikut untuk menghitung estimasi kebutuhan energi, protein, dan preferensi Anda.
          </p>
        </div>

        <ol className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
          {STEP_TITLES.map((title, idx) => (
            <li key={title}>
              <button
                type="button"
                onClick={() => setStep(idx)}
                className={`w-full rounded px-2 py-1.5 text-left font-medium border ${
                  step === idx
                    ? "border-indigo-600 bg-indigo-50 text-indigo-800"
                    : "border-slate-200 bg-slate-50 text-slate-600"
                }`}
              >
                {title}
              </button>
            </li>
          ))}
        </ol>

        {error ? <ErrorBanner message={error.msg} requestId={error.reqId} /> : null}
        {consultBlocked ? (
          <div className="space-y-3">
            <ConsultBlockBanner />
            <button
              type="button"
              onClick={() => router.push("/nutrition")}
              className="rounded bg-indigo-600 px-4 py-2 text-xs font-semibold text-white"
            >
              Lihat Estimasi Nutrisi
            </button>
          </div>
        ) : null}

        {step === 0 ? (
          <div className="space-y-4">
            <h2 className="text-base font-semibold">Langkah 1: Persetujuan Pemrosesan Data</h2>
            <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700 leading-relaxed border border-slate-200">
              {consentText ||
                "FitBudget AI memproses data tubuh, preferensi makanan/latihan, dan catatan harian Anda untuk menghitung estimasi kebutuhan gizi dan menyusun rencana secara lokal. Aplikasi ini bukan layanan medis."}
            </p>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={dataProcessing}
                onChange={(e) => setDataProcessing(e.target.checked)}
                className="mt-1"
              />
              <span>
                Saya berusia ≥ 18 tahun dan menyetujui pemrosesan data untuk perhitungan estimasi &amp; perencanaan{" "}
                <strong>(Wajib)</strong>.
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={aiCloud}
                onChange={(e) => setAiCloud(e.target.checked)}
                className="mt-1"
              />
              <span>
                Opsional: Izinkan penggunaan penyedia AI Cloud (Gemini) bila model lokal tidak digunakan. Data
                dikirim secara teranonimkan tanpa identitas pribadi (default: nonaktif).
              </span>
            </label>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="ob-age" className="block text-xs font-semibold text-slate-700 mb-1">
                Umur (18–80 tahun)
              </label>
              <input
                id="ob-age"
                type="number"
                min={18}
                max={80}
                value={ageYears}
                onChange={(e) => setAgeYears(Number(e.target.value))}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label htmlFor="ob-sex" className="block text-xs font-semibold text-slate-700 mb-1">
                Jenis Kelamin Biologis (Rumus Mifflin–St Jeor)
              </label>
              <select
                id="ob-sex"
                value={sex}
                onChange={(e) => setSex(e.target.value as "male" | "female")}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="male">Laki-laki (male, s = +5)</option>
                <option value="female">Perempuan (female, s = −161)</option>
              </select>
            </div>
            <div>
              <label htmlFor="ob-weight" className="block text-xs font-semibold text-slate-700 mb-1">
                Berat Badan (30–250 kg)
              </label>
              <input
                id="ob-weight"
                type="number"
                step="0.1"
                min={30}
                max={250}
                value={weightKg}
                onChange={(e) => setWeightKg(Number(e.target.value))}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label htmlFor="ob-height" className="block text-xs font-semibold text-slate-700 mb-1">
                Tinggi Badan (120–230 cm)
              </label>
              <input
                id="ob-height"
                type="number"
                min={120}
                max={230}
                value={heightCm}
                onChange={(e) => setHeightCm(Number(e.target.value))}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="ob-act" className="block text-xs font-semibold text-slate-700 mb-1">
                  Tingkat Aktivitas
                </label>
                <select
                  id="ob-act"
                  value={activityLevel}
                  onChange={(e) => setActivityLevel(e.target.value as any)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="sedentary">Sedentary — Hampir tidak olahraga (1,2)</option>
                  <option value="light">Light — Olahraga ringan 1–3 hari/minggu (1,375)</option>
                  <option value="moderate">Moderate — Olahraga sedang 3–5 hari/minggu (1,55)</option>
                  <option value="active">Active — Olahraga berat 6–7 hari/minggu (1,725)</option>
                </select>
              </div>
              <div>
                <label htmlFor="ob-goal" className="block text-xs font-semibold text-slate-700 mb-1">
                  Tujuan Utama
                </label>
                <select
                  id="ob-goal"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value as any)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="maintain">Maintain — Pertahankan berat (0%)</option>
                  <option value="build_strength">Build Strength — Tambah kekuatan (+10%)</option>
                  <option value="lose_weight">Lose Weight — Turunkan berat moderat (−10%)</option>
                </select>
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
              <div className="text-xs font-semibold text-slate-800">
                Skrining Keamanan Kesehatan (centang bila berlaku pada Anda):
              </div>
              {SCREENING_LABELS.map((item) => (
                <label key={item.key} className="flex items-center gap-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={Boolean(screening[item.key])}
                    onChange={(e) => setScreening((prev) => ({ ...prev, [item.key]: e.target.checked }))}
                  />
                  <span>{item.label}</span>
                </label>
              ))}
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="space-y-4">
            <div>
              <span className="block text-xs font-semibold text-slate-700 mb-2">
                Hari Tersedia Latihan (pilih 2–6 hari):
              </span>
              <div className="flex flex-wrap gap-2">
                {WEEKDAY_NAMES_ID.map((name, idx) => {
                  const selected = workoutDays.includes(idx);
                  return (
                    <button
                      key={name}
                      type="button"
                      onClick={() => toggleWorkoutDay(idx)}
                      className={`rounded px-3 py-1.5 text-xs font-medium border ${
                        selected
                          ? "border-indigo-600 bg-indigo-600 text-white"
                          : "border-slate-300 bg-white text-slate-700"
                      }`}
                    >
                      {name}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label htmlFor="ob-min" className="block text-xs font-semibold text-slate-700 mb-1">
                  Durasi per Sesi
                </label>
                <select
                  id="ob-min"
                  value={sessionMinutes}
                  onChange={(e) => setSessionMinutes(Number(e.target.value) as any)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                >
                  {[30, 45, 60, 75, 90].map((m) => (
                    <option key={m} value={m}>
                      {m} menit
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="ob-exp" className="block text-xs font-semibold text-slate-700 mb-1">
                  Pengalaman
                </label>
                <select
                  id="ob-exp"
                  value={experienceLevel}
                  onChange={(e) => setExperienceLevel(e.target.value as any)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="beginner">Pemula (Beginner)</option>
                  <option value="intermediate">Menengah (Intermediate)</option>
                </select>
              </div>
              <div>
                <label htmlFor="ob-eq" className="block text-xs font-semibold text-slate-700 mb-1">
                  Akses Alat
                </label>
                <select
                  id="ob-eq"
                  value={equipmentAccess}
                  onChange={(e) => setEquipmentAccess(e.target.value as any)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="bodyweight_only">Tanpa Alat (Bodyweight)</option>
                  <option value="home_dumbbell">Dumbbell di Rumah</option>
                  <option value="gym_full">Gym Lengkap</option>
                </select>
              </div>
            </div>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="space-y-4">
            <div>
              <label htmlFor="ob-budget" className="block text-xs font-semibold text-slate-700 mb-1">
                Budget Makanan Harian (Rp 10.000 – Rp 500.000):{" "}
                <strong className="text-indigo-700">{formatIdr(dailyBudgetIdr)}</strong>
              </label>
              <input
                id="ob-budget"
                type="number"
                min={10000}
                max={500000}
                step={1000}
                value={dailyBudgetIdr}
                onChange={(e) => setDailyBudgetIdr(Number(e.target.value))}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <span className="block text-xs font-semibold text-slate-700 mb-1">
                Pengecualian / Alergi Pangan (opsional, maks. 15):
              </span>
              <div className="max-h-48 overflow-y-auto grid grid-cols-1 sm:grid-cols-2 gap-1.5 rounded border border-slate-200 p-2 text-xs">
                {foods.map((f) => (
                  <label key={f.id} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={excludedFoodIds.includes(f.id)}
                      onChange={() => toggleExcludedFood(f.id)}
                    />
                    <span>{f.name}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        ) : null}

        <div className="flex items-center justify-between pt-3 border-t border-slate-200">
          <button
            type="button"
            disabled={step === 0}
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            className="rounded border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 disabled:opacity-40"
          >
            Kembali
          </button>
          {step < 4 ? (
            <button
              type="button"
              onClick={() => setStep((s) => Math.min(4, s + 1))}
              className="rounded bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700"
            >
              Lanjut
            </button>
          ) : (
            <button
              type="button"
              disabled={saving}
              onClick={handleFinish}
              data-testid="onboarding-submit"
              className="rounded bg-emerald-600 px-5 py-2 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {saving ? "Menyimpan..." : "Simpan Profil & Hitung Estimasi"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

