# Paket Data Artikel — Vintage-Aware Reconciliation of Official SDG Indicators

Folder ini mengumpulkan semua angka dan tabel hasil eksperimen H1–H10A yang dibutuhkan untuk menulis
artikel. Isinya dibentuk otomatis dari hasil pipeline yang sudah diverifikasi. Jangan mengetik ulang
atau mengedit angka secara manual.

## 1. Di mana data penelitian tersimpan

| Jenis | Lokasi | Keterangan |
|---|---|---|
| **Paket data artikel** (folder ini) | `papers/vintage_reconciliation/data/` | 27 tabel salinan, 3 tabel turunan, 70 angka kunci; laptop dan GitHub |
| Seluruh hasil olahan H1–H10 | `results/processed/` | laptop dan GitHub; sumber folder ini |
| Manifest checksum setiap tahap | `data/manifests/` | laptop dan GitHub |
| Data mentah pengukuran H10A | `results/raw/h10/h10a-20260911/` | laptop dan GitHub |
| **Bahan mentah sumber** (payload WebAPI BPS, PDF TPB) | `data/raw/` | **hanya di laptop**; tidak masuk Git |
| Tabel Iceberg di VM | VM `praktikum-sd` | dapat dibangun ulang dari CSV; tidak menyimpan angka yang unik |

VM tidak menyimpan hasil yang tidak ada di laptop. Semua angka artikel dapat dibentuk ulang dari
repository ini tanpa VM.

## 2. Isi folder `data/`

```text
data/
├── angka-kunci.csv          70 angka kunci + sumber + cara penurunan  ← mulai dari sini
├── bundle-manifest.json     checksum setiap berkas dan manifest tahap asalnya
├── p1-karakterisasi/        P1: bentuk dan sebab ketidaksesuaian antarsumber (H1–H5)
├── p2-representasi/         P2: vintage sebagai dimensi eksplisit (H6, H9A)
├── p3-ongkos/               P3: kerja penghitungan ulang dan ruang fisik (H9A, H9B, H10A)
├── p4-reproducibility/      P4: kemampuan memanggil ulang angka terbit (H7–H10A)
└── pembahasan-b2/           bahan pembahasan perlakuan B2 / Trust Your Friend (H6B, H7B)
```

Setiap tabel salinan identik byte demi byte dengan berkas di `results/processed/`, dan checksum-nya
dicocokkan dengan manifest tahapnya sebelum disalin. Deskripsi setiap berkas tersedia di
`bundle-manifest.json` dan di `config/article/bundle_tables.csv`.

## 3. Cara memakai angka di naskah

1. Ambil angka dari `data/angka-kunci.csv` berdasarkan `metric_id`. Jangan menyalin dari dokumen lain.
2. Kolom `source_file` dan `derivation` menunjukkan dari mana dan bagaimana angka dihitung. Pakai
   keduanya saat reviewer bertanya.
3. Rasio ditulis dengan empat desimal (misalnya `0.7805`). Di naskah berbahasa Inggris, bulatkan
   secara konsisten, misalnya 78,05% menjadi 78.1%.
4. Setiap angka ruang (byte) harus disertai keterangan "fixture 14 sel, median tiga repetisi, VM
   2 vCPU" (lihat §6).

### Peta angka ke bagian naskah

| Bagian naskah | Angka kunci (`metric_id`) | Tabel pendukung |
|---|---|---|
| Hasil P1 — karakterisasi | `p1_indicator_*`, `p1_main_*`, `p1_release_*`, `p1_confirmed_core_*`, `p1_*_observed`, `p1_revision_traces` | `p1-distribusi-sebab.csv` (usulan Tabel: sebab ketidaksesuaian), `h3-discrepancies.csv`, `h5-revision-traces.csv` |
| Metode / P2 — representasi | `p2_vintages`, `p2_observations`, `p2_stable_cells`, `p2_b3_asof_rows` | `h6-release-vintages.csv`, `h6-indicator-observations.csv` |
| Hasil P3 — ongkos | `p3_recompute_ratio`, `p3_*_bytes_median`, `p3_b3_store_*`, `p3_b3_over_b1_bytes` | `h10-storage-by-treatment.csv` (usulan Tabel: ruang), `h9-b3-arrival-catalog.csv`, `h9b-route-executions.csv` |
| Hasil P4 — reproducibility | `p4_*_success_rate`, `p4_*_recalled_after_restart`, `p4_lineage_*` | `h9c-reproducibility-table.csv` (usulan Tabel: reproducibility), `h9c-reproducibility-figure-data.csv` (data gambar) |
| Pembahasan — B2 | `b2_trust_score_*`, `b2_selected_non_latest`, `b2_propagation_*` | `p3-propagasi-revisi.csv`, `h7b-b2-discarded-candidates.csv` |

## 4. Ringkasan angka utama

Tabel ini hanya ringkasan. Angka otoritatif ada di `angka-kunci.csv`, dan test
`tests/unit/test_article.py` memastikan angka inti tetap sama.

**P1.** Dari 35 kandidat indikator, 14 berstatus verified. Perbandingan nasional–provinsi mencakup
1.435 sel, dengan 33 sel berbeda, dan perbandingan antarrilis menemukan 8 perbedaan pada 3 domain.
Dari 123 kejadian, 96 (0,7805) mempunyai sebab inti terkonfirmasi: 82 granularitas, 13 vintage, dan
1 metodologi. Proporsinya menjadi 0,8455 bila kandidat ikut dihitung. Ada 14 jejak revisi dengan 38
baris vintage.

**P2.** Workload nyata terdiri atas 3 vintage, 38 observasi, dan 14 sel stabil. B3 merekonstruksi
42 baris state per rilis yang sama persis dengan snapshot B1.

**P3.** Pada tiga rilis nyata, B3 menghitung ulang 38 dari 42 evaluasi sel (0,9048).

| Perlakuan | Ruang fisik (median) | Data | Metadata |
|---|---:|---:|---:|
| B0 overwrite | 95.898 B | 32.656 B | 63.242 B |
| B1 snapshot penuh | 190.261 B | 101.486 B | 88.775 B |
| B2 sumber tunggal | 64.077 B | 38.311 B | 25.766 B |
| B3 vintage-aware | 240.884 B | 117.603 B | 123.281 B |
| — store B3 saja | 146.352 B | 80.880 B | 65.472 B |

**P4.**

| Perlakuan | Tingkat keberhasilan (38 angka terbit) | Terpanggil setelah restart katalog |
|---|---:|---:|
| B0 | 0,3684 | 14 |
| B1 | 1,0000 | 38 |
| B2 | 0,3684 | 14 |
| B3 | 1,0000 | 38 |

Lineage mencakup 152 path dengan kelengkapan 1,0000.

**Pembahasan B2.** Skor beku sumber: TPB 2025 = TPB 2024 = 0,962500, dan WebAPI = 0,907143. Pada
data nyata, 10 dari 14 sel B2 menyajikan nilai yang bukan vintage terbaru. Pada revisi tersuntik,
tingkat propagasi revisi B2 hanya 0,2857 (8/28), sedangkan B0, B1, dan B3 mencapai 1,0000.

## 5. Arah pembahasan yang disarankan

- **B3 bukan pemenang ruang pada fixture ini.** Ongkos terbesarnya berasal dari tabel serving yang
  dimaterialisasi. Store vintage-nya sendiri 23% lebih kecil daripada B1. Laporkan B3 dengan dan
  tanpa tabel serving.
- **B1 dan B3 sama-sama mereproduksi 38/38 angka dengan mekanisme berbeda.** B1 bergantung pada
  snapshot dan metadata katalog, sedangkan B3 pada kunci `(cell_id, vintage_id)`. Insiden katalog
  in-memory (11 September 2026) adalah contoh nyata risiko pertama.
- **B2 menahan revisi secara diam-diam** bila revisi datang dari sumber berskor lebih rendah. Bahas
  ini sebagai sifat kelas kebijakan pemilihan satu sumber, bukan kesalahan implementasi, dan ukur
  dengan tingkat propagasi revisi.
- **Titik impas P3 belum terjawab.** Workload nyata hampir menyentuh semua sel, sehingga jawabannya
  menunggu sweep revisi tersuntik H11 serta pengukuran waktu.

## 6. Batas klaim yang wajib ikut bersama angka

- Semua hasil berlaku untuk fixture 38 observasi / 14 sel, bukan untuk seluruh indikator BPS.
- Pada tabel sekecil ini, byte didominasi ongkos tetap metadata Iceberg. **Jangan ekstrapolasi ke
  skala besar.**
- Byte diukur pada VM 2 vCPU / 7,7 GiB yang dinyatakan untuk pengukuran ruang. **Waktu belum diukur.**
- Hasil H9B adalah eksekusi logis profil validasi (bukan freeze H10). Baris logis bukan byte.
- Gate G2 dan G3 belum lolos.

Rincian setiap tahap: `docs/research/` dan panduan audit `papers/teknis-lab/Readme.md`.

## 7. Membentuk ulang paket ini

```bash
make article-bundle   # verifikasi checksum semua sumber, salin tabel, hitung angka kunci
make test             # termasuk test_article.py yang mengunci angka inti
```

Paket dibentuk ulang setiap kali hasil tahap berubah. Bila salah satu sumber tidak cocok dengan
manifest tahapnya, perintah berhenti dan tidak menulis angka baru. Tabel yang dihapus dari
`config/article/bundle_tables.csv` juga ikut dihapus dari folder ini.

## 8. Cadangan bahan mentah sumber (`data/raw`)

`data/raw/` hanya ada di laptop. Snapshot WebAPI 8 September 2026 **tidak dapat ditarik ulang
persis**, karena menarik ulang berarti membuat vintage baru. PDF TPB masih dapat diunduh ulang dari
katalog BPS.

```bash
make raw-backup
```

Perintah ini memverifikasi setiap berkas terhadap checksum di manifest, lalu membuat:

- `backups/data-raw-YYYYMMDD.tar.gz` — arsip `data/raw/`;
- `backups/data-raw-YYYYMMDD.SHA256SUMS` — daftar checksum 52 berkas.

Folder `backups/` tidak masuk Git. **Salin kedua berkas ke minimal satu tempat lain**, misalnya
Google Drive tim atau disk eksternal. Untuk memeriksa arsip setelah dipulihkan:

```bash
tar -xzf data-raw-YYYYMMDD.tar.gz          # dijalankan di root repository
shasum -a 256 -c data-raw-YYYYMMDD.SHA256SUMS
```

Cadangan pertama sudah dibuat pada 11 September 2026 (`backups/data-raw-20260911.tar.gz`, 39 MB).
Ke-52 berkasnya lolos pemeriksaan checksum setelah diekstrak ulang.
