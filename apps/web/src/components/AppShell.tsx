"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export interface AuthMe {
  user_id: string;
  email: string;
  role: "user" | "admin";
  consent_required: boolean;
  profile_complete: boolean;
}

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/nutrition", label: "Nutrisi" },
  { href: "/meal-plan", label: "Menu 7 Hari" },
  { href: "/workout", label: "Jadwal Gym" },
  { href: "/tracker", label: "Tracker" },
  { href: "/chat", label: "Asisten AI" },
  { href: "/settings", label: "Pengaturan" },
];

const ADMIN_ITEMS = [
  { href: "/admin/foods", label: "Admin Pangan" },
  { href: "/admin/prices", label: "Admin Harga" },
  { href: "/admin/exercises", label: "Admin Latihan" },
  { href: "/admin/audit", label: "Audit Log" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<AuthMe | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const isPublic = pathname === "/login" || pathname === "/register";

  useEffect(() => {
    let active = true;
    apiFetch<AuthMe>("/auth/me")
      .then((res) => {
        if (!active) return;
        setMe(res);
      })
      .catch(() => {
        if (!active) return;
        setMe(null);
      });
    return () => {
      active = false;
    };
  }, [pathname]);

  async function handleLogout() {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // ignore
    }
    setMe(null);
    router.push("/login");
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 overflow-x-hidden">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 gap-2">
          <Link href={me ? "/dashboard" : "/login"} className="text-lg font-bold tracking-tight text-indigo-700">
            FitBudget AI
          </Link>

          {!isPublic && me ? (
            <>
              <button
                type="button"
                aria-label="Buka menu navigasi"
                onClick={() => setMenuOpen((v) => !v)}
                className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium md:hidden"
              >
                Menu
              </button>
              <nav aria-label="Navigasi utama" className="hidden md:flex flex-wrap items-center gap-1 text-xs font-medium">
                {NAV_ITEMS.map((item) => {
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`rounded px-2.5 py-1.5 transition ${
                        active ? "bg-indigo-600 text-white" : "text-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
                {me.role === "admin"
                  ? ADMIN_ITEMS.map((item) => {
                      const active = pathname === item.href;
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          className={`rounded px-2.5 py-1.5 transition ${
                            active ? "bg-amber-600 text-white" : "text-amber-800 hover:bg-amber-50"
                          }`}
                        >
                          {item.label}
                        </Link>
                      );
                    })
                  : null}
                <button
                  type="button"
                  onClick={handleLogout}
                  className="ml-2 rounded border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100"
                >
                  Keluar
                </button>
              </nav>
            </>
          ) : (
            <div className="flex items-center gap-2 text-xs font-medium">
              <Link href="/login" className="rounded px-3 py-1.5 text-slate-700 hover:bg-slate-100">
                Masuk
              </Link>
              <Link href="/register" className="rounded bg-indigo-600 px-3 py-1.5 text-white hover:bg-indigo-700">
                Daftar
              </Link>
            </div>
          )}
        </div>

        {!isPublic && me && menuOpen ? (
          <nav aria-label="Navigasi seluler" className="border-t border-slate-200 bg-white px-4 py-2 md:hidden flex flex-col gap-1 text-sm">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMenuOpen(false)}
                className={`rounded px-3 py-1.5 ${
                  pathname === item.href ? "bg-indigo-600 text-white" : "text-slate-700"
                }`}
              >
                {item.label}
              </Link>
            ))}
            {me.role === "admin"
              ? ADMIN_ITEMS.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMenuOpen(false)}
                    className="rounded px-3 py-1.5 text-amber-800"
                  >
                    {item.label}
                  </Link>
                ))
              : null}
            <button
              type="button"
              onClick={handleLogout}
              className="mt-1 rounded border border-slate-300 px-3 py-1.5 text-left text-slate-700"
            >
              Keluar ({me.email})
            </button>
          </nav>
        ) : null}
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>

      <footer className="border-t border-slate-200 bg-white px-4 py-4 text-center text-xs text-slate-600">
        FitBudget AI adalah alat perencanaan &amp; edukasi untuk orang dewasa sehat, bukan layanan medis.
      </footer>
    </div>
  );
}

