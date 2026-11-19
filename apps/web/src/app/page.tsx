import { Activity, Dumbbell, Utensils, Wallet } from "lucide-react";
import Link from "next/link";
import { MotionScene } from "@/components/MotionScene";

export default function HomePage() {
  return (
    <div className="landing">
      <section className="landing-hero">
        <MotionScene />
        <div className="hero-copy">
          <span className="hero-kicker"><Activity size={16} /> FITBUDGET AI</span>
          <h1>Makan terencana.<br />Latihan teratur.</h1>
          <p>Susun menu sesuai anggaran, atur jadwal latihan, dan ikuti progres Anda dalam satu tempat.</p>
          <div className="landing-actions">
            <Link href="/register" className="action-primary">Buat akun</Link>
            <Link href="/dashboard" className="action-secondary">Buka dashboard</Link>
          </div>
        </div>
      </section>
      <section className="landing-features" aria-label="Fitur FitBudget">
        <div className="panel"><span className="quick-icon"><Utensils size={19} /></span><h2>Menu 7 hari</h2><p>Rencanakan porsi berdasarkan target nutrisi.</p></div>
        <div className="panel"><span className="quick-icon"><Wallet size={19} /></span><h2>Anggaran harian</h2><p>Bandingkan biaya menu dengan anggaran Anda.</p></div>
        <div className="panel"><span className="quick-icon"><Dumbbell size={19} /></span><h2>Jadwal latihan</h2><p>Susun sesi sesuai hari, peralatan, dan jeda pemulihan.</p></div>
      </section>
    </div>
  );
}
