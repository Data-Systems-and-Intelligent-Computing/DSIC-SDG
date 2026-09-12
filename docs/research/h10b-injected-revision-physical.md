# H10 Jalur B — Eksekusi Fisik Satu Revisi Tersuntik pada Keempat Perlakuan

## Status

H10 Jalur B menjalankan revisi tersuntik yang sudah dibekukan H8B secara **fisik** di Iceberg, bukan
lagi secara logis seperti H9B. Untuk setiap skenario, keempat tabel perlakuan dibangun ulang dari
workload nyata H6, lalu satu revisi dimasukkan melalui mekanisme tulis milik masing-masing perlakuan.
Yang diukur adalah waktu pernyataan SQL dan pertambahan byte akibat revisi itu.

<!-- STATUS_MARKER -->

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

<!-- ORPHAN_MARKER -->

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

<!-- RESULTS_MARKER -->

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
