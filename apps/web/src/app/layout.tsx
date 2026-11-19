import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "FitBudget AI — Perencanaan Gizi, Budget & Latihan",
  description:
    "Platform perencanaan menu 7 hari berbasis budget harian, estimasi energi/protein deterministik, dan jadwal gym.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id">
      <body className="antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
