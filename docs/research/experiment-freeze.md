# Freeze Konfigurasi Eksperimen (H10 Jalur C)

## Status

Berkas ini membekukan konfigurasi eksperimen sesuai daftar tujuh butir pada §4.4 README, ditambah
definisi metrik pada §4.2. Pembekuan dilakukan pada 12 September 2026, setelah pengukuran ruang H10
Jalur A dan eksekusi fisik H10 Jalur B selesai, dan sebelum sweep utama H11 dimulai. Dengan
tertulisnya berkas ini, kriteria keempat Gate G2 terpenuhi dan **Gate G2 dinyatakan lolos**.

Nilai yang dibekukan tersimpan dalam bentuk yang dapat dibaca mesin pada
[`config/experiments/experiment_freeze.csv`](../../config/experiments/experiment_freeze.csv)
(24 baris, `674bb1ca9e8550921f52824e566b78cef28b467e24ade1c5784db6b9d9f6620b`). Setiap baris memuat
butir §4.4 yang diacu, nilai yang dibekukan, berkas buktinya, serta checksum berkas tersebut pada
saat pembekuan. Dokumen ini menjelaskan alasan di balik setiap nilai; berkas CSV itulah yang
menjadi rujukan operasional.

## Mengapa freeze ditulis sekarang

Rencana kerja menempatkan freeze pada akhir H10, bukan lebih awal, karena dua butir di dalamnya
memerlukan hasil pengukuran yang sebelumnya belum ada. Butir besaran revisi tersuntik bergantung
pada apakah ongkos satu revisi pada fixture kecil masih dapat dibedakan dari ongkos tetap Spark dan
Iceberg, sedangkan butir batas sumber daya bergantung pada apakah node yang lebih besar tersedia.
H10 Jalur A dan Jalur B menjawab keduanya. Pengukuran waktu H10B menunjukkan bahwa revisi satu
nilai pada B0 hanya mengubah 161 byte data tetapi menambah 23.915 byte metadata, dan bahwa selisih
waktu antarperlakuan mencerminkan jumlah pernyataan SQL, bukan jumlah baris yang disentuh. Kondisi
tersebut menentukan bentuk sweep utama, sehingga freeze tidak dapat ditulis sebelum angka itu ada.

Sebaliknya, freeze juga tidak boleh ditunda sampai H11. Sweep utama adalah eksperimen yang hasilnya
dipakai menjawab P3, dan konfigurasi yang dipilih setelah melihat hasilnya kehilangan nilai sebagai
bukti. Karena itu seluruh parameter yang menentukan bentuk hasil ditetapkan di sini, termasuk yang
konsekuensinya belum diketahui.

## Keputusan manusia yang dipakai

Lima keputusan berikut disetujui peninjau pada 12 September 2026 dan tercatat di
[`config/h10c/human_decisions.csv`](../../config/h10c/human_decisions.csv).

| ID | Keputusan |
|---|---|
| `h10c_sweep_workload` | Workload hibrid: fixture 14 sel dipertahankan sebagai basis bukti, panel provinsi dibekukan sebagai basis sweep |
| `h10c_sweep_universe` | Semesta sweep adalah `sdg08_productivity_growth` 2025 pada seluruh 38 provinsi dengan sumber tunggal |
| `h10c_panel_deduplication` | 683 baris duplikat `(cell_id, source_id)` yang nilainya terbukti identik dibuang dari panel |
| `h10c_propagation_metric` | Tingkat propagasi revisi dibekukan sebagai metrik pendukung |
| `h10c_resource_limit` | VM 2 vCPU dibekukan sebagai batas sumber daya seluruh eksperimen, menggantikan spesifikasi proposal |

Keputusan terakhir memperluas `h10b_timing_environment` yang sebelumnya hanya mengikat pengukuran
waktu H10B dan H11. Seluruh pengukuran pada artikel ini kini dinyatakan berjalan pada perangkat
keras yang sama.

## Butir 1 — Snapshot dataset dan tanggal penarikan

Seluruh sumber berada pada jalur gratis dan tidak ada penarikan baru yang diizinkan setelah tanggal
ini. Snapshot WebAPI untuk inventarisasi H1 ditarik pada 2026-09-08 pukul 14:04:19 UTC dan memuat 29
variabel, 240 ID periode, serta 27.826 sel. Snapshot WebAPI kedua untuk perbandingan provinsi H3
ditarik pada hari yang sama pukul 23:38:59 UTC dan memuat 20 variabel. Kedua publikasi TPB diunduh
pukul 14:05:34 UTC, dengan tanggal rilis 2024-12-31 untuk edisi 2024 dan 2025-12-30 untuk edisi
2025.

Tiga vintage yang membentuk basis bukti karena itu adalah `bps_tpb_2024`, `bps_tpb_2025`, dan
`bps_webapi` bertanggal 2026-09-08. Ketiganya terdaftar di
[`results/processed/h6-release-vintages.csv`](../../results/processed/h6-release-vintages.csv)
beserta checksum manifest sumbernya.

Aturan §11 tetap berlaku setelah freeze. Penarikan ulang dari sumber yang sama disimpan sebagai
vintage baru dan tidak menimpa snapshot yang dibekukan di sini, tetapi vintage baru tersebut tidak
boleh masuk ke eksperimen utama tanpa membuat versi eksperimen baru.

## Butir 2 — Daftar indikator yang diuji per domain

Pembekuan dilakukan pada tiga tingkat, karena ketiganya menjawab pertanyaan yang berbeda.

Inventaris kandidat berisi 35 indikator pada lima domain, dengan 14 berstatus `verified`, 17
`partial`, dan 4 `unavailable`. Sebarannya per domain adalah education 4/7/1, economy 5/3/0, energy
3/1/0, environment 1/2/1, dan ecology 1/4/2. Inventaris ini menjadi ruang lingkup karakterisasi P1
dan tidak seluruhnya masuk ke eksperimen perlakuan.

Fixture bukti berisi 14 sel dan 38 observasi pada empat indikator, yaitu
`sdg08_productivity_growth` sebanyak 10 sel, `sdg08_gdp_per_capita_growth` 2 sel,
`sdg07_renewable_share` 1 sel, dan `sdg15_forest_cover` 1 sel. Keempat belas sel inilah yang
mempunyai jejak revisi nyata terkonfirmasi dari H5, sehingga hanya di sini pemanggilan ulang angka
lama dapat diuji terhadap revisi yang benar-benar terjadi. Fixture ini dibekukan apa adanya dan
tidak dibangun ulang.

Panel sweep berisi 6.983 observasi pada 5.378 sel, mencakup 16 indikator, lima domain, 38 provinsi
ditambah agregat nasional, serta periode 2015 sampai 2025. Panel diturunkan dari batch ingestion
H4 `h4-2981e0fb3bc2d960` dan dipakai sebagai keadaan dasar sweep P3.

## Butir 3 — Definisi ketidaksesuaian dan aturan klasifikasinya

Delapan aturan R01 sampai R08 pada
[`config/h4/classification_rules.csv`](../../config/h4/classification_rules.csv) dibekukan tanpa
perubahan. Aturan tersebut memetakan setiap kejadian ketidaksesuaian ke salah satu dari tiga
keluarga sebab, yaitu vintage, metodologi, dan granularitas, serta menandai tingkat buktinya
sebagai `observed`, `candidate`, atau `unresolved`. Aturan R01 mengeluarkan selisih pembulatan dari
hitungan Gate G1, dan R03 menampung selisih yang tidak dapat dijelaskan agar tidak diserap paksa ke
salah satu keluarga sebab.

Identitas sel dan vintage juga dibekukan karena keduanya menentukan apa yang dianggap satu
ketidaksesuaian. Nilai `cell_id` adalah SHA-256 atas `indicator_key`, `series_key`,
`observed_period`, `geo_level`, dan `geo_code` yang dipotong menjadi 20 heksadesimal, sedangkan
`vintage_id` adalah SHA-256 atas `source_id`, `release_date`, dan checksum manifest sumber dengan
pemotongan yang sama. Dua nilai dari sumber berbeda hanya dianggap sel yang sama bila seluruh
dimensi tersebut cocok.

## Butir 4 — Keempat perlakuan

Keempat perlakuan dibekukan beserta mekanisme tulisnya, karena H10B menunjukkan bahwa jumlah
pernyataan SQL yang dikeluarkan sebuah perlakuan menentukan waktunya pada fixture kecil.

| Perlakuan | Keadaan yang disimpan | Pernyataan tulis per revisi | Pemeliharaan |
|---|---|---|---|
| B0 | tepat satu baris terkini per `cell_id` | `MERGE` | `expire_snapshots` sisa 1 |
| B1 | satu snapshot keadaan penuh per rilis | `INSERT OVERWRITE` seluruh state | tidak ada |
| B2 | seleksi sumber tunggal menurut skor H6B | `INSERT OVERWRITE` seleksi yang dihitung ulang | `expire_snapshots` sisa 1 |
| B3 | store append-only berkunci `(cell_id, vintage_id)` dan tabel serving termaterialisasi | `INSERT` ke store lalu `MERGE` sel kotor ke serving | `expire_snapshots` sisa 1 pada kedua tabel |

Skor kepercayaan B2 memakai lima dimensi berbobot yang dibekukan pada H6B, dan nilai observasi
maupun hasil konflik dilarang masuk ke dalam skor. Sel kotor B3 diturunkan dari edge lineage H6C,
bukan dari pembandingan nilai. Varian B2 yang mempertimbangkan kebaruan rilis, dan varian B3 yang
tidak memateralisasi tabel serving, hanya boleh dijalankan sebagai versi eksperimen baru.

## Butir 5 — Metrik

Definisi operasional kedelapan metrik berada pada
[`config/experiments/metric_definitions.csv`](../../config/experiments/metric_definitions.csv).
Empat metrik utama adalah waktu penghitungan ulang, jumlah sel yang benar-benar dievaluasi, ruang
penyimpanan total, dan tingkat keberhasilan memanggil ulang angka terbit. Empat metrik pendukung
adalah kelengkapan lineage, jumlah byte yang dibaca, proporsi ketidaksesuaian yang dapat dijelaskan
otomatis, dan tingkat propagasi revisi.

Dua definisi perlu dinyatakan eksplisit karena mudah disalahartikan. Ruang penyimpanan dihitung dari
seluruh objek yang terjangkau dari metadata snapshot yang dipertahankan, dengan ukuran diambil dari
MinIO; objek di lokasi tabel yang tidak dirujuk metadata apa pun dilaporkan terpisah dan tidak
pernah ikut dihitung. Waktu penghitungan ulang mencakup pernyataan pemeliharaan yang dituntut
perlakuan, sehingga `expire_snapshots` pada B0, B2, dan B3 masuk hitungan, sedangkan B1 memang tidak
memerlukannya.

Tingkat propagasi revisi merupakan tambahan yang diusulkan pada 11 September 2026 setelah profil
validasi H9B, dan statusnya dicatat sebagai tambahan, bukan sebagai metrik yang ada sejak awal.
Definisinya adalah jumlah revisi yang terbaca di state serving sebuah perlakuan setelah satu run,
dibagi jumlah revisi yang masuk pada run tersebut. Pada profil validasi nilainya 1,000 untuk B0, B1,
dan B3, serta 8/28 atau 0,286 untuk B2. Metrik ini dibekukan sebagai metrik pendukung dan tidak
dinaikkan menjadi metrik utama, karena ia mengukur konsekuensi kebijakan pemilihan sumber, bukan
ongkos yang menjadi pokok pertanyaan penelitian.

## Butir 6 — Besaran revisi tersuntik

### Aturan injeksi

Aturan yang disetujui pada 10 September 2026 dibekukan tanpa perubahan. Nilai awal setiap injeksi
adalah vintage terbaru pada sel yang dipilih. Nilai target diubah tepat satu unit pada presisi yang
diterbitkan, dan arah perubahan dibalik menjadi minus satu unit bila nilai persentase akan melewati
100. Dimensi pembentuk sel tidak pernah diubah, dan setiap baris injeksi menyimpan nilai sebelum,
delta, nilai sesudah, observasi dasar, vintage dasar, serta sumber yang disimulasikan direvisi.
Sweep utama wajib merevisi tepat satu `revised_source_id` per run.

Perlu ditegaskan bahwa perubahan satu unit adalah mekanisme pemicu dependensi, bukan model
distribusi revisi BPS yang sebenarnya. Besaran perubahan nilai karena itu tidak boleh ditafsirkan
sebagai besaran revisi yang realistis; yang dikontrol pada eksperimen ini adalah **jumlah sel** yang
direvisi, bukan besar perubahan nilainya.

### Profil validasi

Profil `1-2-4-7-14` dengan seed `20260909` pada fixture 14 sel dipertahankan sebagai profil
validasi, bukan sebagai titik sweep. Profil ini sudah dijalankan secara logis pada H9B untuk kelima
ukuran, dan secara fisik pada H10B untuk ukuran 1 dan 2. Empat dari lima skenarionya memakai lebih
dari satu sumber, sehingga tidak memenuhi aturan satu sumber per run dan tidak boleh dipakai sebagai
titik sweep utama.

### Semesta sweep utama

Fixture 14 sel tidak dapat memikul sweep P3. H10B memperlihatkan bahwa pada keadaan sebesar itu
ongkos tetap satu pernyataan Spark lebih besar daripada pekerjaan datanya, sehingga urutan waktu
antarperlakuan ditentukan oleh jumlah pernyataan dan titik impas inkremental tidak mungkin teramati.
Bukti paling jelas adalah B1, yang menulis ulang seluruh state dan justru menjadi yang tercepat pada
revisi satu sel, serta menambah 68.447 byte baik untuk satu maupun dua sel.

Karena itu sweep utama dijalankan di atas keadaan dasar yang lebih besar. Panel provinsi dibekukan
berisi 6.983 observasi pada 5.378 sel, sehingga keadaan dasar B0 berukuran 5.378 baris, sekitar 384
kali keadaan dasar fixture. Pada ukuran tersebut ongkos penulisan ulang penuh B1 tumbuh mengikuti
ukuran keadaan, sedangkan ongkos B3 tumbuh mengikuti jumlah sel yang direvisi, dan perbedaan itulah
yang menentukan ada tidaknya titik impas.

Panel diturunkan dari batch H4 dengan satu penyesuaian yang perlu dicatat. Dari 7.666 baris, 683
baris mengulang pasangan `(cell_id, source_id)` yang sama karena dua variabel WebAPI membawa
indikator yang sama. Seluruh 683 kelompok duplikat diperiksa dan setiap kelompok hanya memuat satu
nilai yang identik, sehingga pembuangan duplikat tidak menghilangkan informasi. Penyesuaian ini
diperlukan karena B3 mensyaratkan kunci `(cell_id, vintage_id)` yang unik, dan duplikat tersebut
akan melanggarnya.

Semesta seleksi sweep adalah satu irisan indikator-tahun pada seluruh provinsi, yaitu
`sdg08_productivity_growth` seri `total` satuan persen untuk periode 2025 pada 38 provinsi, seluruhnya
bersumber dari `bps_webapi`. Pilihan ini memenuhi dua syarat sekaligus. Titik terbesarnya secara
harfiah merupakan satu tahun penuh untuk seluruh provinsi sebagaimana dijanjikan §4.3, dan karena
seluruh selnya dilayani satu sumber, aturan satu sumber per run terpenuhi pada setiap titik tanpa
pengecualian. Indikator yang dipilih juga merupakan indikator yang sama dengan sepuluh dari empat
belas sel fixture bukti, sehingga hasil sweep dan hasil revisi nyata membahas indikator yang sama.

### Titik sweep

| Skenario | Sel direvisi | Proporsi semesta | Sumber yang direvisi |
|---|---:|---:|---|
| `sweep_001` | 1 | 2,63% | `bps_webapi` |
| `sweep_002` | 2 | 5,26% | `bps_webapi` |
| `sweep_004` | 4 | 10,53% | `bps_webapi` |
| `sweep_008` | 8 | 21,05% | `bps_webapi` |
| `sweep_016` | 16 | 42,11% | `bps_webapi` |
| `sweep_038` | 38 | 100,00% | `bps_webapi` |

Seed sweep utama adalah `20260912` dan ditulis eksplisit di konfigurasi. Seluruh 38 sel diperingkat
satu kali memakai SHA-256 atas seed dan `cell_id`, lalu skenario berukuran `k` mengambil `k`
peringkat pertama. Dengan demikian setiap skenario merupakan subset skenario yang lebih besar, dan
tidak ada random state yang berasal dari waktu eksekusi. Peringkat beserta identitas ke-38 sel
tersimpan di
[`config/experiments/main_sweep_universe.csv`](../../config/experiments/main_sweep_universe.csv).

## Butir 7 — Batas sumber daya

Seluruh pengukuran pada artikel ini dijalankan pada satu node, yaitu VM `praktikum-sd` dengan 2
vCPU, RAM 8.318.799.872 byte, disk 19.594.608.640 byte, dan Spark driver 2g. Spesifikasi proposal
sebesar 8 vCPU dan 16 GB tidak tersedia, dan penggantinya dinyatakan di muka sebagai revisi desain
eksperimen, bukan sebagai penyesuaian setelah melihat hasil.

Konsekuensinya dinyatakan tanpa ditutupi. Waktu hanya boleh dibaca sebagai perbandingan
antarperlakuan pada perangkat keras yang sama dan tidak pernah sebagai klaim performa, throughput,
atau skalabilitas. Run tidak boleh dijalankan bersamaan dan dipegang satu operator, karena dua run
serentak pada 2 vCPU akan saling memengaruhi CPU, memori, dan I/O.

Versi stack dibekukan pada MinIO `RELEASE.2024-06-13T22-53-53Z`, Iceberg REST 1.8.1, dan Spark
`3.5.5_1.8.1`, dengan digest image tercatat pada setiap berkas lingkungan run. Katalog Iceberg wajib
berada pada SQLite persisten di `jdbc:sqlite:/home/iceberg/iceberg_catalog.db`. Syarat terakhir ini
bukan detail operasional: H10A menunjukkan katalog in-memory menghapus kemampuan B1 memanggil angka
lama tanpa meninggalkan tanda apa pun pada data. Setiap titik pengukuran dijalankan dalam tiga
repetisi purge-rebuild-ukur dan dilaporkan sebagai median.

Ruang disk bebas pada node tercatat sekitar 3,5 GB sebelum run H10B. Panel sweep berukuran sekitar
384 kali fixture, dan footprint fixture untuk keempat perlakuan berjumlah sekitar 591 KB, sehingga
kebutuhan ruang sweep diperkirakan masih berada jauh di bawah batas tersebut. Perkiraan ini
merupakan ekstrapolasi linier dan wajib diperiksa ulang pada repetisi pertama H11.

## Pemeriksaan Gate G2

| Kriteria | Status | Bukti |
|---|---|---|
| Keempat perlakuan berjalan pada beban revisi yang identik | lolos | H9B mengeksekusi 20 route logis dengan checksum payload identik antarperlakuan; H10B mengeksekusi 8 route fisik pada dua skenario dalam tiga repetisi, dan seluruh hasil fisiknya sama persis dengan audit logis |
| Angka lama dapat dipanggil ulang pada B1 | lolos | H10A memanggil ulang 38/38 observasi setelah katalog di-restart; H10B memanggil ulang 39/39 dan 40/40 setelah revisi disuntikkan |
| Seluruh harness dapat diulang dari script tanpa langkah manual | lolos | `make h8b-run`, `h9b-run`, `h10b-prepare`, `h10b-cleanup`, `h10b-measure`, dan `h10b-run`; marker serta checksum keluaran identik pada satu run lokal dan dua run VM |
| Berkas freeze sudah ditulis | lolos | dokumen ini beserta `config/experiments/` dan `config/h10c/human_decisions.csv` |

Keempat kriteria terpenuhi, sehingga **Gate G2 lolos** dan penurunan cakupan yang disiapkan untuk
kegagalan B3 tidak diperlukan. B3 berjalan pada beban yang sama dengan ketiga pembanding, baik
secara logis maupun fisik.

## Yang tidak dibekukan

Tiga hal sengaja dibiarkan terbuka karena bukan parameter eksperimen.

Pertama, jumlah repetisi tambahan bila sebuah titik sweep menghasilkan angka yang meragukan. H13
memang dialokasikan untuk menjalankan ulang run yang gagal, dan alasan setiap pengulangan dicatat
pada decision log sesuai §12.

Kedua, bentuk tabel dan gambar naskah. Keduanya diturunkan dari hasil dan tidak memengaruhi apa yang
diukur.

Ketiga, penambahan sumber baru pada workload karakterisasi P1. Status `hold` pada SIRuSa, DNA, dan
batas wilayah tidak berubah, tetapi bila salah satunya dibuka, hasilnya masuk sebagai karakterisasi
tambahan dan tidak boleh mengubah keadaan dasar perlakuan yang dibekukan di sini.

## Aturan perubahan setelah freeze

Konfigurasi pada berkas ini tidak boleh diubah setelah hasil dilihat. Bila sebuah parameter ternyata
perlu diubah, yang dibuat adalah versi eksperimen baru dengan identitas sendiri, dan hasil versi
lama tetap dilaporkan. Penyimpangan yang ditemukan setelah run berjalan dicatat sebagai penyimpangan
beserta alasannya, bukan diperbaiki secara diam-diam dengan menyunting berkas freeze.

Satu pengecualian berlaku untuk kesalahan yang terbukti sebagai bug, misalnya script sweep yang
salah membaca konfigurasi. Perbaikan semacam itu tidak mengubah nilai yang dibekukan, dan run yang
terpengaruh dijalankan ulang dengan alasan yang dicatat.

## Reproduksi

Berkas freeze tidak dibentuk oleh pipeline karena isinya adalah keputusan, bukan hasil hitung.
Verifikasi dilakukan dengan mencocokkan checksum setiap berkas bukti terhadap kolom
`evidence_sha256`:

```bash
python3 - <<'PY'
import csv, hashlib, pathlib
for row in csv.DictReader(open("config/experiments/experiment_freeze.csv")):
    path = pathlib.Path(row["evidence_path"])
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    status = "ok" if actual == row["evidence_sha256"] else "CHANGED"
    print(f"{status:8} {row['freeze_id']:5} {row['evidence_path']}")
PY
```

Semesta sweep dapat dibentuk ulang dari panel H4 memakai seed `20260912` dan aturan peringkat yang
sama dengan H8B, yaitu SHA-256 atas seed dan `cell_id` dengan pemisah `\x1f`.

## Artefak audit

- tabel freeze: `config/experiments/experiment_freeze.csv`;
- definisi metrik: `config/experiments/metric_definitions.csv`;
- titik sweep utama: `config/experiments/main_sweep_scenarios.csv`;
- semesta sweep 38 sel: `config/experiments/main_sweep_universe.csv`;
- keputusan manusia: `config/h10c/human_decisions.csv`;
- keputusan manusia sebelumnya yang tetap mengikat: `config/h8b/human_decisions.csv`,
  `config/h9/human_decisions.csv`, `config/h10/human_decisions.csv`;
- aturan klasifikasi: `config/h4/classification_rules.csv`;
- lingkungan pengukuran: `results/raw/h10/h10a-20260911/environment.txt` dan
  `results/raw/h10b/h10b-20260912/environment.txt`.
