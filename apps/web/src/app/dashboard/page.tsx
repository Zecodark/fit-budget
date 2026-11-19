"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Activity, ChevronDown, ChevronRight, CircleAlert, Dumbbell, Flame, Plus, Scale, Sparkles, Utensils, Wallet, Zap } from "lucide-react";
import { MotionScene } from "@/components/MotionScene";
import { apiFetch, ApiClientError } from "@/lib/api";
import { formatDec1, formatIdr, formatInt } from "@/lib/errorMessages";
import { ErrorBanner } from "@/components/StatusWidgets";

interface Intake {
  energy_kcal: number;
  protein_g: number;
  cost_idr: number;
}

interface DayItem {
  date: string;
  planned: Intake;
  actual: Intake & { has_logs: boolean };
  workout: { planned: number; completed: number; skipped: number };
}

interface DashboardSummary {
  week_start: string;
  targets: { energy_kcal: number; protein_g: number; daily_budget_idr: number };
  days: DayItem[];
  summary: { workouts_planned: number; workouts_completed: number };
  alerts: { code: string; date: string; message: string }[];
  text_summary: string;
}

interface WeightEntry { date: string; weight_kg: number }

const alertActions: Record<string, string> = {
  BUDGET_OVERRUN: "/tracker",
  PROTEIN_LOW: "/nutrition",
  PLAN_OVER_BUDGET_AFTER_PRICE_CHANGE: "/meal-plan",
  MISSED_WORKOUT: "/workout",
  PROFILE_STALE: "/onboarding",
};

function Chart({ days, target }: { days: DayItem[]; target: number }) {
  const max = Math.max(1, target, ...days.map((day) => day.actual.energy_kcal));
  const scale = (value: number) => 100 * value / max;
  return (
    <div className="weekly-chart" role="img" aria-label="Perbandingan energi aktual dan target per hari">
      {days.map((day) => (
        <div className="chart-day" key={day.date} title={`${day.date}: ${formatInt(day.actual.energy_kcal)} / ${formatInt(target)} kkal`}>
          <div className="chart-bars">
            <span style={{ height: `${scale(target)}%` }} className="chart-target" />
            <span style={{ height: `${scale(day.actual.energy_kcal)}%` }} className="chart-actual" />
          </div>
          <small>{dayName.format(parseDay(day.date))}</small>
        </div>
      ))}
    </div>
  );
}

const parseDay = (day: string) => new Date(`${day}T12:00:00+07:00`);
const dayName = new Intl.DateTimeFormat("id-ID", { weekday: "short", timeZone: "Asia/Jakarta" });
const fullDate = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "long", timeZone: "Asia/Jakarta" });

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [weight, setWeight] = useState<WeightEntry | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ msg: string; reqId?: string; status?: number; code?: string } | null>(null);
  const loadSummary = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const [result, weights] = await Promise.all([
        apiFetch<DashboardSummary>("/dashboard", { signal }),
        apiFetch<{ items: WeightEntry[] }>("/logs/weight", { signal }).catch(() => null),
      ]);
      if (!signal?.aborted) {
        setData(result);
        setWeight(weights?.items.at(-1) ?? null);
      }
    } catch (err) {
      if (signal?.aborted) return;
      if (err instanceof ApiClientError) setError({ msg: err.message, reqId: err.requestId, status: err.status, code: err.code });
      else setError({ msg: "Gagal memuat ringkasan dashboard." });
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const request = new AbortController();
    void loadSummary(request.signal);
    return () => request.abort();
  }, [loadSummary]);

  const today = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Jakarta" }).format(new Date());
  const day = data?.days.find((item) => item.date === (selected ?? today)) ?? data?.days[0];
  const target = data?.targets;
  const metrics = day && target ? [
    { label: "Energi", icon: Flame, tone: "energy", value: formatInt(day.actual.energy_kcal), target: formatInt(target.energy_kcal),
      unit: "kkal", actual: day.actual.energy_kcal, total: target.energy_kcal },
    { label: "Protein", icon: Zap, tone: "protein", value: formatDec1(day.actual.protein_g), target: formatDec1(target.protein_g),
      unit: "g", actual: day.actual.protein_g, total: target.protein_g },
    { label: "Pengeluaran", icon: Wallet, tone: "budget", value: formatIdr(day.actual.cost_idr), target: formatIdr(target.daily_budget_idr),
      unit: "", actual: day.actual.cost_idr, total: target.daily_budget_idr },
  ] : [];

  return (
    <div className="dashboard">
      <div className="dashboard-heading">
        <div><h1>Dashboard</h1><p>Ringkasan nutrisi, anggaran, dan latihan Anda.</p></div>
        <Link href="/tracker" className="action-primary desktop-add"><Plus size={18} /> Catat hari ini</Link>
      </div>

      <section className="dashboard-hero">
        <MotionScene />
        <div className="hero-copy">
          <span className="hero-kicker"><Activity size={15} /> TARGET MINGGUAN</span>
          <h2>Latihan yang<br />terencana.</h2>
          <p>Susun sesi berdasarkan jadwal dan peralatan Anda.</p>
          <Link href="/workout" className="action-primary">Buka jadwal <ChevronRight size={17} /></Link>
        </div>
      </section>

      {error && (error.status === 401 ? (
        <div className="panel signed-out"><p>Masuk untuk melihat progres pribadi Anda.</p><Link href="/login" className="action-primary">Masuk</Link></div>
      ) : error.code === "CONSENT_REQUIRED" ? (
        <div className="panel signed-out"><p>Lengkapi persetujuan data untuk melihat ringkasan Anda.</p><Link href="/onboarding" className="action-primary">Atur profil</Link></div>
      ) : <ErrorBanner message={error.msg} requestId={error.reqId} onRetry={() => void loadSummary()} />)}

      {!data && loading && <div className="dashboard-loading panel" role="status">Memuat ringkasan…</div>}

      {data && day && target && (
        <>
          <section className="dashboard-overview">
            <div className="overview-main">
              <div className="section-heading"><h2>Minggu ini</h2><span>{fullDate.formatRange(parseDay(data.week_start), parseDay(data.days.at(-1)?.date ?? data.week_start))}</span></div>
              <div className="week-strip" aria-label="Pilih hari untuk melihat ringkasan">
                {data.days.map((item) => (
                  <button type="button" key={item.date} aria-pressed={day.date === item.date} onClick={() => setSelected(item.date)} aria-label={fullDate.format(parseDay(item.date))}>
                    <small>{dayName.format(parseDay(item.date))}</small><span>{Number(item.date.slice(-2))}</span>
                    <i data-logged={item.actual.has_logs || item.workout.completed > 0} />
                  </button>
                ))}
              </div>
              <div className="section-heading metrics-heading">
                <h2>{day.date === today ? "Nutrisi hari ini" : `Ringkasan ${fullDate.format(parseDay(day.date))}`}</h2>
                <Link className="text-action" href="/nutrition">Target <ChevronRight size={15} /></Link>
              </div>
              <div className="metric-grid">
                {metrics.map(({ icon: Icon, tone, label, value, target, unit, actual, total }) => (
                  <div className={`panel metric metric-${tone}`} key={label}>
                    <span className="metric-icon"><Icon size={19} /></span><span className="metric-label">{label}</span>
                    <strong>{value} <small>{unit}</small></strong>
                    <span className="metric-target">dari {target}{unit && ` ${unit}`}</span>
                    <span className="metric-track" aria-hidden="true"><i style={{ width: `${total > 0 ? Math.min(100, 100 * actual / total) : 0}%` }} /></span>
                  </div>
                ))}
              </div>
            </div>
            <section className="panel chart-panel">
              <div className="section-heading"><h2>Energi mingguan</h2><span>kkal</span></div>
              <div className="chart-total"><strong>{formatInt(data.days.reduce((total, item) => total + item.actual.energy_kcal, 0))}</strong><span> / {formatInt(target.energy_kcal * data.days.length)} target</span></div>
              <Chart days={data.days} target={target.energy_kcal} />
              <div className="chart-legend"><span><i /> Aktual</span><span><i /> Target</span></div>
            </section>
          </section>

          <section className="dashboard-activity">
            <div className="section-heading"><h2>Aktivitas minggu ini</h2><Link href="/tracker" className="text-action">Lihat progres <ChevronRight size={15} /></Link></div>
            <div className="activity-grid">
              <Link href="/tracker" className="panel activity-row"><span className="quick-icon"><Dumbbell size={20} /></span>
                <span><strong>Sesi latihan</strong><small>{day.workout.completed ? "Sesi hari terpilih selesai" : day.workout.planned ? "Ada sesi terjadwal pada hari terpilih" : "Hari terpilih tanpa jadwal"}</small></span>
                <b>{data.summary.workouts_completed}/{data.summary.workouts_planned}</b>
              </Link>
              <Link href="/tracker" className="panel activity-row"><span className="quick-icon"><Scale size={20} /></span>
                <span><strong>Berat badan</strong><small>{weight ? fullDate.format(parseDay(weight.date)) : "Belum ada catatan"}</small></span>
                <b>{weight ? `${formatDec1(weight.weight_kg)} kg` : "—"}</b>
              </Link>
            </div>
          </section>
        </>
      )}

      <section>
        <div className="section-heading"><h2>Rencanakan berikutnya</h2></div>
        <div className="explore-grid">
          <Link href="/meal-plan" className="explore-card">
            <span className="explore-art meal-art"><Utensils size={56} strokeWidth={1.25} /></span>
            <span className="explore-copy"><strong>Menu 7 hari</strong><small>Sesuaikan dengan anggaran</small></span>
            <ChevronRight size={18} />
          </Link>
          <Link href="/workout" className="explore-card">
            <span className="explore-art workout-art"><Dumbbell size={61} strokeWidth={1.25} /></span>
            <span className="explore-copy"><strong>Jadwal latihan</strong><small>Susun sesi untuk minggu ini</small></span>
            <ChevronRight size={18} />
          </Link>
          <Link href="/chat" className="explore-card">
            <span className="explore-art chat-art"><Sparkles size={54} strokeWidth={1.25} /></span>
            <span className="explore-copy"><strong>Asisten AI</strong><small>Bahas rencana Anda</small></span>
            <ChevronRight size={18} />
          </Link>
        </div>
      </section>

      {data && (
        <>
          {data.alerts.length > 0 && (
            <section className="dashboard-alerts" data-testid="dashboard-alerts">
              <div className="section-heading"><h2>Catatan dan saran</h2></div>
              {data.alerts.map((alert, i) => (
                <div className="panel alert-row" key={`${alert.code}-${i}`} data-severity="warn" data-testid={`alert-${alert.code}`}>
                  <CircleAlert size={19} /><p>{alert.message}</p><Link href={alertActions[alert.code] ?? "/tracker"} className="action-secondary">Tindak lanjuti</Link>
                </div>
              ))}
            </section>
          )}
          <div className="panel dashboard-loading" data-testid="dashboard-text-summary">{data.text_summary}</div>
          <details className="panel detail-panel">
            <summary>Rincian mingguan <ChevronDown size={18} /></summary>
            <div className="overflow-x-auto">
              <table>
                <thead><tr><th>Tanggal</th><th>Energi (aktual / rencana / target)</th><th>Protein (aktual / rencana / target)</th><th>Biaya (aktual / rencana / anggaran)</th><th>Latihan</th></tr></thead>
                <tbody>
                  {data.days.map((item) => <tr key={item.date}>
                    <th scope="row">{fullDate.format(parseDay(item.date))}</th>
                    <td>{formatInt(item.actual.energy_kcal)} / {formatInt(item.planned.energy_kcal)} / {formatInt(data.targets.energy_kcal)} kkal</td>
                    <td>{formatDec1(item.actual.protein_g)} / {formatDec1(item.planned.protein_g)} / {formatDec1(data.targets.protein_g)} g</td>
                    <td>{formatIdr(item.actual.cost_idr)} / {formatIdr(item.planned.cost_idr)} / {formatIdr(data.targets.daily_budget_idr)}</td>
                    <td>{item.workout.completed ? "Selesai" : item.workout.planned ? "Terjadwal" : "Istirahat"}</td>
                  </tr>)}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </div>
  );
}
