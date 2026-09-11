# H9 Jalur B — Eksekusi Harness pada Revisi Kecil

## Status

H9 Jalur B menjalankan harness revisi tersuntik H8B untuk pertama kalinya. Kelima skenario profil
validasi (`1-2-4-7-14` sel) dikirim tanpa perubahan ke B0, B1, B2, dan B3, sehingga ada 20 route.
Seluruh route dieksekusi **secara logis** dengan adapter perlakuan yang memakai kembali logika
B0–B3 yang sudah diuji. Waktu, byte, dan eksekusi fisik di Iceberg belum diukur; ketiganya dijadwalkan
pada H10.

Marker `make h9b-run`:

```text
H9B_VERIFY|5|20|20|0|28|28|70|28|8|0|0|executed_logical
```

Artinya: 5 skenario, 20 route, 20 route dengan payload terverifikasi, 0 selisih payload, 28 baris
injeksi, 28 sel dihitung ulang oleh B3, 70 baris ditulis B1, 28 nilai lama yang hilang di B0, 8
revisi yang disajikan B2, 0 permintaan gagal pada B1/B3, 0 selisih replay baseline, dan status
`executed_logical`.

Commit implementasi `ea6efe1` ditarik ke VM `praktikum-sd` (`sigerciv@34.101.84.199`). Dua run
`make h9b-run` di VM menghasilkan marker yang sama dan checksum keluaran yang identik, termasuk dengan
keluaran lokal. Di VM, 83 test lulus, satu test PDF dilewati, dan working tree tetap bersih.

## Keputusan manusia yang dipakai

Pada 11 September 2026, peninjau manusia menyetujui empat keputusan sebelum H9B dijalankan, lalu
dua aturan adapter setelah hasil H9B ditinjau. Keenamnya dicatat di `config/h9/human_decisions.csv`
dan diperiksa oleh pipeline. Karena ada dua keputusan tambahan, kontrak naik dari `h9b.1` ke `h9b.2`.
Keluaran route tidak berubah; yang berubah hanya baris validasi dan manifest.

| ID | Keputusan |
|---|---|
| `h9_b3_history_as_rows` | B3 menyimpan histori sebagai baris append-only dan boleh menghapus snapshot tabel |
| `h9_b3_resolution_key` | versi terbaru dipilih berdasarkan `vintage_date`, lalu `retrieved_at`, lalu `vintage_id` |
| `h9_b3_materialized_serving` | tabel serving B3 dimaterialisasi; 52 baris logis pada fixture H6 dilaporkan sebagai ongkos |
| `h9_synthetic_vintage_ordering` | vintage sintetis bertanggal sehari setelah vintage resmi terbaru (2026-09-09), `retrieved_at` pukul `00:00:00+00:00`, dan `vintage_id` sebagai pemecah seri |
| `h9b_b2_synthetic_scoring` | B2 menilai baris sintetis memakai skor beku `revised_source_id` |
| `h9b_synthetic_cell_lineage` | observasi sintetis mencapai sel melalui edge H6C milik observasi dasarnya |

Tiga keputusan pertama menyetujui desain B3 yang sudah berjalan pada H9A, sehingga kontrak dan
keluaran H9A tidak berubah. Keputusan keempat menutup status `pending_human_decision` pada kontrak
H9A. Aturan tersebut dijalankan oleh adapter H9B.

## Adapter perlakuan

Untuk setiap skenario, payload H8B diubah menjadi satu **vintage sintetis**. Vintage ini mempunyai
`source_id = synthetic_revision_harness`, label rilis bertanda "not BPS", producer
`synthetic_revision_harness`, dan `evidence_level = synthetic_not_official`. Satu-satunya yang
diwarisi dari observasi dasar adalah metodologi. Vintage sintetis kemudian ditambahkan ke workload
nyata H6 dan diproses oleh logika perlakuan yang sama dengan H7–H9:

| Perlakuan | Adapter |
|---|---|
| B0 | replay overwrite H7 dengan empat batch |
| B1 | replay snapshot penuh H8; skenario menambah snapshot keempat |
| B2 | peringkat skor beku H6B; baris sintetis dinilai memakai skor `revised_source_id`, dan seri dipecah oleh `vintage_date` terbaru, lalu `source_id`, lalu `observation_id` |
| B3 | replay H9 dengan empat kedatangan; observasi sintetis mencapai selnya melalui edge H6C milik observasi dasar yang direvisinya |

Sebelum skenario dijalankan, keempat adapter menjalankan replay tanpa injeksi. Hasil replay harus
sama dengan state manifest B0, B1, B2, dan B3 pada 56 sel (4 × 14). Hasilnya 0 selisih. Setiap route
juga menghitung ulang checksum payload skenarionya dan harus cocok dengan checksum route H8B; hasilnya
20 dari 20 cocok.

## Hasil per skenario

| Skenario | Sel | Campuran sumber | B0 tulis | B1 tulis | B2 revisi disajikan | B3 dihitung ulang | B3 tulis |
|---|---:|---|---:|---:|---:|---:|---:|
| validation_001 | 1 | WebAPI 1 | 1 | 14 | 0 | 1 | 2 |
| validation_002 | 2 | TPB 2025 1, WebAPI 1 | 2 | 14 | 1 | 2 | 4 |
| validation_004 | 4 | TPB 2025 1, WebAPI 3 | 4 | 14 | 1 | 4 | 8 |
| validation_007 | 7 | TPB 2025 2, WebAPI 5 | 7 | 14 | 2 | 7 | 14 |
| validation_014 | 14 | TPB 2025 4, WebAPI 10 | 14 | 14 | 4 | 14 | 28 |

"Tulis" adalah jumlah baris logis yang ditulis perlakuan untuk skenario itu, bukan byte. B3 menulis
satu baris store dan satu baris serving untuk setiap sel yang direvisi.

### Temuan

1. **B0, B1, dan B3 menyajikan setiap revisi.** Pada kelima skenario, ketiganya menyajikan vintage
   terbaru di seluruh 14 sel.
2. **B2 mengabaikan revisi terhadap sumber berskor lebih rendah.** Revisi atas sel berbasis WebAPI
   (skor 0,907143) kalah dari observasi TPB 2025 (skor 0,962500) yang sudah terpilih. Hanya revisi
   atas sel berbasis TPB 2025 yang menang, melalui seri skor dan tanggal yang lebih baru. Dari 28
   revisi, B2 menyajikan 8 dan mengabaikan 20 tanpa tanda apa pun di state serving. Ini konsekuensi
   langsung kebijakan *Trust Your Friend* yang dibekukan pada H6B, bukan bug.
3. **B0 kehilangan nilai yang direvisi.** Seluruh 28 observasi dasar yang direvisi tidak dapat
   dipanggil lagi. B0 hanya dapat menjawab 14 permintaan per skenario.
4. **B1 dan B3 mempertahankan semuanya.** Semua 38 observasi resmi ditambah observasi sintetis tetap
   dapat dipanggil, yaitu 39 sampai 52 permintaan per skenario, tanpa kegagalan.
5. **B3 menghitung ulang tepat sel yang direvisi.** Jumlah evaluasi sama dengan ukuran skenario
   (1, 2, 4, 7, 14), dan setelah setiap kedatangan hasilnya sama dengan penghitungan ulang penuh.

### Pengamatan logis yang tidak boleh dibaca sebagai hasil performa

B1 selalu menulis 14 baris per skenario, berapa pun ukuran revisinya. B3 menulis `2n` baris. Pada
hitungan baris logis, B3 menulis lebih sedikit bila `n < 7`, sama pada `n = 7`, dan lebih banyak pada
`n = 14`. Pola ini mengarah pada titik impas yang dicari P3. Namun hitungan ini mengabaikan ukuran
file, metadata Iceberg, biaya `MERGE`, dan pembacaan. Jangan menyebut titik impas 50 persen sebagai
temuan sebelum H10–H11 mengukur waktu dan byte.

## Batas lingkup

- Profil `1-2-4-7-14` masih profil validasi dan **bukan** freeze H10.
- Empat dari lima skenario validasi berisi revisi dari lebih dari satu sumber. Hal ini diizinkan untuk
  profil validasi, tetapi sweep utama wajib memakai tepat satu sumber per run (keputusan H8B,
  2026-09-10).
- Artefak H8B tetap berstatus `prepared_not_run` karena artefak itu tidak diubah. Status eksekusi
  logis dicatat terpisah pada `h9b-route-executions.csv`.
- Eksekusi fisik keempat perlakuan pada satu skenario kecil, lengkap dengan waktu dan byte, adalah
  pekerjaan H10 Jalur B.

## Reproduksi

```bash
make h9b-run
make test
```

`make h9b-run` membutuhkan manifest H6, H6B, H6C, H8B, B0, B1, B2, dan B3 yang valid. Bila salah
satu perlakuan dijalankan ulang dengan keluaran berbeda, replay baseline akan gagal sampai H9B
dijalankan ulang di atas keluaran baru.

## Artefak audit

- kontrak: `contracts/h9b-small-revision-execution.json`;
- keputusan manusia: `config/h9/human_decisions.csv`;
- pipeline: `src/kkciv_vintage/h9b/`;
- 20 eksekusi route: `results/processed/h9b-route-executions.csv`;
- 280 baris state serving setelah revisi: `results/processed/h9b-post-revision-states.csv`;
- 872 baris audit pemanggilan: `results/processed/h9b-recall-audit.csv`;
- 5 vintage sintetis: `results/processed/h9b-synthetic-vintages.csv`;
- invariant: `results/processed/h9b-validation.csv`;
- ringkasan: `results/processed/h9b-summary.csv`;
- manifest: `data/manifests/h9b-small-revision-execution.json`.

## Hal yang memerlukan audit manusia

1. Setujui cara naskah membahas B2 yang mengabaikan 20 revisi WebAPI. Rekomendasi per
   2026-09-11:
   - bahas sebagai sifat kelas kebijakan pemilihan satu sumber, bukan kesalahan implementasi B2
     atau SDG-KG;
   - ukur dengan metrik pendukung *tingkat propagasi revisi* (revisi yang tampil ÷ revisi yang
     masuk). Pada profil validasi nilainya B0 = B1 = B3 = 1,000 dan B2 = 8/28 = 0,286. Metrik ini
     dibekukan pada freeze H10, sebelum eksperimen utama, dan dicatat sebagai tambahan setelah profil
     validasi;
   - gabungkan dengan bukti nyata H7B, yaitu 10 dari 14 sel B2 yang menyajikan nilai bukan vintage
     terbaru;
   - nyatakan batas validitas: hasil bergantung pada bobot H6B yang dibekukan. Varian B2 yang
     mempertimbangkan kebaruan hanya boleh menjadi versi eksperimen baru.
2. **Disetujui 2026-09-11:** adapter B2 menilai baris sintetis memakai skor `revised_source_id`
   (`h9b_b2_synthetic_scoring`).
3. **Disetujui 2026-09-11:** observasi sintetis mewarisi edge sel dari observasi dasar yang
   direvisinya (`h9b_synthetic_cell_lineage`).
4. Tetapkan skenario kecil satu sumber untuk eksekusi fisik H10 Jalur B. Rekomendasi: bekukan dua
   skenario smoke 1-sel, yaitu `validation_001` (WebAPI, jalur B2 yang menahan revisi) dan satu sel
   TPB 2025 dengan seed yang sama (jalur B2 yang mempropagasikan revisi). Dengan begitu kedua
   perilaku B2 teruji secara fisik, dan setiap run tetap memakai satu sumber.
