# FitBudget AI v2.0

**Sistem Perencanaan Makan Hemat Anggaran & Jadwal Latihan Deterministik dengan Asisten AI Terkendali (Bahasa Indonesia)**

FitBudget AI membantu pengguna di Indonesia merencanakan menu mingguan bergizi sesuai anggaran Rupiah harian, menyusun jadwal latihan beban/kalistenik yang aman berdasarkan peralatan dan riwayat cedera, serta memantau progres mingguan — dengan pemisahan tegas antara **mesin deterministik** (kalkulator gizi, solver CP-SAT OR-Tools, penjadwal latihan) dan **lapisan asisten AI** (penjelasan Bahasa Indonesia & usulan terparameterisasi yang memerlukan konfirmasi pengguna).

---

## Arsitektur & Prinsip Utama (Golden Rules)

1. **100% Deterministik untuk Angka & Rencana**: Semua perhitungan kalori (Mifflin–St Jeor), makronutrisi, harga Rupiah, optimasi menu (Google OR-Tools CP-SAT + pemeriksa independen `Decimal`), dan jadwal latihan dihitung oleh fungsi murni di backend Python. LLM tidak pernah menghitung angka.
2. **Transparansi Status Kelayakan (`FEASIBLE` / `PARTIAL` / `INFEASIBLE`)**: Sistem tidak pernah mengklaim `"target terpenuhi"` apabila anggaran tidak mencukupi. Saat `INFEASIBLE`, sistem menghitung estimasi anggaran harian minimum yang dibutuhkan (`minimum_budget_required_idr`).
3. **Asisten AI Hanya Mengusulkan (`Pending Proposal`)**: LLM tidak pernah menulis langsung ke basis data rencana. Usulan perubahan (`change_budget`, `exclude_food`, `reschedule_workout`) ditampilkan sebagai kartu pratinjau yang harus dikonfirmasi pengguna.
4. **Berfungsi Penuh Tanpa AI (`AI_PROVIDER=none`)**: Seluruh fitur utama berjalan penuh meskipun AI dimatikan.
5. **Kepatuhan Privasi (UU PDP)**: Persetujuan eksplisit tercatat per versi, data PII (`full_name`, `email`) tidak pernah dikirim ke penyedia AI, tersedia fitur ekspor data JSON (`GET /api/v1/account/export`) dan penghapusan akun permanen (`DELETE /api/v1/account`).

---

## Struktur Monorepo

```text
/
├── apps/
│   ├── api/                 # FastAPI (Python 3.12), SQLAlchemy 2.x, OR-Tools CP-SAT, Alembic, Pytest
│   └── web/                 # Next.js (App Router, TypeScript), Tailwind CSS, Playwright E2E
├── data/
│   └── seeds/               # Katalog awal: 25 bahan pangan Indonesia, harga regional, 25 gerakan latihan
├── docs/
│   ├── PRD.md               # Dokumen Spesifikasi Produk (PRD v2.0 AI-Buildable Edition)
│   ├── API.md               # Ringkasan kontrak endpoint OpenAPI 3.1 otomatis
│   ├── DECISIONS.md         # Catatan keputusan arsitektur & kalibrasi solver CP-SAT
│   └── RUNBOOK.md           # Panduan operasional, seed, & penanganan insiden
├── scripts/
│   ├── gen_openapi.py       # Generator OpenAPI JSON, docs/API.md, dan tipe TypeScript
│   └── gen-types.sh         # Skrip sinkronisasi kontrak tipe API -> Web
├── docker-compose.yml       # Orkestrasi PostgreSQL 16, API, Web, dan Ollama (opsional)
└── Makefile                 # Target standar: up, down, seed, gen-types, test, lint
```

---

## Cara Menjalankan Secara Lokal

### 1. Menggunakan Docker Compose (Direkomendasikan)
```bash
cp .env.example .env
docker compose up --build
```
- Aplikasi Web: `http://localhost:3000`
- Dokumentasi API: `http://localhost:8000/docs`

### 2. Menjalankan Tanpa Docker (Pengembangan Lokal)

**Backend (`apps/api`):**
```bash
cd apps/api
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend (`apps/web`):**
```bash
cd apps/web
npm install
npm run dev
```

### Akun Awal (Seed Otomatis)
- **Demo User**: `demo@fitbudget.local` / `DemoFitBudget123!`
- **Admin**: `admin@fitbudget.local` / `AdminFitBudget123!`

---

## Pengujian & Verifikasi Kualitas

**Backend (Unit, Property-Based Hypothesis, Integrasi API, Keamanan, Guardrail AI, Linter):**
```bash
cd apps/api
uv run ruff check .
uv run pytest --cov=app/services/nutrition --cov-report=term-missing
```

**Frontend (Unit Test, Typecheck, Production Build):**
```bash
cd apps/web
npm test
npm run typecheck
npm run build
```

**Sinkronisasi Skema OpenAPI & Tipe TypeScript:**
```bash
cd apps/api
uv run python ../../scripts/gen_openapi.py
```
