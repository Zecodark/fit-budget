# Supabase FitBudget

Proyek: `fit-budget` (`rgumjxmekqdetnghxbms`), region `ap-southeast-2`.

Backend FastAPI menggunakan PostgreSQL Supabase melalui SQLAlchemy/psycopg.
Login dan sesi tetap dikelola FitBudget. Tabel `public.users` berbeda dari
`auth.users`; jangan menghubungkan frontend langsung ke tabel ini.

## Koneksi lokal

1. Buka [Connect](https://supabase.com/dashboard/project/rgumjxmekqdetnghxbms?showConnect=true),
   pilih **Session pooler** (port 5432), lalu salin URI PostgreSQL.
2. Simpan sebagai `DATABASE_URL` di `.env` root proyek. Ganti placeholder password
   dengan password database dan percent-encode karakter khususnya. URI
   `postgresql://` otomatis menggunakan driver psycopg. Tambahkan `?sslmode=require`
   (atau `&sslmode=require` bila URI sudah memiliki query parameter).
3. Isi juga `SECRET_KEY` acak dan kredensial admin milik sendiri jika menjalankan seed.
   Jangan commit `.env` atau mengirim password ke chat.
4. Jalankan dari `apps/api`:

```powershell
uv run python -m app.core.check_db
uv run alembic upgrade head
uv run python -m app.core.seed
uv run uvicorn app.main:app --reload --port 8000
```

Frontend tetap mengakses `/api/v1` melalui FastAPI. Untuk menjalankan kontainer
tanpa menyalakan PostgreSQL lokal:

```powershell
docker compose up --build --no-deps api web
```

## Struktur dan akses

`schema.sql` berisi 24 tabel aplikasi, indeks, RLS, serta pencabutan hak akses
`anon`/`authenticated`/`PUBLIC`. Koneksi backend menggunakan kredensial PostgreSQL
dan otorisasi aplikasi yang sudah ada. Tidak ada policy Data API untuk browser;
Advisor `RLS Enabled No Policy` pada tabel ini bersifat informasional dan sesuai
dengan akses melalui backend saja.

`seed.sql` memuat katalog pangan, harga, alias, dan latihan; tidak membuat akun
admin/demo. File schema hanya untuk database baru, bukan untuk dijalankan ulang
pada database berisi data. Schema dan katalog sudah diterapkan melalui konektor
Supabase; file ini disimpan sebagai salinan yang dapat diperiksa.

Untuk mengekspor ulang dari model dan CSV sumber (tidak mengakses Supabase),
jalankan dari `apps/api`:

```powershell
uv run python ../../scripts/export_supabase_bootstrap.py
```

Perubahan struktur berikutnya tetap harus dibuat sebagai migrasi Alembic dan
mempertahankan RLS serta pembatasan akses tabel baru.
