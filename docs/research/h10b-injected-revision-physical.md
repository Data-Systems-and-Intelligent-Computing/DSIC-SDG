# H10 Jalur B — Eksekusi Fisik Satu Revisi Tersuntik pada Keempat Perlakuan

## Status

H10 Jalur B menjalankan revisi tersuntik yang sudah dibekukan H8B secara **fisik** di Iceberg, bukan
lagi secara logis seperti H9B. Untuk setiap skenario, keempat tabel perlakuan dibangun ulang dari
workload nyata H6, lalu satu revisi dimasukkan melalui mekanisme tulis milik masing-masing perlakuan.
Yang diukur adalah waktu pernyataan SQL dan pertambahan byte akibat revisi itu.

Marker agregasi `make h10b-run`:

```text
H10B_VERIFY|3|2|8|64|585261|9.818|5.442|5.308|13.388|24076|68447|24564|60156|14|39|14|39|measured
```

Artinya: 3 repetisi; 2 skenario; 8 route fisik; 64 objek dan 585.261 byte orphan dibersihkan sebelum
run; waktu tulis skenario satu sel B0 9,818 s, B1 5,442 s, B2 5,308 s, dan B3 13,388 s; pertambahan
byte 24.076, 68.447, 24.564, dan 60.156; permintaan yang dapat dipanggil ulang 14, 39, 14, dan 39 dari
39; status `measured`.

Pengukuran berjalan di VM `praktikum-sd` pada 12 September 2026 pukul 01:36–03:07 UTC, commit
`6c34e1d`, working tree bersih, satu operator dan tanpa beban lain di node. Ke-24 marker pembangunan
ulang cocok pada percobaan pertama.

Data mentah disalin dari VM ke repositori. `make h10b-run` dijalankan sekali di lokal dan dua kali di
VM; marker serta checksum keluaran dan manifest identik pada ketiga run. Seluruh 105 test lokal lulus,
dan di VM 105 test lulus dengan satu test PDF dilewati karena PDF mentah tidak disimpan di Git.

Angka H10B juga masuk paket data artikel: `make article-bundle` sekarang mengumpulkan 30 tabel dan 86
angka kunci, termasuk waktu tulis, pertambahan byte, dan pemanggilan ulang setelah revisi.

## Keputusan manusia yang dipakai

| ID | Keputusan |
|---|---|
| `h10b_timing_environment` | VM `praktikum-sd` 2 vCPU dibekukan sebagai lingkungan pengukuran waktu H10B dan H11 |
| `h10b_orphan_cleanup` | Orphan di lokasi tabel eksperimen dibersihkan dengan `remove_orphan_files` sebelum sweep utama |

Keduanya disetujui pada 12 September 2026 dan tercatat di
[`config/h10/human_decisions.csv`](../../config/h10/human_decisions.csv), bersama dua keputusan
pelaporan H10A yang dijawab pada hari yang sama.

## Skenario yang dieksekusi

Dua skenario dipilih dari profil validasi H8B yang sudah beku, dan keduanya sudah dijalankan secara
logis pada H9B sehingga hasil fisiknya punya pembanding baris per baris.

| Urutan | Skenario | Sel | Sumber yang direvisi | Perilaku B2 yang diuji |
|---|---|---:|---|---|
| 1 | `validation_001` | 1 | `bps_webapi` | menahan revisi |
| 2 | `validation_002` | 2 | `bps_tpb_2025`, `bps_webapi` | meneruskan 1 dari 2 revisi |

Skenario pertama memakai tepat satu sumber, sesuai aturan sweep utama. Skenario kedua sengaja memakai
dua sumber karena hanya dengan begitu jalur B2 yang *meneruskan* revisi ikut teruji secara fisik.
H10B adalah uji asap fisik, **bukan** sweep utama; aturan satu sumber per run tetap mengikat H11.

## Protokol

Kontraknya `contracts/h10b-injected-revision-physical.json` (`h10b.1`), dieksekusi oleh
`scripts/h10b_measure.sh` (`make h10b-measure`):

1. memastikan katalog persisten, working tree bersih, dan tidak ada orphan tersisa di kelima tabel;
2. untuk setiap repetisi dan setiap skenario: `DROP TABLE ... PURGE` lalu membangun ulang B0, B1, B2,
   dan B3 dari workload nyata, serta mencocokkan marker verifikasi tiap perlakuan;
3. mengukur footprint baseline setiap tabel;
4. menyuntikkan revisi melalui satu sesi Spark SQL per perlakuan:

   | Perlakuan | Pernyataan tulis | Pemeliharaan |
   |---|---|---|
   | B0 | `MERGE` baris sintetis ke tabel current | `expire_snapshots` sisa 1 |
   | B1 | `INSERT OVERWRITE` seluruh state baru sebagai snapshot keempat | tidak ada |
   | B2 | `INSERT OVERWRITE` seleksi yang dihitung ulang dengan skor beku H6B | `expire_snapshots` sisa 1 |
   | B3 | `INSERT` baris sintetis ke store, lalu `MERGE` hanya sel kotor ke tabel serving | `expire_snapshots` sisa 1 pada kedua tabel |

5. mengukur footprint sesudah revisi, lalu memanggil ulang seluruh observasi resmi dan sintetis.

Payload fisiknya dibentuk `make h10b-prepare` dari artefak H8B dan H9B yang sudah beku. Pipeline
persiapan menolak berjalan bila state yang dihitungnya berbeda dari state logis H9B, sehingga yang
ditulis ke Iceberg dijamin sama dengan yang sudah diaudit secara logis.

### Batas pengukuran waktu

Waktu yang dilaporkan adalah **waktu pernyataan di dalam satu sesi**, yaitu baris `Time taken` dari
Spark SQL CLI. Waktu menyalakan JVM, memanaskan katalog, dan membuat view CSV tidak dihitung sebagai
ongkos perlakuan. Pemisahan ini penting karena pada fixture 14 sel, ongkos tetap sesi jauh lebih besar
daripada pekerjaan datanya.

## Pembersihan orphan

Pembersihan dijalankan sekali dengan `scripts/h10b_cleanup_orphans.sh` (`make h10b-cleanup`) dan
dicatat di `results/raw/h10b/cleanup-20260912/`.

| Tabel | Objek sebelum | Byte sebelum | Objek dihapus | Objek sesudah | Byte sesudah | Byte dihapus |
|---|---:|---:|---:|---:|---:|---:|
| `b0_indicator_current` | 38 | 344.366 | 26 | 12 | 95.890 | 248.476 |
| `b1_indicator_full_snapshots` | 49 | 438.443 | 28 | 21 | 190.258 | 248.185 |
| `b2_indicator_selected` | 17 | 152.675 | 10 | 7 | 64.075 | 88.600 |
| `b3_observation_vintages` | 48 | 439.048 | 0 | 48 | 439.048 | 0 |
| `b3_indicator_current` | 33 | 283.583 | 0 | 33 | 283.583 | 0 |

Seluruh 64 objek yang dihapus bertanggal 9 September 2026 pukul 05:19–05:25 UTC, yaitu run yang
kehilangan registrasi katalog. Setelah pembersihan, lokasi B0, B1, dan B2 berisi persis objek yang
dihitung footprint H10A (95.890, 190.258, dan 64.075 byte).

Kedua lokasi B3 tidak berubah. Sebanyak 481.747 byte yang tidak dihitung H10A di sana **bukan orphan
menurut Iceberg**: berkas metadata lama masih menunjuk objek tersebut, sehingga prosedur
mempertahankannya. Angka "objek tidak dirujuk" pada H10A karena itu tidak boleh dibaca sebagai
"sampah yang dapat dihapus"; keduanya definisi yang berbeda.

Dua temuan infrastruktur muncul di sini:

1. **Prosedur Iceberg tidak dapat melistkan lokasi tabel sendiri pada stack ini.** Image Spark hanya
   membawa `iceberg-aws-bundle`, tanpa file system Hadoop untuk skema `s3`, sehingga
   `remove_orphan_files` gagal dengan `No FileSystem for scheme "s3"`. Daftar berkas karena itu
   diambil dari listing MinIO dan diserahkan lewat parameter `file_list_view`.
2. **Definisi orphan Iceberg lebih sempit daripada definisi footprint H10A.** Objek yang tidak
   dihitung H10A karena tidak dapat dicapai dari metadata snapshot yang dipertahankan masih dianggap
   terpakai oleh Iceberg bila berkas metadata lama masih menunjuknya.

Prosedur juga menolak interval di bawah 24 jam, sehingga ambang `older_than` ditetapkan 25 jam
sebelum run. Semua objek yang dihapus jauh lebih tua daripada ambang itu.

## Hasil waktu

Median tiga repetisi, dalam detik. `tulis` adalah pernyataan yang mengubah data, `pemeliharaan`
adalah `expire_snapshots` yang dituntut rancangan perlakuan.

| Skenario | Perlakuan | Pernyataan tulis | Tulis (median) | Rentang | Pemeliharaan | Total |
|---|---|---:|---:|---:|---:|---:|
| `validation_001` (1 sel) | B0 | 1 | 9,818 | 9,321–9,885 | 14,088 | 23,448 |
| | B1 | 1 | 5,442 | 4,847–5,533 | 0,000 | 5,442 |
| | B2 | 1 | 5,308 | 5,245–5,381 | 15,872 | 21,253 |
| | B3 | 2 | 13,388 | 13,109–14,977 | 20,991 | 34,877 |
| `validation_002` (2 sel) | B0 | 1 | 9,503 | 8,970–10,846 | 13,765 | 23,268 |
| | B1 | 1 | 5,384 | 5,030–5,648 | 0,000 | 5,384 |
| | B2 | 1 | 5,335 | 5,104–5,429 | 17,230 | 22,585 |
| | B3 | 2 | 14,704 | 14,396–15,116 | 22,914 | 37,618 |

Rincian per pernyataan B3 pada satu sel: `INSERT` ke store 4,763 s dan `MERGE` sel kotor ke serving
8,636 s.

## Hasil ruang

Median tiga repetisi, dalam byte.

| Skenario | Perlakuan | Baseline | Sesudah revisi | Pertambahan | Rentang | Data | Metadata | Snapshot |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `validation_001` (1 sel) | B0 | 95.896 | 119.972 | 24.076 | 24.075–24.085 | 161 | 23.915 | 1 |
| | B1 | 190.252 | 258.699 | 68.447 | 68.445–68.448 | 33.923 | 34.524 | 4 |
| | B2 | 64.079 | 88.643 | 24.564 | 24.563–24.565 | 37 | 24.527 | 1 |
| | B3 | 240.874 | 301.030 | 60.156 | 60.150–60.167 | 11.550 | 48.606 | 1+1 |
| `validation_002` (2 sel) | B0 | 95.878 | 119.906 | 24.028 | 24.028–24.031 | 253 | 23.775 | 1 |
| | B1 | 190.245 | 258.782 | 68.537 | 68.523–68.541 | 34.015 | 34.522 | 4 |
| | B2 | 64.077 | 88.833 | 24.756 | 24.755–24.757 | 128 | 24.628 | 1 |
| | B3 | 240.878 | 312.368 | 71.483 | 71.472–71.493 | 22.831 | 48.652 | 1+1 |

Pertambahan B3 terbagi atas store dan serving: 34.887 + 25.280 byte pada satu sel, dan 46.149 +
25.323 byte pada dua sel.

## Pemanggilan ulang setelah revisi

| Skenario | Perlakuan | Observasi resmi | Observasi sintetis | Total |
|---|---|---|---|---|
| `validation_001` | B0 | 13/38 | 1/1 | 14/39 |
| | B1 | 38/38 | 1/1 | 39/39 |
| | B2 | 14/38 | 0/1 | 14/39 |
| | B3 | 38/38 | 1/1 | 39/39 |
| `validation_002` | B0 | 12/38 | 2/2 | 14/40 |
| | B1 | 38/38 | 2/2 | 40/40 |
| | B2 | 13/38 | 1/2 | 14/40 |
| | B3 | 38/38 | 2/2 | 40/40 |

Setiap pembacaan yang berhasil cocok pada `observation_id` dan `value_lexeme`, identik pada ketiga
repetisi, dan sama dengan audit logis H9B baris per baris. Dengan demikian hasil logis H9B kini
terbukti secara fisik, bukan hanya secara simulasi.

### Temuan

1. **Pada revisi satu sel, B1 justru paling murah dalam waktu, dan B3 paling mahal.** B1 hanya
   menjalankan satu `INSERT OVERWRITE` (5,4 s) dan tidak perlu pemeliharaan, sedangkan B3 memerlukan
   dua pernyataan tulis (13,4 s) ditambah dua `expire_snapshots` (21,0 s). Penyebabnya bukan volume
   data melainkan ongkos tetap per pernyataan: menulis 14 baris sama mahalnya dengan menulis 1 baris
   pada skala ini. Keunggulan inkremental B3 tidak dapat muncul pada fixture 14 sel.
2. **Ongkos ruang B1 tetap, ongkos ruang B3 tumbuh mengikuti sel yang direvisi.** B1 menambah 68.447
   byte untuk satu sel dan 68.537 byte untuk dua sel, karena selalu menulis ulang seluruh state. B3
   menambah 60.156 byte untuk satu sel dan 71.483 byte untuk dua sel. Titik silangnya karena itu
   sudah terlewati pada dua sel di fixture ini: B3 lebih hemat pada satu sel, lebih boros pada dua
   sel. Angka ini belum boleh disebut titik impas P3, karena dua sel skenario ini berada di dua
   domain yang berbeda sehingga store B3 menulis dua file partisi.
3. **Metadata Iceberg mendominasi pertambahan byte.** Revisi satu nilai pada B0 hanya mengubah 161
   byte data, tetapi menambah 23.915 byte metadata. Pada B2 bahkan hanya 37 byte data berbanding
   24.527 byte metadata. Pada ukuran ini, ongkos satu revisi praktis adalah ongkos satu commit
   Iceberg, bukan ongkos datanya.
4. **B2 membayar penuh ongkos tulis meskipun menahan revisi.** Pada `validation_001`, B2 menulis
   ulang seluruh tabel seleksi (5,3 s, 24.564 byte) dan tetap tidak menyajikan nilai baru, karena
   revisi menyentuh sel berbasis WebAPI yang skornya kalah. Kebijakan sumber tunggal karena itu tidak
   menghemat ongkos tulis; yang hilang hanya informasinya.
5. **`expire_snapshots` adalah ongkos nyata perlakuan yang membuang histori.** B0, B2, dan B3
   menghabiskan 14–23 detik untuk memangkas snapshot pada setiap revisi, sedangkan B1 tidak
   memerlukannya sama sekali. Ongkos ini selama ini tidak terlihat pada hitungan baris logis H9B.

## Batas klaim

- Hasil hanya berlaku untuk fixture 38 observasi/14 sel dengan revisi 1 dan 2 sel. Urutan waktu
  maupun byte pada skala ini tidak boleh diekstrapolasi.
- Waktu yang dilaporkan adalah waktu pernyataan di dalam satu sesi Spark SQL pada VM 2 vCPU yang
  dibekukan. Angkanya hanya perbandingan antarperlakuan pada lingkungan itu, bukan klaim performa,
  throughput, atau skalabilitas.
- Nilai satu pernyataan mencakup ongkos tetap Spark dan Iceberg. Pada fixture ini ongkos tetap
  tersebut lebih besar daripada pekerjaan datanya, sehingga perbedaan antarperlakuan mencerminkan
  jumlah pernyataan, bukan jumlah baris.
- H10B adalah uji asap fisik pada profil validasi. Freeze eksperimen, profil sweep utama, dan aturan
  satu sumber per run tetap menjadi pekerjaan H11.
- Skenario `validation_002` sengaja memakai dua sumber, sehingga ia tidak memenuhi aturan sweep utama
  dan tidak boleh dipakai sebagai titik sweep.


## Reproduksi

```bash
make h10b-prepare                          # payload fisik dan hasil yang diharapkan
make h10b-cleanup H10B_CLEANUP=<label>     # di VM stack; sekali saja
make h10b-measure H10B_RUN=<label-baru>    # di VM stack; tidak menimpa run yang sudah ada
make h10b-run                              # agregasi dari results/raw/h10b/h10b-20260912
make test
```

## Artefak audit

- kontrak: `contracts/h10b-injected-revision-physical.json`;
- keputusan manusia: `config/h10/human_decisions.csv`;
- script pembersihan: `scripts/h10b_cleanup_orphans.sh`;
- script pengukuran: `scripts/h10b_measure.sh`;
- pipeline: `src/kkciv_vintage/h10b/`;
- payload fisik: `results/processed/h10b-synthetic-observations.csv`,
  `results/processed/h10b-b1-next-state.csv`, `results/processed/h10b-b2-next-state.csv`,
  `results/processed/h10b-b3-dirty-cells.csv`;
- hasil yang diharapkan dari H9B: `results/processed/h10b-expected-state.csv`,
  `results/processed/h10b-expected-recall.csv`;
- manifest payload: `data/manifests/h10b-physical-payload.json`;
- data mentah: `results/raw/h10b/cleanup-20260912/` dan `results/raw/h10b/h10b-20260912/`;
- waktu per pernyataan: `results/processed/h10b-statement-timing.csv`;
- ongkos per perlakuan: `results/processed/h10b-apply-cost.csv`;
- selisih byte per tabel: `results/processed/h10b-storage-delta.csv`;
- pemanggilan ulang setelah revisi: `results/processed/h10b-recall-after-revision.csv`;
- pembersihan orphan: `results/processed/h10b-orphan-cleanup.csv`;
- invariant: `results/processed/h10b-validation.csv`;
- ringkasan: `results/processed/h10b-summary.csv`;
- manifest: `data/manifests/h10b-injected-revision-physical.json`.
