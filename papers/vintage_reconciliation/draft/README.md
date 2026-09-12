# Draf Naskah — Vintage-Aware Reconciliation of Official SDG Indicators

Folder ini menampung draf bagian naskah yang ditulis Jalur C. Draf ditulis dalam bahasa Indonesia
lebih dahulu agar alur argumennya dapat diperiksa bersama, lalu diterjemahkan ke bahasa Inggris
menjelang submit. Target venue tetap jurnal Q1 Scopus sesuai §7 README utama.

## Isi

| Berkas | Bagian naskah | Ditulis |
|---|---|---|
| `01-pendahuluan.md` | Pendahuluan | H10 Jalur C, 12 September 2026 |
| `02-kedudukan-terhadap-literatur.md` | Kedudukan terhadap Literatur | H10 Jalur C, 12 September 2026 |
| `03-kerangka-tabel-hasil.md` | kerangka tabel dan gambar bagian Hasil | H11 Jalur A dan C, 13 September 2026 |
| `04-metode.md` | Metode | H12 Jalur A dan C, 13 September 2026 |

Versi bahasa Inggris kedua bagian tersebut, dalam format Elsevier CAS kolom ganda, ada di
[`../manuscript/`](../manuscript/README.md) dan dapat dikompilasi dengan `make manuscript`.

Metode sudah ditulis pada H12 dan memuat bagian ancaman terhadap validitas, termasuk tiga
keterbatasan yang ditemukan sendiri oleh sweep H11: kebijakan pemeliharaan snapshot ikut terukur di
dalam angka waktu, semesta sweep hanya dilayani satu sumber, dan besaran perubahan nilai tidak
divariasikan. Hasil, Pembahasan, dan Kesimpulan belum ditulis; Hasil dijadwalkan pada H15 sesuai
§6.5 README utama, dan bentuk tabel serta gambarnya sudah dibekukan pada H11 di
`03-kerangka-tabel-hasil.md`, sebelum angka sweep ditafsirkan.

## Aturan penulisan yang dipakai

1. **Angka tidak diketik ulang.** Setiap angka pada draf diambil dari
   `papers/vintage_reconciliation/data/angka-kunci.csv` melalui `metric_id`. Setiap berkas draf
   ditutup tabel pemetaan dari kalimat ke `metric_id` agar angkanya dapat diperiksa tanpa membuka
   pipeline.
2. **Klaim yang belum ada buktinya ditandai, bukan ditulis halus.** Penanda
   `[Sumber belum mendukung klaim ...]` dipakai pada tempat yang masih menunggu hasil, misalnya
   titik impas P3 yang baru tersedia setelah sweep H11.
3. **Sitasi hanya untuk sumber yang sudah diverifikasi.** Status verifikasi diambil dari
   `docs/research/related-work.md`. Sumber berstatus `metadata` boleh disitasi, tetapi statusnya
   dicatat di tabel sumber pada akhir berkas. Sumber yang nama penulisnya belum tercatat disitasi
   memakai venue, dan daftar yang perlu dilengkapi ada di bagian akhir
   `02-kedudukan-terhadap-literatur.md`.
4. **Batas klaim mengikuti §8 README utama.** Tidak ada klaim skalabilitas, performa, kebaruan
   algoritma truth discovery atau incremental view maintenance, maupun generalisasi ke seluruh 17
   SDG.

## Bila angka berubah

Angka pada draf sah selama `angka-kunci.csv` tidak berubah. Setelah `make article-bundle` dijalankan
ulang, periksa kembali tabel pemetaan di akhir setiap berkas draf sebelum memakai draf tersebut.
