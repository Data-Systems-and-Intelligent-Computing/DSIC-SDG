# H6 Jalur B - Skor kepercayaan sumber untuk B2

H6 Jalur B membekukan skor yang kelak dipakai oleh perlakuan B2 untuk memilih tepat satu sumber
pada setiap `cell_id`. Skor ini mengadaptasi pola *single-source trust selection* sebagai
pembanding, bukan menaksir kebenaran statistik. Semua kandidat berasal dari kanal resmi BPS dan
tetap sah sebagai vintage; istilah “kepercayaan” di sini hanya berarti kecocokan operasional
sumber untuk perlakuan B2.

## Unit yang dinilai

Tiga `source_id` pada fixture H6 dinilai sebagai tiga instance sumber-rilis: publikasi TPB 2024,
publikasi TPB 2025, dan snapshot WebAPI 2026. Pembedaan dua publikasi diperlukan karena keduanya
adalah artefak beku dengan tanggal dan checksum berbeda. Skor dibekukan pada semesta 14
`cell_id` dan 38 observasi nyata H6; H7 Jalur B nanti harus memakai skor ini tanpa melatih ulang
dari hasil konflik.

## Rumus yang dibekukan

Semua dimensi berada pada rentang 0–1. Skor adalah jumlah `weight × dimension_value`.

| Dimensi | Bobot | Derivasi |
|---|---:|---|
| Otoritas resmi | 0,30 | 1 untuk publisher BPS yang lolos registry |
| Provenance termanifestasi | 0,20 | proporsi baris dengan manifest, checksum artefak, dan locator |
| Konteks semantik | 0,20 | 1 untuk nilai+definisi; 0,75 untuk nilai tanpa definisi di registry |
| Keterstrukturan langsung | 0,15 | 1 untuk JSON/CSV; 0,75 untuk PDF |
| Cakupan sel workload | 0,15 | jumlah sel sumber dibagi 14 sel H6 |

Bobot tidak dipelajari dari nilai observasi dan tidak diklaim sebagai kalibrasi kualitas BPS.
Bobot adalah definisi perlakuan yang ditetapkan sebelum implementasi B2 agar pembanding dapat
diulang. Nilai, kesepakatan antarsumber, keluarga sebab, tingkat bukti, dan identitas pemenang
secara eksplisit dilarang menyumbang skor.

Jika skor sama, urutannya adalah tanggal vintage terbaru, lalu `source_id`, lalu
`observation_id`. Tanggal vintage hanya menjadi tie-break dan tidak memberi poin. Aturan ini
mencegah hasil bergantung pada urutan baris input.

## Hasil skor

| Rank | Sumber-rilis | Cakupan | Skor |
|---:|---|---:|---:|
| 1 | TPB 2025 | 14/14 | 0,962500 |
| 2 | TPB 2024 | 14/14 | 0,962500 |
| 3 | WebAPI 2026 | 10/14 | 0,907143 |

Kedua publikasi mempunyai skor sama karena atribut registry dan cakupannya sama; tie-break tanggal
menempatkan TPB 2025 lebih dahulu. WebAPI mendapat keuntungan format terstruktur, tetapi skor
konteks semantik dan cakupan fixture lebih rendah. Ini tidak berarti angka WebAPI kurang benar.

## Preview diagnostik B2

Preview memilih satu observasi untuk setiap 14 sel tanpa menulis tabel B2. TPB 2025 terpilih pada
seluruh sel. Pada empat sel dua-vintage, pilihan itu sekaligus merupakan vintage terbaru. Pada
sepuluh sel tiga-vintage, pilihan mengabaikan snapshot WebAPI yang lebih baru; kesepuluh nilainya
berbeda dari pilihan TPB 2025.

Temuan ini bersifat diagnostik dan tidak dipakai kembali sebagai fitur skor. Ia menunjukkan
trade-off yang memang perlu diuji oleh B2: pemilihan sumber tunggal bisa konsisten dengan aturan
kepercayaan tetapi tetap membuang perubahan vintage resmi yang bermakna.

## Invariant dan batas interpretasi

Enam invariant lulus: bobot berjumlah satu, ketiga sumber lolos eligibility, semua role/format
terpetakan, tidak ada kebocoran hasil, tepat satu pemenang per sel, dan preview dipisahkan dari
skor. Karena fixture hanya memuat tiga instance sumber-rilis, angka skor tidak boleh digeneralisasi
sebagai peringkat seluruh produk BPS. Perubahan bobot atau pemetaan harus menghasilkan versi
kontrak eksperimen baru.

## Artefak dan reproduksi

- `contracts/h6b-source-trust.json`: dimensi, bobot, eligibility, larangan kebocoran, dan tie-break;
- `results/processed/h6b-source-trust-scores.csv`: komponen serta ranking tiga sumber-rilis;
- `results/processed/h6b-selection-preview.csv`: pilihan diagnostik untuk 14 sel;
- `results/processed/h6b-source-trust-validation.csv`: hasil enam invariant;
- `data/manifests/h6b-source-trust.json`: checksum input-output;
- `tests/unit/test_h6b.py`: uji determinisme, formula, tie-break, dan kebocoran hasil.

Jalankan:

```bash
make h6b-run
make test
```

Eksekusi diverifikasi pada 9 September 2026 di `sigerciv@34.128.67.92` setelah VM menarik commit
`bc6fd31` dari `main`. Marker `H6B_VERIFY|3|14|4|10|10|frozen` membuktikan tiga skor sumber, 14
pilihan sel, empat pilihan yang sama dengan vintage terbaru, sepuluh pilihan vintage lebih lama,
sepuluh nilai terpilih yang berbeda dari nilai latest, dan status skor `frozen`. Seluruh 40 tes
yang dapat dijalankan di VM lulus; satu tes ekstraksi PDF H3 dilewati karena payload mentah tidak
disimpan di Git. Clone VM tetap bersih setelah reproduksi.
