# H7 Jalur A - Perlakuan B0 overwrite

H7 mengimplementasikan B0 sebagai pembanding paling sederhana: tabel hanya menyimpan satu
observasi terkini untuk setiap `cell_id`. Tiga vintage nyata dari H6 diterapkan berurutan. Baris
yang cocok mengganti seluruh fakta sebelumnya dan baris yang belum ada dimasukkan. B0 sengaja
tidak menyediakan alamat vintage untuk membaca angka lama.

## Kontrak perlakuan

State fisik berada pada `kkciv.experiments.b0_indicator_current`, memakai seluruh kolom fakta H6
ditambah `applied_order` dan `replaced_observation_id` untuk memeriksa operasi terakhir. Grain-nya
tepat satu baris per `cell_id`; tabel dipartisi hanya menurut `domain`, sama seperti fakta H6.

Setelah seluruh batch selesai, semua snapshot Iceberg selain snapshot terbaru dihapus melalui
`expire_snapshots`. Langkah ini merupakan bagian dari definisi B0. Tanpanya, time travel Iceberg
secara tidak sengaja akan membuat baseline overwrite mampu membaca state lama dan menyamarkan
perbedaan terhadap B1.

## Beban revisi nyata

`make h7-run` menerapkan 38 observasi H6 menurut `vintage_date`, `retrieved_at`, lalu `vintage_id`.

| Urutan | Vintage | Masuk | Insert | Ditimpa | Nilai berubah | Nilai sama | State akhir |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | TPB 2024 | 14 | 14 | 0 | 0 | 0 | 14 |
| 2 | TPB 2025 | 14 | 0 | 14 | 4 | 10 | 14 |
| 3 | WebAPI 2026 | 10 | 0 | 10 | 10 | 0 | 14 |

Secara total, 24 alamat observasi lama ditimpa: 14 benar-benar berubah secara numerik dan 10
diganti oleh vintage baru dengan nilai numerik yang sama. Perbedaan ini dipertahankan agar biaya
overwrite tidak keliru disamakan dengan jumlah perubahan nilai.

## Audit reproduksi angka lama

Audit meminta ulang setiap pasangan `cell_id` dan `vintage_id` pada 38 observasi input. Hanya 14
observasi terakhir yang masih tersedia dan 24 observasi historis gagal dipanggil ulang. Tingkat
keberhasilan adalah `14 / 38 = 0,3684` atau 36,84 persen. Ini adalah hasil kontrol negatif untuk
P4, bukan metrik performa dan bukan alasan mengeluarkan B0 dari perbandingan eksperimen.

Kegagalan tersebut terjadi sesuai desain: B0 hanya dapat menjawab nilai terkini berdasarkan
`cell_id`. Kolom audit `replaced_observation_id` tidak mengembalikan fakta lama; ia hanya menyimpan
identitas baris yang langsung diganti pada state terkini.

## Uji Iceberg

`make h7-apply` memvalidasi checksum manifest, membuat tabel, menjalankan tiga `MERGE` secara
berurutan, menghapus snapshot lama, lalu memeriksa:

- jumlah baris dan `cell_id` unik sama-sama 14;
- hasil fisik cocok dengan state deterministik yang dibentuk `make h7-run`;
- 14 permintaan current berhasil dan 24 permintaan historis gagal sesuai audit;
- hanya satu snapshot Iceberg yang tertinggal dan tabel mempunyai data file;
- tidak ada duplikasi sel atau ketidakcocokan audit.

Status verifikasi VM akan dicatat setelah commit implementasi ditarik dan dijalankan pada
`sigerciv@34.128.67.92`.

## Artefak dan reproduksi

- `contracts/h7-b0-overwrite.json`: kontrak state, tindakan overwrite, dan kebijakan histori;
- `infra/spark/h7-b0.sql`: DDL tabel Iceberg;
- `results/processed/h7-b0-operations.csv`: statistik dan hash state setiap batch;
- `results/processed/h7-b0-final-state.csv`: 14 baris state terkini;
- `results/processed/h7-b0-reproducibility.csv`: audit 38 permintaan vintage;
- `results/processed/h7-b0-summary.csv`: ringkasan metrik B0;
- `data/manifests/h7-b0-overwrite.json`: checksum input-output;
- `scripts/h7_apply.sh`: uji integrasi Iceberg idempoten.

Jalankan:

```bash
make h7-run
make test
make h7-apply  # membutuhkan stack yang aktif
```
