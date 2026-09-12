# H10 Jalur A — Ruang Fisik dan Pemanggilan Ulang setelah Restart Katalog

## Status

H10 Jalur A mengukur ruang fisik keempat perlakuan pada workload revisi nyata H6. Pengujian juga
memastikan angka lama tetap dapat dipanggil setelah katalog Iceberg di-restart. Pengukuran berjalan
di VM `praktikum-sd` pada 11 September 2026 pukul 11:05–11:33 UTC, dalam tiga repetisi berurutan
yang dijalankan satu operator. **Waktu tidak diukur.**

Marker agregasi `make h10-run`:

```text
H10_VERIFY|3|95898|190261|64077|240884|14|38|14|38|variable|measured
```

Artinya: 3 repetisi; median byte B0 95.898, B1 190.261, B2 64.077, dan B3 240.884; permintaan yang
berhasil dipanggil setelah restart B0 14, B1 38, B2 14, dan B3 38. Label `variable` berarti total
byte tidak identik persis antarrepetisi. Selisihnya 4–18 byte dan hanya berasal dari berkas metadata
(lihat bagian Stabilitas).

Data mentah disalin dari VM ke repositori. `make h10-run` dijalankan sekali di lokal dan dua kali di
VM, dan checksum gabungan tujuh CSV keluaran serta manifest identik pada ketiga run. Seluruh 89 test
lokal lulus.

## Temuan infrastruktur yang mendahului pengukuran

Setelah VM dimatikan dan dinyalakan kembali pada 11 September 2026, katalog `kkciv` hanya berisi
tabel yang dibuat sesudah boot. Namespace `research` dan `gate1`, beserta tabel B0, B1, dan B2,
tidak lagi terdaftar, walaupun berkas datanya masih ada di MinIO. Penyebabnya, image
`apache/iceberg-rest-fixture` secara bawaan menyimpan katalog JDBC di SQLite **in-memory**
(`jdbc:sqlite::memory:`). Semua marker H5–H9 sah pada saat dijalankan, tetapi registrasi tabelnya
tidak bertahan saat restart.

Atas persetujuan peninjau (`h10_catalog_persistence`), katalog dipindahkan ke berkas SQLite pada
volume Docker bernama `iceberg-catalog`, yang dipasang di `/home/iceberg` (direktori milik user
image). Uji probe menulis satu tabel, me-restart `iceberg-rest`, lalu membaca tabel yang sama
kembali. Setelah itu seluruh tabel penelitian dibangun ulang dari CSV ber-manifest dengan script
apply yang sudah ada, dan setiap marker identik dengan catatan lama:

```text
H5_VERIFY|38|14|1|3|1
H6_VERIFY|3|38|14|2|3|1|3|0|0
H7_VERIFY|14|14|14|24|1|3|0|0|0
H7B_VERIFY|14|14|1|10|14|24|1|3|0|0|0
H8_VERIFY|3|42|14|38|0|3|0|0|0|0
H9_VERIFY|38|38|14|14|38|0|1|1|0|0|42|0
```

Temuan ini relevan bagi P4. Kemampuan B1 memanggil angka lama bergantung pada metadata snapshot
di katalog. Katalog yang tidak persisten menghapus kemampuan itu tanpa tanda apa pun di data.

## Protokol

Kontraknya adalah `contracts/h10-storage-recall.json` (`h10a.1`), dengan eksekusi melalui
`scripts/h10_measure.sh` (`make h10-measure`):

1. memastikan `CATALOG_URI` berada di bawah `jdbc:sqlite:/home/iceberg/` dan working tree bersih;
2. merekam lingkungan: host, vCPU, memori, disk, digest image, checksum konfigurasi, dan commit;
3. untuk setiap repetisi: menjalankan `DROP TABLE ... PURGE` pada lima tabel perlakuan, lalu script
   apply B0, B1, B2, dan B3 secara berurutan, dan merekam marker verifikasinya;
4. membaca metadata Iceberg setiap tabel (`all_data_files`, `all_delete_files`, `all_manifests`,
   `snapshots.manifest_list`, `metadata_log_entries`) dan listing objek MinIO di lokasi tabel;
5. setelah repetisi terakhir: me-restart `iceberg-rest`, lalu memanggil ulang 38 permintaan per
   perlakuan. B1 dipanggil dengan `VERSION AS OF` pada setiap snapshot yang dipertahankan, B3 dengan
   `(cell_id, vintage_id)`, sedangkan B0 dan B2 dengan `observation_id` di tabel current.

Footprint didefinisikan sebagai byte setiap objek yang **dapat dicapai dari metadata snapshot yang
dipertahankan**, termasuk metadata JSON lama yang masih tercatat di `metadata_log_entries`. Definisi
ini disetujui peninjau pada 12 September 2026 (`h10a_footprint_definition`). Ukuran diambil dari
listing MinIO. Untuk data, delete, dan manifest, ukuran di
metadata harus sama dengan ukuran objek. Objek di lokasi tabel yang tidak dirujuk metadata dilaporkan
terpisah dan tidak dihitung, termasuk sisa run 9 September yang tertinggal saat katalog hilang.

Data mentah pengukuran disimpan di `results/raw/h10/h10a-20260911/`. `make h10-run` membentuk seluruh
keluaran `results/processed/h10-*` dari data mentah itu.

## Lingkungan yang dinyatakan

| Parameter | Nilai |
|---|---|
| Host | `praktikum-sd` (`sigerciv@34.101.84.199`) |
| vCPU host / container Spark | 2 / 2 |
| Memori | 8.318.799.872 byte (7,7 GiB) |
| Disk / sisa sebelum run | 19,6 GB / 3,5 GB |
| Katalog | `jdbc:sqlite:/home/iceberg/iceberg_catalog.db` |
| Commit pengukuran | `c84e77a` |

Lingkungan ini lebih kecil daripada spesifikasi proposal (8 vCPU, 16 GB, 256 GB). Keputusan
`h10_storage_environment` menyatakan dan membekukannya **hanya untuk pengukuran byte**. Byte tidak
bergantung pada CPU selama tata letak file sama, dan tata letak itu direkam per objek. Pada 12
September 2026, VM yang sama juga dibekukan sebagai lingkungan pengukuran waktu H10B dan H11
(`h10b_timing_environment`), sehingga keempat perlakuan diukur pada perangkat keras yang identik dan
angkanya hanya boleh dibaca sebagai perbandingan antarperlakuan.

## Hasil ruang

| Perlakuan | Total (median) | Rentang | Data Parquet | Metadata Iceberg | File data | Baris fisik | Snapshot |
|---|---:|---:|---:|---:|---:|---:|---:|
| B0 | 95.898 B | 95.890–95.899 | 32.656 B | 63.242 B | 3 | 14 | 1 |
| B1 | 190.261 B | 190.258–190.265 | 101.486 B | 88.775 B | 9 | 42 | 3 |
| B2 | 64.077 B | 64.075–64.079 | 38.311 B | 25.766 B | 3 | 14 | 1 |
| B3 | 240.884 B | 240.870–240.888 | 117.603 B | 123.281 B | 10 | 52 | 1+1 |

Rincian B3 per tabel:

| Tabel B3 | Total (median) | Data | Metadata | File data | Baris |
|---|---:|---:|---:|---:|---:|
| store `b3_observation_vintages` | 146.352 B | 80.880 B | 65.472 B | 7 | 38 |
| serving `b3_indicator_current` | 94.532 B | 36.723 B | 57.809 B | 3 | 14 |

Baris fisik sama dengan baris logis yang dihitung pada H7–H9 (14, 42, 14, 52). Artinya tidak ada
duplikasi tersembunyi di tingkat file.

### Temuan

1. **Pada fixture 14 sel, B3 memakai ruang paling besar, sekitar 1,27× B1.** Penyebabnya adalah
   tabel serving yang dimaterialisasi (94.532 B). **Store B3 saja 23% lebih kecil daripada B1**
   (146.352 dibanding 190.261 B): 38 baris dan 7 file data, dibanding 42 baris dan 9 file.
   Keputusan memelihara tabel serving (disetujui 2026-09-11) menjadi ongkos terbesar B3 pada skala
   ini. Keputusan pelaporan 12 September 2026 (`h10a_b3_serving_reporting`) menetapkan angka utama
   B3 adalah total termasuk tabel serving, karena tabel itu bagian dari rancangan perlakuan,
   sedangkan dekomposisi store dan serving dilaporkan pada tabel yang sama.
2. **Metadata sebanding dengan data, bahkan melampauinya.** B0 menyimpan 63.242 B metadata untuk
   32.656 B data. `expire_snapshots` menghapus snapshot dan file data lama, tetapi keenam metadata
   JSON dari riwayat tulis tabel tetap tersimpan. Pada tabel sekecil ini, ongkos tetap Iceberg
   mendominasi. Perbandingan ruang karena itu harus melaporkan data dan metadata secara terpisah.
3. **Ongkos ruang B1 tumbuh per rilis, bukan per revisi.** Setiap snapshot menulis ulang ketiga
   partisi domain (9 file data untuk 3 snapshot). Pada tabel yang jauh lebih besar, pola ini yang
   diperkirakan membuat B1 mahal. Namun perkiraan itu belum terukur di sini dan baru diuji oleh sweep
   H11.
4. **B0 dan B2 paling hemat hanya karena membuang histori.** Angka ruangnya tidak boleh dibaca
   terpisah dari hasil pemanggilan ulang di bawah.

## Stabilitas antarrepetisi

Byte data Parquet, jumlah file, baris fisik, dan jumlah snapshot identik pada ketiga repetisi. Yang
bergeser hanya berkas metadata, sebesar 4–18 byte per perlakuan (<0,01%). Manifest dan manifest list
Avro memuat snapshot ID acak, dan metadata JSON memuat timestamp, sehingga panjang digitnya dapat
berbeda. Median dan rentang dilaporkan bersama. Pipeline menandai hasil ini sebagai `variable`, bukan
`stable`, agar perbedaan sekecil apa pun tidak tersembunyi.

## Pemanggilan ulang setelah restart katalog

Setelah `iceberg-rest` di-restart, ke-152 permintaan dipanggil ulang dari Iceberg:

| Perlakuan | Mekanisme | Berhasil | Tidak tersedia |
|---|---|---:|---:|
| B0 | tabel current | 14 | 24 |
| B1 | `VERSION AS OF` pada 3 snapshot yang bertahan | 38 | 0 |
| B2 | tabel current | 14 | 24 |
| B3 | kunci `(cell_id, vintage_id)` pada store | 38 | 0 |

Setiap pembacaan yang berhasil cocok pada `observation_id` dan `value_lexeme`. Setiap hasil juga sama
dengan addressability yang diaudit H9C. Untuk B1, urutan snapshot yang memuat setiap observasi sama
dengan `matching_snapshot_orders` H8A. Dengan demikian P4 kini terbukti secara fisik, tidak hanya
secara logis, dan tetap berlaku setelah restart katalog persisten.

## Batas klaim

- Hasil hanya berlaku untuk fixture 38 observasi/14 sel. Byte pada skala ini didominasi ongkos tetap
  dan tidak boleh diekstrapolasi menjadi klaim skala.
- Tidak ada waktu tulis, waktu baca, atau waktu penghitungan ulang yang diukur.
- Byte diukur pada lingkungan 2 vCPU yang dinyatakan. Tata letak file direkam per objek agar
  pengulangan di VM lain dapat dibandingkan.
- Workload tersuntik belum diukur secara fisik. Itu pekerjaan H10 Jalur B.

## Reproduksi

```bash
make h10-measure H10_RUN=<label-baru>   # di VM stack; tidak menimpa run yang sudah ada
make h10-run                            # agregasi dari results/raw/h10/h10a-20260911
make test
```

`make h10-measure` menolak berjalan bila direktori run sudah ada, bila katalog tidak persisten, atau
bila salah satu marker perlakuan gagal.

## Artefak audit

- kontrak: `contracts/h10-storage-recall.json`;
- keputusan manusia: `config/h10/human_decisions.csv`;
- konfigurasi katalog persisten: `docker-compose.yml` (`CATALOG_URI`, volume `iceberg-catalog`);
- script pengukuran: `scripts/h10_measure.sh`;
- pipeline: `src/kkciv_vintage/h10/`;
- data mentah: `results/raw/h10/h10a-20260911/` (lingkungan, 12 marker, 216 baris metadata,
  555 baris listing, 152 baris recall);
- 201 objek yang dirujuk: `results/processed/h10-storage-objects.csv`;
- footprint per kelas objek: `results/processed/h10-storage-footprint.csv`;
- footprint per tabel, termasuk objek yang tidak dirujuk: `results/processed/h10-storage-tables.csv`;
- ringkasan per perlakuan: `results/processed/h10-storage-by-treatment.csv`;
- 152 pemanggilan setelah restart: `results/processed/h10-recall-after-restart.csv`;
- invariant: `results/processed/h10-validation.csv`;
- ringkasan: `results/processed/h10-summary.csv`;
- manifest: `data/manifests/h10-storage-recall.json`.

## Keputusan audit manusia

Keempat pertanyaan audit H10A dijawab peninjau pada 12 September 2026 dan dicatat di
[`config/h10/human_decisions.csv`](../../config/h10/human_decisions.csv).

| ID | Keputusan |
|---|---|
| `h10a_footprint_definition` | Disetujui. Footprint adalah objek yang dapat dicapai dari metadata snapshot yang dipertahankan, termasuk metadata JSON lama di `metadata_log_entries`; objek yang tidak dirujuk dilaporkan terpisah dan tidak dihitung |
| `h10a_b3_serving_reporting` | Naskah melaporkan B3 sebagai total **termasuk** tabel serving, dengan dekomposisi store dan serving pada tabel yang sama |
| `h10b_timing_environment` | VM `praktikum-sd` 2 vCPU yang sudah dinyatakan dibekukan sebagai lingkungan pengukuran waktu H10B dan H11 |
| `h10b_orphan_cleanup` | Orphan di lokasi tabel eksperimen dibersihkan dengan `remove_orphan_files` sebelum sweep utama |

Pembersihan orphan dijalankan pada 12 September 2026 dan hasilnya berbeda dari dugaan semula:

- 64 objek dan 585.261 byte terhapus dari lokasi B0, B1, dan B2. Seluruhnya bertanggal 9 September
  05:19–05:25 UTC, yaitu run yang kehilangan registrasi katalog.
- Kedua lokasi B3 tidak kehilangan satu objek pun. Sebanyak 481.747 byte yang tidak dihitung sebagai
  footprint di sana **bukan orphan menurut Iceberg**, karena masih dapat dicapai lewat berkas
  metadata lama. Objek seperti itu hanya hilang bila metadata log dipangkas atau tabel dibangun ulang.
- `remove_orphan_files` juga tidak dapat melistkan lokasi tabel sendiri pada stack ini, karena image
  Spark tidak memuat file system Hadoop untuk skema `s3`. Daftar berkas karena itu diberikan dari
  listing MinIO lewat parameter `file_list_view`.

Rincian pembersihan ada di [`docs/research/h10b-injected-revision-physical.md`](h10b-injected-revision-physical.md)
dan data mentahnya di `results/raw/h10b/cleanup-20260912/`.
