# Architectural & Engineering Decisions (`DECISIONS.md`)

Dokumen ini mencatat seluruh keputusan arsitektural, kalibrasi solver, serta detail implementasi selama pembangunan **FitBudget AI v2.0** sesuai **PRD §0.1 Rule 6**.

---

## 1. Pemisahan Mesin Deterministik dan Lapisan LLM (PRD §0.1, §5.7)
- **Keputusan**: Seluruh kalkulasi energi (REE, TDEE, penyesuaian tujuan, batas lantai energi), makronutrisi (protein, lemak, karbohidrat, serat), harga dan daftar belanja, penjadwalan latihan mingguan, serta agregasi dashboard diimplementasikan sebagai fungsi murni deterministik (`Decimal` / integer) di backend Python.
- **Alasan**: Mencegah halusinasi numerik dari model bahasa (LLM) pada domain gizi, anggaran, dan kesehatan.
- **Konsekuensi**:
  - LLM hanya menerima konteks yang telah dianonimkan (`build_ai_context` tidak pernah menyertakan `email`, `full_name`, `password_hash`, atau `user_id`).
  - Setiap angka pada keluaran teks LLM diverifikasi terhadap himpunan angka izin (`extract_allowed_numbers_from_context`) dengan toleransi $\le 1\%$ atau $\le 1{,}0$ satuan.
  - Usulan perubahan rencana (`change_budget`, `exclude_food`, `reschedule_workout`) disimpan sebagai baris `ai_proposals` berstatus `pending` dan baru dieksekusi oleh mesin deterministik setelah pengguna menekan tombol konfirmasi (`POST /api/v1/ai/proposals/{id}/confirm`).

---

## 2. Kalibrasi Solver OR-Tools CP-SAT untuk Reprodusibilitas & Latensi (PRD §5.3)
- **Keputusan**:
  - Mengonversi seluruh besaran gizi dan harga per langkah sajian (`step_g = 25g`) ke bilangan bulat berskala tetap (`cost_idr` dalam Rupiah bulat, energi dalam `kcal * 10`, makronutrisi dalam `gram * 100`).
  - Mengatur parameter solver CP-SAT: `num_search_workers = 1`, `random_seed = 42`, dan `max_deterministic_time = 0.25` detik per pemanggilan solver harian/tahap.
  - Memverifikasi ulang seluruh solusi CP-SAT menggunakan pemeriksa independen berbasis `Decimal` (`app/services/optimizer/checker.py:check_day`).
- **Alasan**:
  - Tanpa batas waktu deterministik (`max_deterministic_time`), CP-SAT yang dibatasi oleh *wall-clock timeout* dapat menghasilkan variasi solusi kecil saat beban CPU berubah dan menghabiskan waktu penuh untuk membuktikan celah optimalitas 0,0% pada model bilangan bulat.
  - Dengan `num_search_workers = 1`, `random_seed = 42`, dan `max_deterministic_time = 0.25`, optimasi rencana 7 hari selesai dalam $\approx 2{,}5 - 3{,}5$ detik (di bawah target p95 $< 5$ detik) dan menghasilkan rencana yang 100% identik (*bit-for-bit reproducible*) pada input yang sama (diverifikasi oleh pengujian `O4` dan `O5`).

---

## 3. Strategi Penanganan Infeasibilitas 3-Tahap (PRD §5.3.7)
- **Keputusan**:
  - **Stage 1 (`FEASIBLE`)**: Memenuhi seluruh kendala keras C1–C8 dan meminimalkan biaya + penalti deviasi energi + penalti pengulangan mingguan.
  - **Stage 2 (`PARTIAL`)**: Melonggarkan kendala komposisi/variasi/rentang energi secara terukur dengan bobot penalti leksikografis (`w_E_under = 500`, `w_P_under = 2000`, `w_comp = 50000`, `w_var = 20000`) sambil tetap menjaga batas keras anggaran harian C1 (`cost <= B`) dan batas atas protein C4 (`protein <= 1.30 * P_target`).
  - **Stage 3 (`INFEASIBLE`)**: Jika anggaran terlalu rendah (mis. Rp 10.000/hari untuk target 2.200 kkal), sistem menghitung anggaran harian minimum yang dibutuhkan (`compute_minimum_budget_idr`) dengan meminimalkan biaya pada kendala gizi ketat tanpa batas anggaran, serta menghasilkan rencana upaya terbaik (*best-effort*) di bawah anggaran pengguna beserta daftar kendala yang belum terpenuhi (`unmet_constraints`).
- **Alasan**: Memberikan informasi transparan dan dapat ditindaklanjuti kepada pengguna tanpa pernah mengklaim `"target terpenuhi"` saat status `PARTIAL` atau `INFEASIBLE`.

---

## 4. Portabilitas Skema Basis Data PostgreSQL 16 & SQLite Pengujian
- **Keputusan**: Menggunakan SQLAlchemy 2.x dengan tipe ORM portabel dan pengaktifan `PRAGMA foreign_keys=ON` otomatis pada koneksi SQLite, disertai migrasi Alembic lengkap (`apps/api/alembic/versions/0001_initial.py`) untuk PostgreSQL 16 di lingkungan produksi/kontainer.
- **Alasan**: Memungkinkan seluruh suite pengujian unit, properti (Hypothesis), integrasi API, keamanan, dan evaluasi AI berjalan cepat dan terisolasi tanpa ketergantungan layanan eksternal, sekaligus mempertahankan kesesuaian penuh dengan PostgreSQL 16 pada deployment Docker Compose.

---

## 5. Keamanan Sesi, CSRF, & Privasi Data (UU PDP)
- **Keputusan**:
  - Menggunakan *password hashing* `argon2id` (`argon2-cffi`).
  - Menyimpan sesi autentikasi pada cookie `fb_session` (`HttpOnly`, `SameSite=Lax`, masa berlaku 7 hari) dan menerapkan pemeriksaan `Origin` + `Content-Type: application/json` pada endpoint mutasi untuk mencegah serangan CSRF.
  - Mengimplementasikan penguncian akun sementara selama 15 menit setelah 5 kali kegagalan masuk berturut-turut (`ACCOUNT_LOCKED`).
  - Menyediakan ekspor portabilitas data (`GET /api/v1/account/export`) dan penghapusan akun berjenjang (`DELETE /api/v1/account`) sesuai prinsip UU No. 27 Tahun 2022 (UU PDP).

