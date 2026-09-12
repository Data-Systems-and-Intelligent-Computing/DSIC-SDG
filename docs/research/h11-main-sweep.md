# Sweep Revisi Tersuntik Utama (H11)

## Status

H11 menjalankan sweep utama yang menjawab P3: keempat perlakuan dibangun ulang pada panel provinsi
beku, satu revisi tersuntik berukuran 1 sampai 38 sel disuntikkan melalui mekanisme tulis masing-masing
perlakuan, lalu waktu, byte, jumlah sel yang dievaluasi, recall, dan propagasi revisi diukur pada
setiap titik. Konfigurasi seluruhnya mengikuti freeze 12 September 2026 di
[`docs/research/experiment-freeze.md`](experiment-freeze.md); tidak ada parameter yang ditetapkan
setelah melihat hasil.

Kontrak eksekusi ada di [`contracts/h11-main-sweep.json`](../../contracts/h11-main-sweep.json).
Jalankan `make h11-prepare`, lalu `make h11-measure` di host stack, lalu `make h11-run`.

## Mengapa panel, bukan fixture

H10B memperlihatkan bahwa pada fixture 14 sel ongkos tetap satu pernyataan Spark lebih besar
daripada pekerjaan datanya: B1 yang menulis ulang seluruh state justru tercepat, dan pertambahan
byte B1 sama untuk revisi satu sel maupun dua sel. Pada keadaan sebesar itu titik impas tidak
mungkin teramati, karena yang dibandingkan sebenarnya adalah jumlah pernyataan, bukan jumlah
pekerjaan. Keputusan `h10c_sweep_workload` karena itu memindahkan sweep P3 ke panel provinsi dan
mempertahankan fixture 14 sel sebagai basis bukti P1, P2, dan P4.

## Panel yang menjadi keadaan dasar

Panel diturunkan dari batch ingestion H4 `h4-2981e0fb3bc2d960` dan diproyeksikan ke skema vintage
H6 tanpa mengubah satu pun keputusan H6.

| Besaran | Nilai |
|---|---:|
| baris H4 yang masuk | 7.666 |
| baris duplikat `(cell_id, source_id)` yang dibuang | 683 |
| observasi panel | 6.983 |
| sel indikator | 5.378 |
| vintage (rilis) | 4 |

Empat vintage tersebut adalah TPB 2024 (rilis 2024-12-31), TPB 2025 (2025-12-30), snapshot WebAPI H1
(ditarik 2026-09-08 pukul 14:04:19 UTC), dan snapshot WebAPI H3 (hari yang sama pukul 23:38:59 UTC).
Kedua snapshot WebAPI berbeda manifest, sehingga `vintage_id`-nya berbeda meskipun `release_date`-nya
sama; urutan kedatangan ditentukan oleh `(vintage_date, retrieved_at, vintage_id)`, persis aturan
resolusi H9. Manifest sumber dipilih menurut dataset asal baris: `h3_province_webapi` berasal dari
snapshot H1 dan `h3_release_reconciliation` dari snapshot H3, sebagaimana tercatat pada manifest H3
dan H4.

Aturan pembuangan duplikat perlu dinyatakan lengkap karena freeze hanya menyebut jumlahnya. Dari 683
kelompok duplikat, seluruhnya berisi tepat dua baris dengan nilai, satuan, dan bentuk angka yang
identik; 665 di antaranya adalah sel WebAPI yang muncul pada kedua snapshot dan 18 adalah sel
publikasi TPB 2024 yang muncul dengan dua locator berbeda. Baris yang dipertahankan adalah yang
penarikannya paling baru, lalu `source_record_id` terkecil bila penarikannya sama. Seluruh 683
pasangan beserta buktinya tercatat di
[`results/processed/h11-panel-duplicates.csv`](../../results/processed/h11-panel-duplicates.csv).
Alasan pembuangan tetap yang dibekukan: B3 mensyaratkan kunci `(cell_id, vintage_id)` yang unik.

Kolom `trace_id` dan `cause_family` pada baris panel dibiarkan kosong dan `evidence_level` diisi
`official_panel`. Jejak revisi H5 hanya ada untuk 14 sel fixture, dan klasifikasi sebab P1 hidup pada
tingkat kejadian H4, bukan pada tingkat observasi. Ketiga kolom itu tidak pernah dibaca oleh
keputusan perlakuan, skor kepercayaan, maupun metrik apa pun.

## Keadaan dasar setiap perlakuan

Panel tidak dimuat sebagai satu blok. Keempat rilis datang berurutan dan setiap perlakuan
menerapkan mekanisme tulisnya sendiri pada setiap kedatangan, sehingga keadaan sebelum revisi adalah
keadaan yang memang dihasilkan perlakuan itu.

| Perlakuan | Tabel | Baris dasar | Snapshot Iceberg | Mekanisme muat |
|---|---|---:|---:|---|
| B0 | `kkciv.sweep.b0_panel_current` | 5.378 | 1 | satu `MERGE` per rilis, lalu `expire_snapshots` |
| B1 | `kkciv.sweep.b1_panel_full_snapshots` | 10.106 | 4 | satu `INSERT OVERWRITE` per rilis, memuat seluruh state sampai rilis itu |
| B2 | `kkciv.sweep.b2_panel_selected` | 5.378 | 1 | satu `INSERT OVERWRITE` seleksi skor beku H6B, lalu `expire_snapshots` |
| B3 | `kkciv.sweep.b3_panel_observation_vintages` | 6.983 | 1 | satu `INSERT` per rilis ke store append-only |
| B3 | `kkciv.sweep.b3_panel_current` | 5.378 | 1 | satu `MERGE` sel kotor per rilis, lalu `expire_snapshots` |

Empat state B1 berukuran 1.560, 1.584, 1.584, dan 5.378 baris. Ukurannya tidak sama karena panel
bertambah ketika rilis baru masuk; ini berbeda dari fixture 14 sel yang setiap rilisnya menutup
seluruh sel. Konsekuensinya, simulator B1 milik H8 tidak dapat dipakai apa adanya, karena ia
memeriksa bahwa setiap rilis mencakup jumlah sel yang sama. H11 memakai pembentuk state sendiri
dengan semantik B1 yang sama dan tanpa invarian khusus fixture tersebut.

Skor kepercayaan B2 dipakai apa adanya dari H6B (F4.5) dan tidak dihitung ulang di atas panel.
Dimensi `workload_cell_coverage` pada skor itu didefinisikan atas 14 sel workload H6; menghitungnya
ulang di atas panel berarti mengubah nilai yang dibekukan, dan itu hanya boleh dilakukan sebagai
versi eksperimen baru. Dengan skor beku tersebut B2 memilih TPB 2025, lalu TPB 2024, lalu WebAPI;
pada panel hasilnya 1.522 sel dari TPB 2024, 62 sel dari TPB 2025, dan 3.794 sel dari WebAPI.

Sel kotor B3 diturunkan dari edge lineage, bukan dari pembandingan nilai, sesuai F4.4. Lineage panel
dibentuk dengan kode H6C yang sama dan menghasilkan 19.379 node serta 41.928 edge; 6.983 edge
`observation_materializes_cell`-nya disimpan di
[`results/processed/h11-panel-impact-edges.csv`](../../results/processed/h11-panel-impact-edges.csv)
dan itulah yang dibaca pernyataan `MERGE` B3, baik saat memuat panel maupun saat menyuntikkan revisi.

## Beban revisi

Semesta sweep adalah `sdg08_productivity_growth` seri `total` satuan persen periode 2025 pada 38
provinsi, seluruhnya dilayani `bps_webapi`. Peringkat ke-38 sel dibentuk ulang dari seed `20260912`
dengan aturan SHA-256 yang sama seperti H8B, lalu dicocokkan baris per baris terhadap
[`config/experiments/main_sweep_universe.csv`](../../config/experiments/main_sweep_universe.csv);
nilai dasar dan sumber dasar setiap sel juga diperiksa terhadap keadaan panel, sehingga sweep berhenti
bila panel bergeser. Skenario berukuran `k` mengambil `k` peringkat pertama, sehingga setiap skenario
merupakan subset skenario yang lebih besar.

Aturan mutasi mengikuti F6.1 tanpa perubahan: nilai dasar adalah vintage terbaru sel itu, nilainya
digeser tepat satu unit presisi publikasi, dan arahnya dibalik bila persentase akan melewati 100.
Dimensi sel tidak pernah berubah dan setiap baris ditandai `synthetic_not_official`. Revisi masuk
sebagai vintage sintetis bertanggal 2026-09-09, yaitu kedatangan kelima.

Yang dikontrol pada sweep ini adalah **jumlah sel** yang direvisi, bukan besar perubahan nilainya.
Perubahan satu unit adalah pemicu dependensi, bukan model besaran revisi BPS.

## Yang diukur dan bagaimana

Setiap titik dijalankan tiga kali dalam siklus purge-rebuild-suntik-ukur yang berurutan, dan seluruh
repetisi dilaporkan sebelum agregasi apa pun. Waktu diambil dari baris `Time taken` satu sesi Spark
SQL per perlakuan, sehingga start-up JVM dan pembuatan view tidak masuk ongkos perlakuan; pembuatan
view dicatat terpisah sebagai ongkos harness. Ruang dihitung dari seluruh objek yang terjangkau dari
metadata snapshot yang dipertahankan, dengan ukuran diambil dari listing MinIO, dan setiap objek yang
dirujuk metadata wajib ada dengan ukuran yang sama persis.

Definisi `cells_evaluated` mengikuti metrik beku m2: B0 dan B3 hanya mengevaluasi sel yang menjadi
sasaran pernyataannya, sedangkan B1 dan B2 menghitung ulang seluruh sel pada state yang mereka tulis
ulang. Perlu dicatat sebagai penyimpangan pelaporan: tabel `h10b-apply-cost.csv` mengisi kolom yang
sama untuk B2 dengan jumlah sel yang direvisi. H11 memakai definisi beku, sehingga angka B2 di kedua
tabel tidak dapat dibandingkan langsung.

Satu keputusan implementasi perlu dinyatakan di muka. Mekanisme B1 yang dibekukan adalah
`INSERT OVERWRITE` seluruh state per rilis, sehingga pada setiap revisi B1 menulis ulang seluruh
tabel, bukan hanya state baru. Iceberg tidak dapat menulis ulang sebuah tabel dari `SELECT` atas
tabel itu sendiri, sehingga state-state lama dibentuk ulang dari view panel beku di dalam pernyataan
yang sama. Ongkos yang terukur karena itu adalah ongkos penuh B1: menghitung ulang keadaan dan
menuliskan seluruh tabel.

Jumlah byte yang dibaca (metrik pendukung s2) tidak diukur pada H11, karena Spark SQL CLI pada stack
beku tidak mengekspos statistik pembacaan per pernyataan. Hal ini dinyatakan dalam kontrak, bukan
disembunyikan.

## Verifikasi sebelum angka dipakai

Setiap pernyataan revisi diikuti pemeriksaan keadaan di dalam sesi yang sama. Sel yang direvisi
dibandingkan terhadap prediksi beku di
[`results/processed/h11-expected-revised.csv`](../../results/processed/h11-expected-revised.csv),
sedangkan seluruh sel lain dibandingkan terhadap keadaan panel yang dihitung secara independen dari
pernyataan yang sedang diukur. Prediksi itu dibuat pada tahap `prepare` oleh simulator Python
perlakuan, sebelum ada satu pun pengukuran fisik.

Selama pengembangan harness, pemeriksaan ini pernah melaporkan 10.754 ketidaksesuaian pada seluruh
perlakuan. Penyebabnya bukan data, melainkan `EXCEPT` dan `UNION ALL` yang berbagi presedensi di
Spark SQL, sehingga perbandingan terbaca ulang menjadi bentuk lain. Bug diperbaiki dengan
memberi tanda kurung eksplisit, dan dua run uji satu skenario (`smoke-01`, `smoke-02`, keduanya
ditandai `limited_run=yes`) dipakai untuk memastikan pemeriksaan kembali bernilai nol sebelum sweep
utama dijalankan. Kedua run uji itu dibuang dan tidak masuk hasil; skrip agregasi menolak run yang
ditandai terbatas.

## Hasil

Sweep dijalankan pada 12 September 2026 pukul 17:30:53 sampai 19:39:57 UTC, yaitu 18 siklus berurutan
selama 2 jam 9 menit, dari commit `d32308e` dengan working tree bersih. Seluruh 72 route dieksekusi
dan kedua belas invarian lolos, termasuk 72 pemeriksaan keadaan yang seluruhnya nol selisih dan 18
pembangunan ulang keadaan dasar yang menghasilkan marker identik. Marker:

```
H11_VERIFY|3|6|72|6983|5378|24.652|10.056|24.616|38.007|24.861|10.068|23.052|35.626|
14459|469682|26363|52873|0.7660|1.0000|0.7660|1.0000|none|none|measured
```

### Waktu penghitungan ulang

Waktu median tiga repetisi, dalam detik, dengan tulis dan pemeliharaan dipisah.

| Sel direvisi | B0 | B1 | B2 | B3 |
|---:|---:|---:|---:|---:|
| 1 | 24,652 | 10,056 | 24,616 | 38,007 |
| 2 | 26,018 | 10,286 | 22,830 | 37,563 |
| 4 | 24,823 | 10,181 | 23,458 | 36,920 |
| 8 | 25,023 | 9,911 | 24,238 | 35,854 |
| 16 | 25,595 | 10,349 | 24,084 | 37,517 |
| 38 | 24,861 | 10,068 | 23,052 | 35,626 |

Waktu keempat perlakuan praktis **datar** sepanjang sweep. B3 menghitung ulang 1 sel pada titik
terkecil dan 38 sel pada titik terbesar, tetapi waktunya tidak bertambah; B1 menulis ulang 15.484
baris pada setiap titik dan waktunya juga tidak berubah. Penjelasannya terbaca langsung dari
pemisahan fase: pernyataan tulis B0, B1, dan B2 berkisar 9,5 sampai 11,3 detik berapa pun ukuran
revisinya, sedangkan `expire_snapshots` menghabiskan 13,3 sampai 14,6 detik pada B0 dan B2 serta
20,2 sampai 22,1 detik pada B3 yang memelihara dua tabel. B1 tercepat bukan karena menulis lebih
sedikit, melainkan karena mekanismenya yang dibekukan memang tidak menuntut pemeliharaan snapshot.

Dengan kata lain, pada panel 5.378 sel di node 2 vCPU, waktu ditentukan oleh **jumlah pernyataan dan
ongkos pemeliharaan Iceberg**, bukan oleh jumlah baris yang disentuh. Ini gejala yang sama seperti
H10B pada fixture 14 sel, dan pada panel yang 384 kali lebih besar gejalanya belum hilang.

### Pertambahan ruang

Pertambahan byte median tiga repetisi, dengan pemisahan data Parquet dan metadata Iceberg.

| Sel direvisi | B0 | B1 | B2 | B3 |
|---:|---:|---:|---:|---:|
| 1 | 13.279 | 468.313 | 25.883 | 49.262 |
| 2 | 13.362 | 468.398 | 25.971 | 50.608 |
| 4 | 13.410 | 468.491 | 26.004 | 50.789 |
| 8 | 13.619 | 468.714 | 26.107 | 50.818 |
| 16 | 13.884 | 468.987 | 26.250 | 51.959 |
| 38 | 14.459 | 469.682 | 26.363 | 52.873 |

Di sinilah perbedaan mekanisme terlihat. B1 menambah sekitar 468 KB pada setiap revisi, dengan 430
KB di antaranya berupa data, karena ia menuliskan satu salinan penuh keadaan 5.378 sel setiap kali.
B3 menambah 49 sampai 53 KB, yaitu **8,9 sampai 9,5 kali lebih sedikit daripada B1** pada seluruh
rentang, karena yang ditulis hanya `k` baris ke store ditambah berkas serving yang tersentuh. B0
paling murah dalam ruang (13,3 sampai 14,5 KB) tetapi membayarnya pada recall, dan B3 memerlukan
sekitar 3,7 kali ruang B0 untuk mempertahankan seluruh riwayat.

Dominasi metadata yang ditemukan H10B muncul kembali dan lebih tajam. Merevisi satu nilai pada B0
mengubah 279 byte data tetapi menambah 13.000 byte metadata, yaitu 47 kali lipat. Pada B2 angkanya
221 byte data terhadap 25.662 byte metadata. Hanya pada B1 data mendominasi metadata, dan itu justru
karena ia menulis ulang seluruh keadaan.

### Sel yang dievaluasi

Metrik m2 memisahkan pekerjaan logis dari ongkos fisik. B0 dan B3 mengevaluasi tepat sel yang
menjadi sasaran pernyataannya, yaitu 1 sampai 38 sel, sedangkan B1 dan B2 menghitung ulang seluruh
5.378 sel pada setiap titik. Pada titik terkecil B3 mengevaluasi 5.378 kali lebih sedikit sel
daripada B1, namun tetap 3,8 kali lebih lambat. Penghematan inkremental karena itu **nyata dalam
pekerjaan logis dan dalam ruang, tetapi habis diserap ongkos tetap pernyataan dalam waktu**.

### Titik impas

| Perbandingan | Ukuran | Titik impas | Arah pada seluruh rentang |
|---|---|---|---|
| B3 terhadap B1 | waktu | tidak ada | B1 lebih murah di seluruh rentang |
| B3 terhadap B1 | byte | tidak ada | B3 lebih murah di seluruh rentang |
| B3 terhadap B0 | waktu | tidak ada | B0 lebih murah di seluruh rentang |
| B3 terhadap B0 | byte | tidak ada | B0 lebih murah di seluruh rentang |
| B3 terhadap B2 | waktu | tidak ada | B2 lebih murah di seluruh rentang |
| B3 terhadap B2 | byte | tidak ada | B2 lebih murah di seluruh rentang |

Tidak ada satu pun titik silang di dalam rentang beku 1 sampai 38 sel, yaitu 2,63 persen sampai 100
persen semesta sweep. Urutan antarperlakuan stabil pada keenam titik, dan karena aturan kontrak
melarang interpolasi maupun ekstrapolasi, jawaban P3 pada beban ini dinyatakan apa adanya:
pendekatan inkremental **tidak pernah berhenti terbayar dalam ruang dan tidak pernah mulai terbayar
dalam waktu** pada rentang yang disapu. Jawaban ini negatif untuk waktu, dan itu tetap temuan yang
sah karena alasannya terukur, yaitu ongkos tetap pernyataan dan pemeliharaan snapshot yang
mengalahkan pekerjaan datanya.

### Recall dan propagasi

Recall dihitung atas seluruh 6.983 observasi panel ditambah observasi sintetis skenario, dan
dicocokkan pada `observation_id` beserta bentuk angka yang diterbitkan.

| Perlakuan | Titik 1 sel | Titik 38 sel | Jalur akses |
|---|---:|---:|---|
| B0 | 0,7700 | 0,7660 | `observation_id` pada tabel current |
| B1 | 1,0000 | 1,0000 | `observation_id` pada state yang dipertahankan |
| B2 | 0,7700 | 0,7660 | `observation_id` pada tabel current |
| B3 | 1,0000 | 1,0000 | `(cell_id, vintage_id)` pada store append-only |

B0 dan B2 hanya menyimpan satu baris per sel, sehingga 1.605 observasi historis panel memang tidak
dapat dipanggil; rasionya turun pelan seiring bertambahnya permintaan sintetis. B1 dan B3 memanggil
ulang seluruh permintaan dengan nilai yang sama persis pada ketiga repetisi. Snapshot B1 sebelum
revisi juga diuji dengan `VERSION AS OF` pada setiap siklus dan tetap memuat 10.106 baris tanpa state
revisi.

Tingkat propagasi revisi bernilai 1,0000 untuk keempat perlakuan pada seluruh titik. Ini konsekuensi
semesta sweep, bukan temuan tentang B2: ke-38 sel semesta hanya dilayani `bps_webapi`, sehingga B2
tidak punya kandidat lain untuk dipilih dan tidak pernah menahan revisi. Perilaku menahan yang
terlihat pada H9B dan H10B, yaitu 8 dari 28 revisi tersaji, tetap menjadi bukti untuk kebijakan
pemilihan sumber; sweep ini tidak membantahnya maupun mengulanginya.

### Ruang keadaan dasar

Footprint median keadaan dasar sebelum revisi: B0 373.370 byte, B1 889.876 byte, B2 316.590 byte, dan
B3 931.387 byte yang terbagi menjadi store 561.559 byte dan serving 369.826 byte. Urutannya sama
seperti fixture 14 sel pada H10A, termasuk B3 yang terbesar karena tabel serving yang dimaterialisasi,
sehingga kesimpulan H10A tidak berubah ketika keadaan dasarnya 384 kali lebih besar.

## Batas klaim

Waktu hanya boleh dibaca sebagai perbandingan antarperlakuan pada perangkat keras yang sama, yaitu VM
`praktikum-sd` dengan 2 vCPU yang dibekukan sebagai batas sumber daya seluruh eksperimen
(`h10c_resource_limit`). Angka ini bukan klaim performa, throughput, maupun skalabilitas. Panel
provinsi berukuran 5.378 sel tetap kecil, dan titik impas yang ditemukan atau tidak ditemukan hanya
berlaku untuk rentang ukuran yang benar-benar disapu, tanpa interpolasi maupun ekstrapolasi.

## Artefak audit

- kontrak: `contracts/h11-main-sweep.json`;
- DDL tabel sweep: `infra/spark/h11-sweep.sql`;
- SQL bersama, pemuat keadaan dasar, dan penggerak pengukuran: `scripts/h11_sql.sh`,
  `scripts/h11_baseline.sh`, `scripts/h11_measure.sh`;
- payload dan prediksi: `data/manifests/h11-main-sweep-payload.json`;
- keluaran mentah: `results/raw/h11/h11-20260913/`;
- hasil agregat: `results/processed/h11-*.csv` dan `data/manifests/h11-main-sweep.json`.
