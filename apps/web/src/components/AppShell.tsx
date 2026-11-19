"use client";

import {
  Activity, BicepsFlexed, CalendarDays, ChartNoAxesColumnIncreasing, ClipboardList, Dumbbell, Flame,
  House, LogOut, Menu, Settings, Sparkles, UserRound, Utensils, Wallet, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { apiFetch } from "@/lib/api";

export interface AuthMe {
  user_id: string;
  email: string;
  role: "user" | "admin";
  consent_required: boolean;
  profile_complete: boolean;
}

const mainItems = [
  { href: "/dashboard", label: "Beranda", icon: House },
  { href: "/workout", label: "Latihan", icon: Dumbbell },
  { href: "/meal-plan", label: "Menu Makan", icon: Utensils },
  { href: "/nutrition", label: "Target Nutrisi", icon: Flame },
  { href: "/tracker", label: "Progres", icon: ChartNoAxesColumnIncreasing },
];

const otherItems = [
  { href: "/chat", label: "Asisten AI", icon: Sparkles },
  { href: "/settings", label: "Pengaturan", icon: Settings },
];

const adminItems = [
  { href: "/admin/foods", label: "Admin Pangan", icon: Utensils },
  { href: "/admin/prices", label: "Admin Harga", icon: Wallet },
  { href: "/admin/exercises", label: "Admin Latihan", icon: BicepsFlexed },
  { href: "/admin/audit", label: "Log Audit", icon: ClipboardList },
];

function Brand({ href }: { href: string }) {
  return (
    <Link className="brand" href={href}>
      <span className="brand-icon"><Activity size={23} strokeWidth={2.7} /></span>
      <span>Fit<span>Budget</span></span>
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<AuthMe | null>(null);
  const drawer = useRef<HTMLDialogElement>(null);
  const isPublic = ["/", "/login", "/register"].includes(pathname);
  const allItems = [...mainItems, ...otherItems, ...(me?.role === "admin" ? adminItems : [])];
  const current = allItems.find((item) => item.href === pathname);
  const mobilePaths = ["/dashboard", "/workout", "/tracker", "/meal-plan"];
  const [dateLabel, setDateLabel] = useState("");

  useEffect(() => {
    setDateLabel(new Intl.DateTimeFormat("id-ID", {
      weekday: "long", day: "numeric", month: "short", timeZone: "Asia/Jakarta",
    }).format(new Date()));
  }, []);

  useEffect(() => {
    const request = new AbortController();
    apiFetch<AuthMe>("/auth/me", { signal: request.signal })
      .then((result) => { if (!request.signal.aborted) setMe(result); })
      .catch(() => { if (!request.signal.aborted) setMe(null); });
    return () => request.abort();
  }, [pathname]);

  async function handleLogout() {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      return;
    }
    drawer.current?.close();
    setMe(null);
    router.push("/login");
  }

  function renderItem({ href, label, icon: Icon }: (typeof mainItems)[number]) {
    return (
      <Link key={href} className="nav-link" href={href} aria-current={pathname === href ? "page" : undefined}
        onClick={() => drawer.current?.close()}>
        <Icon size={19} /><span>{label}</span>
      </Link>
    );
  }

  const logout = me && <button className="nav-link" type="button" onClick={handleLogout}><LogOut size={19} /> Keluar</button>;

  if (isPublic) return (
    <div className="app-frame public-frame">
      <header className="public-header">
        <Brand href="/" />
        <nav aria-label="Akun">
          <Link href="/login" className="action-secondary">Masuk</Link>
          <Link href="/register" className="action-primary">Daftar</Link>
        </nav>
      </header>
      <main id="main-content" className="public-content">{children}</main>
    </div>
  );

  const pageClass = pathname === "/dashboard" ? " dashboard-content" : "";
  return (
    <div className="app-frame app-layout">
      <a className="skip-link" href="#main-content">Lewati ke konten</a>
      <aside className="app-sidebar">
        <Brand href="/dashboard" />
        <nav aria-label="Navigasi utama" className="sidebar-nav">
          <div className="sidebar-group"><span>AKTIVITAS</span>{mainItems.map(renderItem)}</div>
          <div className="sidebar-group"><span>AKUN</span>{otherItems.map(renderItem)}</div>
          {me?.role === "admin" && <div className="sidebar-group"><span>ADMIN</span>{adminItems.map(renderItem)}</div>}
        </nav>
        <div className="sidebar-account">
          {me ? <><div className="account-details"><span className="avatar">{me.email[0]?.toUpperCase()}</span>
            <span><strong>{me.email.split("@")[0]}</strong><small>{me.role === "admin" ? "Administrator" : "Anggota FitBudget"}</small></span>
          </div>{logout}</> : <Link href="/login" className="nav-link"><UserRound size={19} /> Masuk</Link>}
        </div>
      </aside>
      <div className="app-workspace">
        <header className="app-header">
          <div className="desktop-location">FitBudget <span>/</span> <strong>{current?.label ?? "Profil"}</strong></div>
          <div className="mobile-brand"><Brand href="/dashboard" /></div>
          <div className="header-actions">
            {dateLabel && <span className="header-date"><CalendarDays size={16} /> {dateLabel}</span>}
            <Link href="/chat" className="icon-button" aria-label="Asisten AI"><Sparkles size={19} /></Link>
            <Link href={me ? "/settings" : "/login"} className="avatar" aria-label={me ? "Pengaturan akun" : "Masuk"}>
              {me ? me.email[0]?.toUpperCase() : <UserRound size={18} />}
            </Link>
          </div>
        </header>
        <main id="main-content" className={`app-content route-content${pageClass}`} key={pathname}>{children}</main>
        <footer className="app-footer">FitBudget AI · Alat perencanaan dan edukasi untuk orang dewasa sehat.</footer>
      </div>
      <nav className="mobile-dock" aria-label="Navigasi bawah">
        {mobilePaths.map((href) => {
          const { icon: Icon, label } = mainItems.find((item) => item.href === href)!;
          return (
            <Link key={href} href={href} className={href === "/tracker" ? "dock-primary" : undefined}
              aria-current={pathname === href ? "page" : undefined}>
              <span><Icon size={21} /></span><small>{href === "/meal-plan" ? "Menu" : label}</small>
            </Link>
          );
        })}
        <button type="button" onClick={() => drawer.current?.showModal()} aria-haspopup="dialog" aria-controls="mobile-menu"
          data-active={!mobilePaths.includes(pathname)}>
          <span><Menu size={21} /></span><small>Lainnya</small>
        </button>
      </nav>
      <dialog id="mobile-menu" className="mobile-sheet" ref={drawer} aria-labelledby="mobile-menu-title"
        onClick={(event) => { if (event.target === event.currentTarget) drawer.current?.close(); }}>
        <div className="sheet-content">
          <div className="sheet-head"><h2 id="mobile-menu-title">Navigasi</h2>
            <button type="button" className="icon-button" aria-label="Tutup menu" onClick={() => drawer.current?.close()}><X size={21} /></button>
          </div>
          <nav aria-label="Semua halaman">{allItems.map(renderItem)}{logout}</nav>
        </div>
      </dialog>
    </div>
  );
}

