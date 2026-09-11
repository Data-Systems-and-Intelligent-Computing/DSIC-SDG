# H9 Jalur A — B3 Vintage-Aware dengan Penghitungan Ulang Inkremental

## Status

H9 Jalur A mengimplementasikan perlakuan usulan B3 pada workload revisi nyata yang sama dengan
B0, B1, dan B2: 38 observasi, 14 sel stabil, dan tiga rilis berurutan. Implementasi logis, kontrak,
DDL dua tabel, script integrasi Iceberg, serta 5 unit test baru sudah selesai. Seluruh 79 test lokal
lulus. Marker logis yang dihasilkan `make h9-run` adalah:

```text
H9_LOGIC|38|14|3|38|42|38|0|42|implemented
```

Artinya: 38 baris store, 14 baris serving, 3 kedatangan rilis, 38 evaluasi sel inkremental, 42
evaluasi bila dihitung ulang penuh, 38 pembacaan vintage berhasil, 0 gagal, 42 baris rekonstruksi
as-of, dan status implemented.

Integrasi Iceberg melalui `make h9-apply` lulus pada VM eksperimen `praktikum-sd`, yang sejak
11 September 2026 beralamat `sigerciv@34.101.84.199`. VM menarik commit implementasi `c2a249d` dengan
`git pull --ff-only`. Dua run `make h9-run` menghasilkan checksum keluaran yang sama dengan lokal.
`make h9-apply` dijalankan dua kali untuk menguji idempotensi drop-and-recreate, dan kedua run
mencetak marker yang sama:

```text
H9_ARRIVAL|1|14|14|14|14|0
H9_ARRIVAL|2|28|14|14|14|0
H9_ARRIVAL|3|38|14|10|10|0
H9_VERIFY|38|38|14|14|38|0|1|1|0|0|42|0
```

Di VM, 78 test lulus dan satu test ekstraksi PDF dilewati karena PDF mentah tidak disimpan di Git.
Working tree VM tetap bersih. Arti setiap field marker dijelaskan pada bagian Reproduksi.

## Kontrak perlakuan

B3 menyimpan histori sebagai **baris**, bukan sebagai snapshot tabel. Kontraknya adalah
`contracts/h9-b3-vintage-aware.json` (`b3.1`) dengan dua tabel:

| Tabel | Kunci | Cara tulis | Isi |
|---|---|---|---|
| `kkciv.experiments.b3_observation_vintages` | `(cell_id, vintage_id)` | `INSERT` saja; tanpa `UPDATE`, `DELETE`, atau `MERGE` | seluruh kolom H6 ditambah `source_id`, `vintage_date`, `vintage_retrieved_at`, `arrival_order` |
| `kkciv.experiments.b3_indicator_current` | `cell_id` | `MERGE` hanya untuk sel kotor | baris store yang terpilih ditambah `vintage_count`, `value_revision_count`, `recomputed_at_arrival` |

Nilai current untuk satu sel adalah vintage tersimpan dengan kunci resolusi terbesar, yaitu
`vintage_date`, `vintage_retrieved_at`, lalu `vintage_id`. Urutan ini sama dengan urutan rilis yang
dipakai B0 dan B1. Kunci resolusi diambil dari metadata vintage, bukan dari urutan kedatangan, sehingga
rilis lama yang datang terlambat tidak menimpa vintage yang lebih baru.

Kolom `vintage_count` dan `value_revision_count` sengaja disimpan di tabel serving. Keduanya
bergantung pada seluruh histori sel, sehingga tabel serving benar-benar merupakan view turunan yang
harus dihitung ulang ketika histori berubah. B0 tidak dapat menghitung kedua kolom ini karena
histori sudah hilang.

## Penghitungan ulang berbasis lineage

Untuk setiap rilis yang datang, pipeline menjalankan urutan berikut.

1. Baris rilis ditambahkan ke store. Kunci `(cell_id, vintage_id)` atau `observation_id` yang sudah
   ada ditolak.
2. Setiap observasi yang datang dicari pada graf H6C. Sel kotor adalah node `indicator_cell` yang
   dicapai melalui edge `observation_materializes_cell`. Bila edge tidak ada atau menunjuk sel lain
   daripada `cell_id` observasi, run berhenti. Tidak ada fuzzy matching.
3. Hanya sel kotor yang dihitung ulang dari store. Sel lain tidak disentuh.
4. Hasil inkremental dibandingkan dengan penghitungan ulang penuh atas seluruh store. Keduanya harus
   sama pada seluruh kolom H6, `vintage_count`, dan `value_revision_count`.

| Kedatangan | Rilis | Baris masuk | Sel kotor | Tidak disentuh | Evaluasi penuh | Nilai berubah | Provenance saja | Store setelahnya |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | TPB 2024 | 14 | 14 | 0 | 14 | 0 (14 baru) | 0 | 14 |
| 2 | TPB 2025 | 14 | 14 | 0 | 14 | 4 | 10 | 28 |
| 3 | WebAPI 2026 | 10 | 10 | 4 | 14 | 10 | 0 | 38 |

Secara total B3 mengevaluasi 38 sel, sedangkan penghitungan ulang penuh setelah setiap rilis
mengevaluasi 42 sel. Rasio kerja logisnya `38/42 = 0,9048`. Pada ketiga kedatangan, hasil
inkremental sama persis dengan hasil penghitungan ulang penuh.

Angka ini perlu dibaca apa adanya: **pada revisi nyata H6, hampir semua sel tersentuh setiap rilis,
sehingga penghematan inkremental kecil.** Hanya empat evaluasi yang dapat dilewati, yaitu empat sel
yang tidak mempunyai nilai WebAPI 2026. Keunggulan B3 bergantung pada seberapa kecil bagian sel yang
direvisi. Pertanyaan itu dijawab oleh sweep revisi tersuntik pada H10–H11, bukan oleh workload ini.

## Kesetaraan dengan B0 dan B1

- State serving akhir sama dengan state latest-vintage B0 dan snapshot terakhir B1 pada seluruh kolom
  observasi H6: 10 sel dari WebAPI 2026 dan 4 sel dari TPB 2025.
- Untuk setiap rilis, B3 merekonstruksi state as-of dari store: vintage terbaru per sel yang kunci
  resolusinya tidak melewati rilis tersebut. Ketiga state as-of, masing-masing 14 baris dengan total 42,
  sama persis dengan tiga snapshot logis B1.
- Distribusi histori pada state akhir: 10 sel memiliki tiga vintage dan 4 sel memiliki dua vintage.
  Setiap sel memiliki tepat satu perubahan nilai sepanjang historinya (`value_revision_count = 1`),
  sehingga totalnya 14, sama dengan jumlah overwrite yang mengubah nilai pada B0.

Artinya B3 dapat menghasilkan kembali semua yang dapat dihasilkan B1 tanpa bergantung pada time
travel tabel.

## Audit reproducibility

Setiap `observation_id` dari 38 masukan dicari melalui kunci `(cell_id, vintage_id)` di store, lalu
dibandingkan pada ID observasi, nilai `DECIMAL(38,10)`, dan `value_lexeme`:

- 14 observasi adalah current dan juga tersedia di tabel serving;
- 24 observasi historis tersedia melalui kunci vintage;
- tidak ada permintaan yang gagal, sehingga tingkat keberhasilan `38/38 = 1,0000`.

Kontrak menyatakan `depends_on_table_snapshots = false`. Untuk membuktikannya di Iceberg, script
integrasi memanggil `expire_snapshots` pada kedua tabel B3 sampai tersisa satu snapshot, lalu
mengulang seluruh audit. Hasil yang diharapkan tetap 38/38. Perbedaannya dengan B1 menjadi tegas:
B1 memerlukan snapshot lama, sedangkan B3 tidak.

## Sifat yang diuji di unit test

Selain determinisme dan jumlah baris, unit test H9 menguji tiga sifat yang tidak terlihat pada
workload berurutan.

1. **Independensi urutan kedatangan.** Bila rilis datang terbalik (WebAPI 2026, TPB 2025, lalu
   TPB 2024), state serving akhir dan ketiga state as-of tetap sama. Rilis lama yang datang belakangan
   membuat sel kotor dihitung ulang, tetapi observasi terpilihnya tidak berubah
   (`unchanged_resolution_cells > 0`). B0 pada kondisi yang sama akan menimpa nilai baru dengan nilai
   lama.
2. **Ketergantungan pada lineage.** Edge H6C yang diarahkan ke sel lain atau dihapus membuat run
   berhenti dan tidak menebak sel kotor.
3. **Append-only.** Kontrak, DDL, dan script integrasi ditolak bila memuat `UPDATE`, `DELETE FROM`,
   `MERGE INTO`, atau `INSERT OVERWRITE` terhadap tabel store.

## Jejak logis dan batas pengukuran

| Perlakuan | Baris logis tersimpan | Keterangan |
|---|---:|---|
| B0 | 14 | state current saja |
| B1 | 42 | 3 snapshot × 14 sel, termasuk 4 baris yang dibawa maju |
| B3 | 52 | 38 baris store + 14 baris serving turunan |

Pada fixture kecil ini **B3 menyimpan lebih banyak baris logis daripada B1**, karena tabel serving
ikut dimaterialisasi dan tiga rilis hampir menyentuh seluruh sel. Temuan ini tidak disembunyikan.
Baris logis bukan byte: B1 dapat berbagi data file antarsnapshot, dan tabel serving B3 dapat dibentuk
ulang dari store. Ukuran fisik, waktu tulis, dan waktu baca baru sah setelah protokol H10 dijalankan.
H9 tidak mengklaim B3 lebih cepat atau lebih hemat ruang.

## Batas terhadap harness H8B

Pada saat H9A dibekukan, route B3 pada harness H8B masih berstatus `prepared_not_run`, dan kontrak
mencatat urutan vintage sintetis sebagai `pending_human_decision`. Pada 11 September 2026, keputusan
itu disetujui: vintage sintetis bertanggal sehari setelah vintage resmi terbaru, dengan `retrieved_at`
pukul `00:00:00+00:00` dan `vintage_id` sebagai pemecah seri. Keputusan tersimpan di
`config/h9/human_decisions.csv`. Route B3 kemudian dieksekusi secara logis oleh H9 Jalur B (lihat
`docs/research/h9b-small-revision-execution.md`). Kontrak `b3.1` tidak diubah karena perilaku B3
sendiri tidak berubah.

## Reproduksi

```bash
make h9-run
make test
make h9-apply
```

`make h9-run` memvalidasi input bermanifest (H6, H6C, B0, B1), membangun artefak deterministik,
membandingkan hasil dengan B0 dan B1, lalu menulis manifest H9. `make h9-apply` menjatuhkan dan
membuat ulang hanya dua tabel B3, lalu menjalankan tiga kedatangan. Setiap kedatangan terdiri atas
`INSERT` ke store dan `MERGE` sel kotor ke serving. Setelah itu script melakukan expire snapshot dan
verifikasi.

Marker yang harus muncul pada VM eksperimen:

```text
H9_ARRIVAL|1|14|14|14|14|0
H9_ARRIVAL|2|28|14|14|14|0
H9_ARRIVAL|3|38|14|10|10|0
H9_VERIFY|38|38|14|14|38|0|1|1|0|0|42|0
```

`H9_ARRIVAL` berisi urutan kedatangan, baris store, baris serving, sel yang dihitung ulang pada
kedatangan itu, sel kotor dari berkas impact, dan selisih antara serving dan penghitungan ulang penuh.
`H9_VERIFY` berisi baris store, kunci unik, baris serving, sel unik, pembacaan vintage berhasil,
gagal, snapshot store dan serving setelah expire, selisih serving terhadap CSV, selisih terhadap
penghitungan ulang penuh, baris as-of, dan selisih as-of terhadap snapshot B1.

## Artefak audit

- kontrak: `contracts/h9-b3-vintage-aware.json`;
- DDL: `infra/spark/h9-b3.sql`;
- pipeline: `src/kkciv_vintage/h9/`;
- integrasi Iceberg: `scripts/h9_apply.sh`;
- katalog tiga kedatangan: `results/processed/h9-b3-arrival-catalog.csv`;
- 38 baris store append-only: `results/processed/h9-b3-observation-store.csv`;
- 38 baris impact berbasis lineage: `results/processed/h9-b3-impact.csv`;
- 14 baris serving: `results/processed/h9-b3-current-state.csv`;
- 42 baris rekonstruksi as-of: `results/processed/h9-b3-asof-states.csv`;
- audit 38 permintaan: `results/processed/h9-b3-reproducibility.csv`;
- invariant: `results/processed/h9-b3-validation.csv`;
- ringkasan: `results/processed/h9-b3-summary.csv`;
- manifest: `data/manifests/h9-b3-vintage-aware.json`.

## Hal yang memerlukan audit manusia

1. **Disetujui 2026-09-11:** B3 menyimpan histori sebagai baris append-only dan boleh menghapus
   snapshot tabel. Keputusan ini membuat B3 berbeda secara prinsip dari B1.
2. **Disetujui 2026-09-11:** kunci resolusi `vintage_date`, `vintage_retrieved_at`, `vintage_id`.
   Pada dua rilis bertanggal sama, `retrieved_at` menjadi penentu.
3. Setujui definisi sel kotor sebagai sel yang dicapai dari observasi yang datang melalui edge lineage
   H6C, bukan sel yang nilainya berubah. Rilis lama yang datang terlambat tetap membuat sel kotor.
4. **Disetujui 2026-09-11:** tabel serving dimaterialisasi. Tanpa materialisasi, jumlah baris logis
   turun menjadi 38, tetapi tidak ada lagi view yang dipelihara secara inkremental.
5. Jangan memakai rasio 0,9048 atau angka 52 baris sebagai klaim performa atau ruang.
6. **Disetujui 2026-09-11:** urutan vintage sintetis adalah sehari setelah vintage resmi terbaru.
