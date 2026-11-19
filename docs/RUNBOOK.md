# FitBudget AI — Runbook Operasional (`RUNBOOK.md`)

Panduan operasional untuk menjalankan, mengelola katalog, memantau kesehatan layanan, dan menangani insiden pada **FitBudget AI v2.0**.

---

## 1. Menjalankan Layanan dengan Docker Compose

### Mode Standar (Tanpa GPU / Penyedia AI `none`, `fake`, atau `gemini`)
```bash
cp .env.example .env
docker compose up --build -d
```
- **Web UI (Next.js)**: `http://localhost:3000`
- **API (FastAPI + OpenAPI)**: `http://localhost:8000/api/v1/health`
- **PostgreSQL 16**: `localhost:5432`

### Mode AI Lokal dengan Ollama (`profile: ai`)
```bash
AI_PROVIDER=ollama docker compose --profile ai up --build -d
docker exec -it $(docker compose ps -q ollama) ollama pull qwen2.5:3b-instruct
```

---

## 2. Migrasi Basis Data & Seed Katalog Awal

Saat kontainer `api` dijalankan, aplikasi otomatis menginisialisasi skema dan memuat data awal (`data/seeds/foods.csv`, `data/seeds/food_prices.csv`, `data/seeds/exercises.csv`) serta membuat akun:
- **Admin**: `admin@fitbudget.local` / `AdminFitBudget123!`
- **Demo User**: `demo@fitbudget.local` / `DemoFitBudget123!`

Untuk menjalankan migrasi Alembic dan seed secara manual di lingkungan lokal:
```bash
cd apps/api
uv run alembic upgrade head
uv run python -m app.core.seed
```

---

## 3. Pembaruan Harga Pangan (Append-Only) & Audit

Harga bahan pangan pada tabel `food_prices` bersifat **append-only** agar rencana makan yang telah dikonfirmasi pengguna tidak berubah secara retroaktif.

1. Masuk menggunakan akun admin (`admin@fitbudget.local`).
2. Buka halaman `/admin/prices`.
3. Untuk impor CSV massal:
   - Jalankan **1. Pratinjau (Dry-Run)** terlebih dahulu (`POST /api/v1/admin/prices/import?dry_run=true`).
   - Jika terdapat perubahan harga $> 50\%$, sistem akan mengembalikan peringatan dan menolak penerapan kecuali opsi **Konfirmasi perubahan harga besar (> 50%)** (`confirm_large_changes=true`) dicentang.
   - Setiap perubahan wajib menyertakan alasan (`reason`) yang dicatat permanen pada `/admin/audit`.

---

## 4. Penanganan Gangguan Penyedia AI (Degradasi Anggun / Non-AI Mode)

Jika penyedia AI eksternal/lokal mengalami gangguan atau kuota habis:
1. Ubah variabel lingkungan `AI_PROVIDER=none` pada `.env` lalu mulai ulang layanan `api`.
2. Seluruh fitur kalkulator gizi, optimasi rencana makan CP-SAT, penjadwalan latihan, pencatatan harian, dan dashboard tetap berjalan 100% normal.
3. Halaman `/chat` secara otomatis menampilkan pita pemberitahuan mode Non-AI dan mengarahkan pengguna ke kontrol deterministik langsung.

---

## 5. Pemeriksaan Kesehatan & Diagnostik

- **Healthcheck Endpoint**: `GET /api/v1/health` mengembalikan status koneksi basis data (`db: "ok"`), penyedia AI aktif (`ai_provider`), serta versi aplikasi.
- **Correlation ID**: Setiap respons menyertakan header `X-Request-ID`. Gunakan ID ini untuk menelusuri log terstruktur JSON pada stdout layanan `api`.
- **Verifikasi Privasi Log**: Log aplikasi tidak pernah mencatat `password`, `email`, atau `full_name` pengguna (diverifikasi secara otomatis oleh pengujian `S7`).

