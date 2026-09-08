# H2 - Perbandingan awal dua jalur gratis

Tanggal snapshot WebAPI: 8 September 2026. Rilis publikasi pembanding: 31 Desember 2024.

## Keputusan H2

H2 selesai sebagai pilot lima domain. Empat indikator dapat disejajarkan pada tingkat nasional dan
satu indikator ditolak sebelum perbandingan nilai karena definisinya berbeda. Semua input berasal
dari WebAPI BPS dan publikasi TPB 2024 yang gratis; SIRuSa, DNA, dan Silastik/PST tidak digunakan.

H2 menemukan perbedaan nilai pada domain energi. Temuan itu membuktikan bahwa dua jalur resmi
tidak selalu mengembalikan angka yang identik, tetapi belum cukup untuk meloloskan Gate G1 karena
perbedaan baru ditemukan pada satu dari lima domain. H3 perlu memperluas indikator di setiap
domain dan menelusuri penyebab perbedaannya.

## Pilot dan aturan penyelarasan

| Domain | Indikator | WebAPI | Publikasi | Keputusan |
|---|---|---|---|---|
| Pendidikan | Tingkat penyelesaian SD/SMP/SMA | `var=1980` | Gambar 4.2-4.4, hlm. 46-47 | Dapat dibandingkan |
| Lingkungan | Fasilitas cuci tangan dengan sabun dan air | `var=1273` | Gambar 6.2, hlm. 70 | Dapat dibandingkan |
| Energi | Bauran energi terbarukan | `var=1824` | Gambar 7.5, hlm. 80 | Dapat dibandingkan |
| Ekonomi | Upah rata-rata per jam | `var=1172` | Gambar 8.8, hlm. 88 | Dapat dibandingkan |
| Ekologi | Proporsi tutupan hutan | `var=1304` | Gambar 15.1, hlm. 162 | `methodology_mismatch` |

Kunci sel ditetapkan sebagai `indicator_key + series_key + observed_period + geo_level +
geo_code + unit`. Kolom `series_key` ditambahkan agar SD, SMP, dan SMA tidak tercampur menjadi
satu observasi. Hanya observasi nasional tahunan dengan konsep dan unit yang sama yang masuk
perbandingan nilai.

Variabel 1304 tidak dibandingkan secara numerik. WebAPI menyajikan luas penutupan lahan di dalam
atau di luar kawasan hutan dalam ribu hektare. Publikasi menyajikan proporsi kawasan hutan terhadap
luas lahan. Menghitung rasio kedua kategori WebAPI tidak otomatis menghasilkan indikator tutupan
hutan karena “kawasan hutan” adalah klasifikasi kawasan, bukan kelas tutupan hutan.

## Hasil perbandingan sel

| Domain | Sel publikasi | Sel WebAPI | Sel beririsan | Sama | Berbeda | Hilang pada satu snapshot |
|---|---:|---:|---:|---:|---:|---:|
| Pendidikan | 6 | 6 | 6 | 6 | 0 | 0 |
| Lingkungan | 3 | 3 | 3 | 3 | 0 | 0 |
| Energi | 6 | 5 | 5 | 2 | 3 | 1 |
| Ekonomi | 5 | 5 | 5 | 5 | 0 | 0 |
| Ekologi | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total yang dapat dibandingkan** | **20** | **19** | **19** | **16** | **3** | **1** |

Tiga perbedaan seluruhnya berasal dari bauran energi terbarukan:

| Tahun | Publikasi TPB 2024 | Snapshot WebAPI 2026-09-08 | Selisih absolut |
|---|---:|---:|---:|
| 2018 | 9,00 | 8,60 | 0,40 |
| 2019 | 9,15 | 9,19 | 0,04 |
| 2020 | 11,20 | 11,27 | 0,07 |

Nilai 2021 dan 2022 sama persis. Publikasi juga memiliki nilai 2023 sebesar 13,21 persen, sedangkan
variabel WebAPI 1824 berhenti pada 2022. Tiga sel berbeda untuk sementara diberi label
`unclassified_difference`. H2 belum mempunyai bukti yang cukup untuk menyebutnya revisi versi
rilis atau perubahan metodologi.

## Provenans ekstraksi publikasi

Nilai publikasi ditranskripsi dari grafik TPB 2024 dan diverifikasi secara visual pada halaman
aslinya. Berkas referensi menyimpan halaman, nomor gambar, metode ekstraksi, tanggal rilis,
produsen, dan `source_record_id`. Hash berkas tersebut serta seluruh keluaran disimpan dalam
manifest H2.

WebAPI dinormalisasi langsung dari `datacontent`. Kunci gabungan BPS dibentuk kembali dari ID
wilayah, variabel, kategori, periode, dan turunan periode. `release_date` untuk baris WebAPI adalah
tanggal snapshot H1; tanggal `last_update` tabel tetap disimpan pada `methodology_version`.

## Artefak

- `config/h2/pilot_indicators.csv`: keputusan kesetaraan konsep per domain.
- `config/h2/pilot_series.csv`: pemetaan kategori WebAPI ke seri analitis.
- `data/reference/h2/tpb-2024-figure-observations.csv`: 25 angka yang diverifikasi dari grafik,
  termasuk lima angka ekologi yang ditahan dari perbandingan.
- `results/processed/h2-normalized-observations.csv`: 39 observasi yang lolos penyelarasan.
- `results/processed/h2-cell-comparison.csv`: hasil perbandingan 20 kunci sel.
- `results/processed/h2-discrepancies.csv`: tiga perbedaan belum terklasifikasi dan satu celah
  periode untuk ditelusuri pada H3.
- `results/processed/h2-indicator-summary.csv`: ringkasan per domain.
- `data/manifests/h2-normalization.json`: checksum input dan keluaran.

Jalankan ulang dengan:

```bash
make h2-run
make test
```

H2 dianggap selesai karena lima domain sudah melewati keputusan penyelarasan, empat pasangan
sumber berhasil dibandingkan, dan kasus yang tidak sebanding ditolak dengan alasan eksplisit.
Langkah berikutnya adalah H3: memperluas perbandingan nasional dan provinsi untuk mencari
ketidaksesuaian pada sedikitnya tiga domain serta memisahkan revisi, metodologi, dan granularitas.
