# H4 - Aturan klasifikasi dan ingestion ber-manifest

H4 memakai seluruh keluaran H3 yang berasal dari sumber gratis. Tujuannya adalah menetapkan satu
aturan klasifikasi lintas domain sebelum eksperimen dimulai, serta membentuk satu batch observasi
yang hanya dapat dibuat bila checksum dan jumlah baris input cocok dengan manifest H3.

## Hasil

Batch **h4-2981e0fb3bc2d960** memuat **7.666 observasi** dari tiga dataset:

| Dataset | Baris |
|---|---:|
| WebAPI untuk audit nasional-provinsi H3 | 1.435 |
| TPB 2024 untuk audit nasional-provinsi H3 | 1.435 |
| Rekonsiliasi WebAPI, TPB 2024, dan TPB 2025 | 4.796 |
| **Total** | **7.666** |

Pipeline menolak input bila berkas tidak tercantum dalam manifest H3, checksum berbeda, jumlah
baris berubah, kolom wajib hilang, indikator tidak mempunyai domain, nilai bukan angka hingga,
atau sebuah observasi muncul dua kali dalam dataset yang sama. ID batch diturunkan dari checksum
dua manifest H3 dan pemetaan domain, sehingga input yang sama menghasilkan ID serta keluaran yang
sama.

## Aturan bersama

Aturan ada di **config/h4/classification_rules.csv** dan tidak bercabang menurut domain. Domain
pendidikan, lingkungan, energi, ekonomi, dan ekologi memakai delapan aturan yang sama.

| Masukan | Hasil | Sebab utama | Bukti |
|---|---|---|---|
| Selisih paling banyak satu unit desimal terakhir | rounding_or_presentation | Di luar tiga sebab utama | Teramati |
| WebAPI diperbarui setelah publikasi | vintage_candidate | Vintage | Kandidat |
| Dua publikasi bertanggal memberi nilai berbeda | vintage_observed | Vintage | Teramati |
| Judul atau denominator berubah | methodology_candidate | Metodologi | Kandidat |
| Selisih terlalu besar untuk pembulatan | methodology_or_unit_candidate | Metodologi | Kandidat |
| Nasional berbeda dari rata-rata provinsi tanpa bobot | granularity_structural | Granularitas | Teramati |
| Tidak ada penanda yang cukup | unclassified_difference | Belum terklasifikasi | Belum terselesaikan |

Perubahan antara dua publikasi bertanggal memiliki bukti lebih kuat daripada perbedaan WebAPI
terhadap satu publikasi. Karena snapshot WebAPI historis belum tersedia, tanggal last_update
saja tidak cukup untuk menaikkan vintage_candidate menjadi vintage_observed.

## Distribusi 123 kejadian

| Sebab | Teramati | Kandidat | Total | Dihitung sebagai tiga sebab utama |
|---|---:|---:|---:|---|
| Granularitas | 82 | 0 | 82 | Ya |
| Vintage | 3 | 17 | 20 | Ya |
| Metodologi | 0 | 2 | 2 | Ya |
| Pembulatan/presentasi | 19 | 0 | 19 | Tidak |
| Belum terklasifikasi | 0 | 0 | 0 | Tidak |
| **Total** | **104** | **19** | **123** | |

Kolom “teramati” pada total mencakup 19 kejadian pembulatan yang bukan bagian dari tiga sebab
utama. Bukti utama yang telah terkonfirmasi adalah 82 kejadian granularitas dan tiga perubahan
langsung antarpublikasi, yaitu 85 kejadian.

Seluruh domain terwakili dalam hasil: 24 kejadian pendidikan, 12 lingkungan, 17 energi, 69
ekonomi, dan satu ekologi. Tidak adanya perbedaan nilai pada pendidikan dan lingkungan tetap
dipertahankan; kejadian kedua domain itu berasal dari perbedaan granularitas nasional-provinsi.

## Keputusan Gate G1 setelah H4

| Kriteria | Hasil |
|---|---|
| Ketidaksesuaian pada minimal tiga domain | Lolos: energi, ekonomi, dan ekologi |
| Minimal 70% dijelaskan oleh vintage, metodologi, atau granularitas | 84,55% bila kandidat dihitung; 69,11% untuk bukti terkonfirmasi |
| Jejak revisi antarwaktu | Menunggu pembekuan jejak pada H5 |

Gate G1 tetap berstatus **pending_H5**. Angka kandidat-inklusif melewati ambang, tetapi angka
terkonfirmasi belum. Dengan denominator 123, sedikitnya 87 kejadian harus terkonfirmasi untuk
melewati 70%; H5 perlu menaikkan minimal dua kandidat menjadi bukti teramati.

## Artefak

- **config/h4/classification_rules.csv**: aturan dan tingkat bukti.
- **config/h4/indicator_domains.csv**: pemetaan 16 indikator ke lima domain.
- **results/processed/h4-ingested-observations.csv**: batch ingestion 7.666 baris.
- **results/processed/h4-ingestion-inventory.csv**: inventaris per domain, dataset, sumber, rilis,
  dan tingkat geografi.
- **results/processed/h4-classified-events.csv**: 123 kejadian dengan ID deterministik dan aturan
  yang dipakai.
- **results/processed/h4-classification-summary.csv**: ringkasan sebab serta tingkat bukti.
- **data/manifests/h4-ingestion-classification.json**: checksum input-output dan penilaian Gate G1.

Jalankan ulang dengan **make h4-run**, lalu **make test**.

Pada VM, masuk ke **~/DSIC-SDG**, jalankan **git pull --ff-only origin main**,
**make h4-run**, lalu **make h4-publish**.

Perintah publish menulis kelima artefak H4 ke bucket **kkciv-warehouse** pada prefiks
**ingest/h4/batch_id/** melalui MinIO yang sudah berjalan. Tidak ada payload mentah atau rahasia
.env yang dikirim dari laptop.
