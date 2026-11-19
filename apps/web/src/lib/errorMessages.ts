/**
 * Mapping kode error backend (PRD §5.9) ke pesan Bahasa Indonesia & utilitas format Indonesia (PRD §2.5, §7.3).
 */

export const ERROR_MESSAGES: Record<string, string> = {
  VALIDATION_ERROR: "Input tidak valid. Periksa kembali nilai yang Anda masukkan.",
  UNAUTHORIZED: "Sesi tidak valid atau Anda belum masuk. Silakan masuk terlebih dahulu.",
  UNAUTHENTICATED: "Sesi tidak valid atau Anda belum masuk. Silakan masuk terlebih dahulu.",
  FORBIDDEN: "Anda tidak memiliki izin untuk mengakses fitur ini.",
  CONSENT_REQUIRED: "Persetujuan pemrosesan data diperlukan sebelum melanjutkan.",
  PROFESSIONAL_CONSULT_REQUIRED:
    "Kondisi Anda memerlukan konsultasi tenaga kesehatan profesional; pembuatan rencana otomatis dinonaktifkan.",
  AI_CONSENT_REQUIRED:
    "Penyedia AI cloud memerlukan persetujuan eksplisit pada Pengaturan (Consent AI Cloud).",
  AI_CLOUD_CONSENT_REQUIRED:
    "Penyedia AI cloud memerlukan persetujuan eksplisit pada Pengaturan (Consent AI Cloud).",
  NOT_FOUND: "Data yang diminta tidak ditemukan.",
  EMAIL_ALREADY_REGISTERED: "Alamat email sudah terdaftar. Silakan masuk atau gunakan email lain.",
  INVALID_CREDENTIALS: "Email atau kata sandi tidak sesuai.",
  ACCOUNT_LOCKED: "Akun dikunci sementara karena terlalu banyak percobaan masuk yang gagal.",
  PLAN_VERSION_CONFLICT:
    "Rencana telah diperbarui di sesi lain. Muat ulang halaman lalu ulangi perubahan Anda.",
  SESSION_CONFLICT: "Sudah ada sesi latihan lain pada tanggal tujuan tersebut.",
  PROPOSAL_EXPIRED: "Usulan asisten AI telah kedaluwarsa (lebih dari 30 menit).",
  PROPOSAL_INVALID: "Usulan perubahan tidak valid atau tidak dapat diterapkan.",
  NO_FEASIBLE_PLAN:
    "Tidak ditemukan kombinasi menu yang mencapai seluruh target gizi dalam batas budget harian ini.",
  OPTIMIZER_NO_CATALOG_FOODS:
    "Tidak ada bahan pangan di katalog yang cocok dengan filter diet atau alergi Anda.",
  GOAL_NOT_ALLOWED:
    "Tujuan penurunan berat badan tidak diizinkan untuk indeks massa tubuh (BMI) di bawah 18,5.",
  AI_RATE_LIMIT:
    "Batas penggunaan asisten AI per jam telah tercapai. Fitur non-AI tetap dapat digunakan sepenuhnya.",
  RATE_LIMITED:
    "Batas permintaan per jam telah tercapai. Silakan coba kembali beberapa saat lagi.",
  INTERNAL_ERROR: "Terjadi kesalahan internal pada server. Silakan coba kembali.",
  AI_UNAVAILABLE:
    "Asisten AI sedang tidak tersedia. Seluruh fitur kalkulator, menu, jadwal, dan pencatatan tetap aktif.",
  AI_OUTPUT_REJECTED:
    "Respons asisten AI ditolak oleh pemeriksa keamanan angka dan konten.",
  PRICE_CHANGE_CONFIRMATION_REQUIRED:
    "Perubahan harga melebihi 50% dan memerlukan konfirmasi eksplisit admin.",
  OPTIMIZER_TIMEOUT: "Penyusunan menu melebihi batas waktu komputasi. Silakan coba kembali.",
  CONFLICT: "Permintaan bertentangan dengan status data saat ini.",
};

export function getErrorMessage(code?: string, serverMessage?: string): string {
  if (serverMessage && serverMessage.trim().length > 0) {
    return serverMessage;
  }
  if (code && ERROR_MESSAGES[code]) {
    return ERROR_MESSAGES[code];
  }
  return "Terjadi kesalahan yang tidak terduga.";
}

const idrFormatter = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const dec1Formatter = new Intl.NumberFormat("id-ID", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

const intFormatter = new Intl.NumberFormat("id-ID", {
  maximumFractionDigits: 0,
});

export function formatIdr(amount: number | null | undefined): string {
  return idrFormatter.format(Math.round(Number(amount ?? 0)));
}

export function formatDec1(val: number | null | undefined): string {
  return dec1Formatter.format(Number(val ?? 0));
}

export function formatInt(val: number | null | undefined): string {
  return intFormatter.format(Math.round(Number(val ?? 0)));
}

export const WEEKDAY_NAMES_ID = [
  "Senin",
  "Selasa",
  "Rabu",
  "Kamis",
  "Jumat",
  "Sabtu",
  "Minggu",
] as const;

export const SLOT_LABELS_ID: Record<string, string> = {
  breakfast: "Sarapan",
  lunch: "Makan Siang",
  dinner: "Makan Malam",
  snack: "Selingan",
};

export function currentMondayIso(d: Date = new Date()): string {
  const day = d.getDay(); // 0=Sun..6=Sat
  const diff = day === 0 ? -6 : 1 - day;
  const mon = new Date(d.getFullYear(), d.getMonth(), d.getDate() + diff);
  const yyyy = mon.getFullYear();
  const mm = String(mon.getMonth() + 1).padStart(2, "0");
  const dd = String(mon.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function todayIso(d: Date = new Date()): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}
