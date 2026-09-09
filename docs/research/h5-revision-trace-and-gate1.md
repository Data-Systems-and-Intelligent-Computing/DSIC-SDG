# H5 - Jejak revisi, Gate G1, dan uji Iceberg

H5 menutup Minggu 1 dengan membekukan nilai lama dan baru sebagai vintage yang terurut, menguji
kembali kandidat H4 dengan bukti tambahan yang bertanggal, lalu menjalankan uji tulis-baca tabel
Iceberg pada fondasi yang sudah aktif. Seluruh bukti berasal dari kanal gratis BPS yang sama dengan
H1-H4.

## Keputusan

**Gate G1 lolos.** Ketiga kriteria yang ditetapkan sebelum eksperimen terpenuhi.

| Kriteria | Ambang | Hasil H5 | Status |
|---|---:|---:|---|
| Domain dengan ketidaksesuaian | minimal 3 | energi, ekonomi, ekologi | Lolos |
| Kejadian terkonfirmasi dalam tiga sebab utama | minimal 70% | 96/123 = 78,05% | Lolos |
| Jejak revisi antarwaktu | minimal 1 | 4 perubahan langsung antarpublikasi | Lolos |

H4 mempunyai 85 kejadian terkonfirmasi dari 123 kejadian. H5 menaikkan sebelas kandidat setelah
pemeriksaan bukti, sehingga numerator menjadi 96 tanpa mengubah denominator. Delapan kandidat
yang belum mempunyai bukti cukup tetap berstatus kandidat; kelolosan gate tidak diperoleh dengan
menganggap seluruh kandidat sebagai fakta.

## Bukti yang dinaikkan

### Sepuluh sel laju pertumbuhan PDB per tenaga kerja

Sepuluh sel provinsi tahun 2022-2023 mempunyai urutan tiga vintage resmi:

1. lampiran TPB 2024 menyimpan nilai awal dan menandai 2022 sebagai `Angka Sementara` serta 2023
   sebagai `Angka Sangat Sementara`;
2. lampiran TPB 2025 mempertahankan nilai yang sama, indikator, unit, produsen, dan penanda
   sementara yang sama;
3. snapshot WebAPI 8 September 2026 memberikan nilai berbeda pada sel indikator yang sama dan
   mencatat pembaruan tabel 6 Juli 2026.

Empat kejadian berasal dari tahun 2022 dan enam dari tahun 2023. Nilai TPB 2025 diperiksa pada
halaman PDF 226 (halaman tercetak 208), kolom 11 dan 12. Definisi penanda `x` dan `xx` terdapat
pada catatan lampiran. Kombinasi nilai lama yang secara eksplisit sementara, publikasi penguat
bertanggal, dan snapshot resmi yang lebih baru cukup untuk menaikkan kejadian menjadi
`vintage_observed`.

Ini tetap bukti vintage lintas kanal resmi, bukan bukti bahwa endpoint WebAPI sendiri pernah
menampilkan nilai TPB lama. Klaim yang lebih sempit ini dipertahankan karena tidak ada penarikan
WebAPI historis sebelum 2026.

### Satu perubahan definisi tutupan hutan

TPB 2024 menamai numerator sebagai **kawasan hutan** dan melaporkan 51,20 persen untuk 2022. TPB
2025 menamai numerator sebagai **tutupan hutan**, melaporkan 51,16 persen, serta menjelaskan bahwa
area berhutan dihitung di dalam dan di luar kawasan hutan dari interpretasi citra satelit. Karena
perubahan konsep numerator tertulis di dua rilis, kandidat ini dinaikkan menjadi
`methodology_observed`, bukan dipaksa menjadi revisi vintage.

## Kandidat yang sengaja tidak dinaikkan

Delapan kejadian masih berstatus kandidat:

- empat perbedaan provinsi tahun 2021 pada laju pertumbuhan PDB per tenaga kerja tidak mempunyai
  penanda angka sementara;
- tiga perbedaan bauran energi 2018-2020 hanya membandingkan publikasi dengan satu snapshot
  WebAPI;
- perbedaan intensitas energi 2018 sebesar 287,98 SBM per miliar rupiah menunjukkan patahan seri,
  tetapi publikasi tidak memberi catatan perubahan unit atau metode yang cukup untuk menentukan
  sebabnya.

Pembatasan ini mencegah selisih besar atau urutan tanggal saja diperlakukan sebagai bukti revisi.

## Jejak yang dibekukan

`results/processed/h5-revision-traces.csv` memuat 14 jejak dan 38 baris vintage:

- empat perubahan langsung TPB 2024 ke TPB 2025, masing-masing dua vintage;
- sepuluh perubahan dari nilai sementara TPB 2024, nilai penguat TPB 2025, dan snapshot WebAPI
  2026, masing-masing tiga vintage.

Setiap baris mempertahankan `event_id`, identitas sel, urutan vintage, tanggal rilis atau snapshot,
nilai, produsen, versi metodologi, locator rekaman sumber, dan dasar bukti. ID jejak sama dengan ID
kejadian H4 agar rantai H3 -> H4 -> H5 dapat ditelusuri tanpa pencocokan kabur.

## Uji tabel Iceberg

`make h5-iceberg` membuat namespace `kkciv.gate1`, menulis 38 baris ke tabel Iceberg
`h5_revision_trace` dengan `INSERT OVERWRITE`, lalu membaca tabel serta metadata data-file kembali.
Uji dinyatakan lulus hanya bila jumlah baris, jumlah jejak, rentang urutan vintage, dan keberadaan
minimal satu data file cocok dengan manifest H5.

Eksekusi telah diverifikasi pada 9 September 2026 di `sigerciv@34.128.67.92` setelah VM menarik
commit `89a9bd4` dari `main`. Marker baca-balik adalah `H5_VERIFY|38|14|1|3|1`: 38 baris, 14
jejak, urutan vintage minimum 1 dan maksimum 3, serta satu data file Iceberg. Seluruh 29 tes lulus;
satu tes ekstraksi PDF dilewati karena payload PDF mentah sengaja tidak disimpan di Git. Clone VM
tetap bersih setelah eksekusi.

## Artefak dan reproduksi

- `config/h5/evidence_decisions.csv`: sebelas keputusan promosi beserta locator bukti;
- `results/processed/h5-confirmed-events.csv`: seluruh 123 kejadian dengan status H4 dan H5;
- `results/processed/h5-revision-traces.csv`: 14 jejak antarwaktu;
- `results/processed/h5-gate-g1-summary.csv`: keputusan tiga kriteria;
- `data/manifests/h5-gate1.json`: checksum input-output dan keputusan gate;
- `scripts/h5_iceberg.sh`: uji tulis-baca Iceberg yang idempoten.

Jalankan:

```bash
make h5-run
make test
make h5-iceberg  # membutuhkan stack yang aktif
```
