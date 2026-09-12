# Vintage-Aware Reconciliation of Official SDG Indicators

KK-CIV Research Program — Data Systems and Intelligent Computing (DSIC)

Peneliti: Ardika Satria, dkk. Testbed: indikator SDG 4, 6, 7, 8, dan 15 ber-provenans BPS.

---

## 1. Posisi Penelitian

Repository ini menampung pekerjaan untuk satu artikel yang dikerjakan bersama oleh enam peneliti. Tidak ada track mahasiswa dan tidak ada klaim pada tingkat platform. Pembagian kerja disusun sebagai jalur paralel yang bermuara pada satu naskah, bukan sebagai sub-penelitian yang berdiri sendiri-sendiri.

Proposal KK-CIV berfungsi sebagai payung yang menyediakan domain, sumber data, infrastruktur, serta konteks 5E. Artikel ini mengambil satu irisan sempit dari payung tersebut, lalu menggarapnya sampai dapat dipertanggungjawabkan secara empiris.

### 1.1 Persoalan yang diteliti

Indikator SDG Indonesia dapat diperoleh dari beberapa jalur resmi BPS, yaitu WebAPI, metadata SIRuSa/DNA, dan kompilasi indikator SDGs. Ketiganya dapat memberikan nilai berbeda untuk indikator, wilayah, dan tahun yang sama.

Perbedaan tersebut bukan kesalahan, melainkan konsekuensi dari cara statistik resmi diproduksi. Setidaknya ada tiga sebab yang perlu dibedakan.

1. **Vintage (versi rilis data).** Angka yang sama dirilis ulang dengan nilai berbeda setelah data sumber yang lebih lengkap masuk.
2. **Metodologi.** Definisi atau cara hitung indikator berubah antar periode.
3. **Granularitas.** Agregat nasional tidak selalu sama dengan penjumlahan angka provinsi.

Pada praktiknya, nilai lama biasanya ditimpa oleh nilai terbaru. Angka yang pernah dipublikasikan karena itu tidak lagi dapat dihasilkan ulang, padahal pedoman revisi statistik resmi justru menuntut kemampuan tersebut.

### 1.2 Pertanyaan yang menggerakkan penelitian

Bagaimana caranya menyimpan dan menghitung indikator SDG sehingga setiap angka yang pernah terbit tetap dapat dipanggil ulang, dan berapa ongkosnya.

---

## 2. Pertanyaan Penelitian

**Pertanyaan utama**

> Ketika beberapa sumber resmi BPS memberikan nilai berbeda untuk indikator SDG yang sama, berapa ongkos mempertahankan indikator yang tetap dapat direproduksi dan ditelusuri, dan pada besaran revisi seperti apa penghitungan ulang inkremental berhenti lebih murah daripada penghitungan ulang penuh?

**Sub-pertanyaan**

**P1 — Karakterisasi ketidaksesuaian**  
Bentuk ketidaksesuaian apa yang benar-benar muncul antarsumber resmi BPS pada lima domain 5E, dan berapa proporsi yang berasal dari revisi vintage dibanding perbedaan metodologi dan perbedaan granularitas?

**P2 — Representasi**  
Dapatkah ketidaksesuaian tersebut direpresentasikan sebagai vintage indikator di atas format tabel terbuka, sehingga nilai yang pernah dipublikasikan tetap dapat dipanggil ulang tanpa menyimpan salinan penuh setiap rilis?

**P3 — Ongkos pemeliharaan**  
Berapa waktu dan ruang yang dibutuhkan untuk menghitung ulang indikator ketika satu sumber direvisi, dan pada besaran revisi seperti apa pendekatan inkremental berhenti terbayar?

**P4 — Reproducibility**  
Apakah angka yang pernah dilaporkan dapat dihasilkan ulang persis setelah sumbernya direvisi, dan pada kondisi apa ia gagal?

P4 berfungsi sebagai syarat kelayakan, sehingga hasil yang lebih murah tetapi gagal menghasilkan ulang angka lama tidak dihitung sebagai keuntungan. Sebaliknya, jawaban "ternyata tidak lebih murah" tetap merupakan temuan yang sah sepanjang eksperimennya dikerjakan dengan benar.

---

## 3. Kedudukan terhadap Literatur

Rincian dan status verifikasi setiap sumber ada di [`docs/research/related-work.md`](docs/research/related-work.md).

Penelitian ini berdiri di antara dua literatur yang sama-sama sudah matang, tetapi belum pernah dipertemukan.

Dari sisi statistik resmi, konsep *vintage* dan *revision triangle* sudah lama mapan dan dituangkan dalam pedoman seperti OECD/Eurostat Guidelines on Revisions Policy and Analysis, serta dalam produk semacam real-time data tables Statistics Canada. Literatur tersebut bekerja pada agregat yang sudah terbit, bukan pada pipeline yang memproduksinya, sehingga ongkos komputasi untuk mempertahankan riwayat angka tidak pernah masuk hitungan.

Dari sisi sistem data, truth discovery dan data fusion sudah matang sejak Dong dkk. Bidang tersebut mengasumsikan ada satu nilai benar yang tersembunyi di balik sumber-sumber yang tidak seluruhnya dapat dipercaya. Asumsi itu keliru untuk statistik resmi karena tidak ada sumber BPS yang salah, sehingga menerapkan truth discovery di sini justru membuang informasi yang bermakna.

Pesaing terdekat adalah SDG-KG (Benjira dkk., PVLDB 18(12):5367–5370, 2025), yang menghitung indikator SDG dari data terbuka heterogen memakai knowledge graph dan penyelarasan skema berbantuan LLM, dengan strategi *Trust Your Friend* untuk memilih satu sumber ketika terjadi konflik. Artikel tersebut berbentuk demonstrasi empat halaman dan menyatakan sendiri bahwa ia bekerja pada tingkat metadata serta tidak memproses aliran data. Di dalamnya tidak terdapat evaluasi performa maupun pembahasan penyimpanan fisik.

Penelitian ini berbeda pada tiga hal. Pertama, pekerjaannya berada pada lapisan fisik, bukan pada metadata, sehingga yang diukur adalah waktu, ruang, dan kemampuan menghasilkan ulang angka. Kedua, perbedaan antarsumber diperlakukan sebagai vintage yang harus dipertahankan, bukan sebagai konflik yang harus dipilih salah satunya. Ketiga, pengujian dilakukan pada statistik resmi nasional Indonesia dengan revisi yang benar-benar terjadi, bukan pada data terbuka Eropa.

Batas klaimnya perlu dinyatakan sejak awal. Kebaruan tidak boleh diklaim pada algoritma truth discovery maupun pada incremental view maintenance karena keduanya hanya dipakai sebagai mekanisme dan pembanding. Yang diklaim penelitian ini adalah perlakuan vintage indikator sebagai objek kelas satu di dalam lakehouse, beserta pengukuran ongkos mempertahankannya.

---

## 4. Rancangan Eksperimen

### 4.1 Perlakuan yang dibandingkan

**B0 — Overwrite.** Hanya nilai terbaru yang disimpan. Ini praktik yang lazim dan menjadi titik nol.

**B1 — Snapshot penuh.** Setiap rilis disimpan sebagai salinan tabel utuh melalui snapshot Iceberg. Reproducibility terjamin, ongkos ruang menjadi batas atas.

**B2 — Pemilihan sumber tunggal.** Satu sumber dipilih berdasarkan skor kepercayaan, mengikuti pola *Trust Your Friend*. Ini wakil pendekatan truth discovery dan pembanding langsung terhadap SDG-KG.

**B3 — Vintage-aware (usulan).** Vintage indikator disimpan sebagai dimensi eksplisit, penghitungan ulang dilakukan inkremental berdasarkan lineage sel indikator yang benar-benar terpengaruh.

### 4.2 Metrik

Metrik utama:

- waktu penghitungan ulang setelah satu revisi;
- jumlah sel indikator yang benar-benar berubah per revisi;
- ruang penyimpanan total;
- tingkat keberhasilan menghasilkan ulang angka yang pernah terbit.

Metrik pendukung:

- kelengkapan lineage dari angka terbit sampai ke rekaman sumber;
- jumlah byte yang dibaca saat penghitungan ulang;
- proporsi ketidaksesuaian yang dapat dijelaskan otomatis sebagai vintage, metodologi, atau granularitas;
- tingkat propagasi revisi, yaitu revisi yang tampil di state serving dibagi revisi yang masuk. Metrik
  ini diusulkan pada 11 September 2026 setelah profil validasi H9B, dan pada 12 September 2026
  dibekukan sebagai metrik pendukung pada freeze H10, sebelum eksperimen utama.

Definisi operasional kedelapan metrik ada di
[`config/experiments/metric_definitions.csv`](config/experiments/metric_definitions.csv).

### 4.3 Beban kerja revisi

Revisi yang diuji berasal dari dua sumber, dan keduanya diperlukan untuk alasan yang berbeda.

Revisi nyata diambil dari perbedaan antarsumber dan antarrilis BPS yang benar-benar terjadi pada rentang yang ditarik. Inilah yang menjadi bukti utama untuk P1.

Revisi tersuntik diperlukan karena besaran revisi nyata tidak dapat dikendalikan. Revisi sintetis dengan besaran terkontrol, mulai dari satu sel sampai satu tahun penuh untuk seluruh provinsi, disuntikkan agar titik impas pada P3 dapat dicari secara sistematis. Prosedur penyuntikannya dicatat dan dapat dijalankan ulang.

Keduanya berjalan pada dua workload yang berbeda, dan pembagiannya dibekukan pada H10 Jalur C. Revisi
nyata diuji pada fixture 14 sel yang mempunyai jejak revisi terkonfirmasi dari H5. Revisi tersuntik
untuk sweep P3 dijalankan di atas panel provinsi berisi 5.378 sel, karena pada fixture 14 sel ongkos
tetap satu pernyataan Spark lebih besar daripada pekerjaan datanya sehingga titik impas tidak mungkin
teramati.

### 4.4 Yang dibekukan sebelum eksperimen utama

1. snapshot dataset dan tanggal penarikan;
2. daftar indikator yang diuji per domain;
3. definisi ketidaksesuaian dan aturan klasifikasinya;
4. keempat perlakuan;
5. metrik utama;
6. besaran revisi tersuntik;
7. batas sumber daya.

Konfigurasi tidak boleh diubah setelah melihat hasil tanpa membuat versi eksperimen baru.

Ketujuh butir tersebut dibekukan pada 12 September 2026 dan tercatat di
[`docs/research/experiment-freeze.md`](docs/research/experiment-freeze.md), dengan nilai yang dapat
dibaca mesin pada [`config/experiments/experiment_freeze.csv`](config/experiments/experiment_freeze.csv).

---

## 5. Data

### 5.1 Sumber

Seluruh sumber aktif berada pada jalur gratis. H1 memakai WebAPI BPS dan dua publikasi TPB yang
diunduh melalui katalog publikasi WebAPI. SIRuSa dan DNA berstatus `hold`. Silastik/PST, data mikro,
publikasi elektronik berbayar, dan peta digital berbayar tidak digunakan.

- WebAPI BPS - katalog variabel dan nilai tabel dinamis;
- *Indikator Tujuan Pembangunan Berkelanjutan Indonesia 2024* - rilis beku yang paling lengkap
  untuk pemetaan indikator H1;
- edisi 2025 - rilis terbaru dan kandidat pembanding versi rilis;
- batas wilayah BPS/BIG - `hold` sampai rilis referensi gratis yang tepat dikonfirmasi.

H1 menemukan 29 variabel WebAPI gratis dengan 240 ID periode sejak 2015 dan 27.826 sel data.
Dari 35 kandidat indikator, 14 berstatus `verified`, 17 `partial`, dan 4 `unavailable`. Rincian
keputusan serta alasan penolakan proksi tersedia di
[`docs/research/h1-data-audit.md`](docs/research/h1-data-audit.md).

### 5.2 Catatan tentang volume

Volume data pada penelitian ini tergolong kecil, dan hal tersebut tidak menjadi masalah. Pertanyaan yang diajukan menyangkut kebenaran, keterlacakan, dan ongkos pemeliharaan, bukan throughput. Rancangan sengaja disusun agar tidak bergantung pada volume besar, karena indikator SDG pada granularitas nasional sampai provinsi memang tidak akan pernah besar. Karena itu, klaim penelitian tidak boleh diperluas menjadi klaim tentang skalabilitas.

Eksperimen utama dirancang untuk satu node dengan 8 vCPU, 16 GB RAM, dan penyimpanan 256 GB,
sesuai spesifikasi pada proposal. Fondasi H3 telah diuji pada VM `praktikum-sd` yang tersedia,
dengan 2 vCPU, RAM 7,7 GiB, dan disk 19 GiB. VM tersebut dipakai untuk validasi layanan, bukan
sebagai bukti performa. Sebelum pengukuran, VM harus dinaikkan ke spesifikasi proposal atau batas
sumber daya yang lebih kecil harus dinyatakan dan dibekukan sebagai revisi desain eksperimen.
Pada 11 September 2026, VM 2 vCPU tersebut dinyatakan dan dibekukan **hanya untuk pengukuran byte**
(`h10_storage_environment` di [`config/h10/human_decisions.csv`](config/h10/human_decisions.csv)).
Pada 12 September 2026, VM yang sama juga dibekukan sebagai lingkungan pengukuran waktu H10B dan H11
(`h10b_timing_environment`), karena tidak ada node yang lebih besar. Konsekuensinya dinyatakan di
muka: waktu hanya boleh dibaca sebagai perbandingan antarperlakuan pada perangkat keras yang sama,
tidak pernah sebagai klaim performa atau skalabilitas. Pada 12 September 2026, VM yang sama
dibekukan sebagai batas sumber daya seluruh eksperimen (`h10c_resource_limit`), menggantikan
spesifikasi proposal 8 vCPU dan 16 GB.

### 5.3 Aturan provenance

Nilai indikator harus mempertahankan provenans BPS. Geometri diperlakukan sebagai data referensi dan tidak boleh dicampur dengan provenans indikator.

Setiap hasil harus dapat dilacak melalui rantai:

`source manifest -> vintage -> transformation version -> indicator cell -> metric -> tabel/gambar`

---

## 6. Rencana Kerja Tiga Minggu untuk Enam Peneliti

Rencana ini disusun untuk 15 hari kerja, dengan akhir pekan dikosongkan sebagai penyangga. Setiap minggu ditutup satu gate yang memuat kriteria lolos beserta tindakan yang diambil bila kriteria itu tidak terpenuhi.

### 6.1 Mengapa enam orang tidak berarti enam kali lebih cepat

Pekerjaan ini memiliki jalur kritis yang berurutan. Skema tabel tidak dapat dirancang sebelum aturan klasifikasi ketidaksesuaian selesai, sedangkan B3 memerlukan skema dan lineage yang sudah jadi. Menambah orang tidak memendekkan rantai tersebut.

Ada pula satu batas yang lebih keras. Eksperimen dijalankan pada satu node, sehingga **pengukuran waktu tidak boleh dijalankan bersamaan**. Dua run yang berjalan serentak akan saling memengaruhi CPU, memori, dan I/O, dan angkanya menjadi tidak dapat dipakai. Berapa pun jumlah peneliti, eksekusi eksperimen pada Minggu 3 tetap berurutan dan dipegang satu operator.

Karena itu tambahan tenaga tidak dipakai untuk mempercepat jalur kritis, melainkan untuk memperdalam pekerjaan di sekitarnya: kelima domain digarap serentak alih-alih bergiliran, fondasi dibangun beriringan dengan validasi, dan penulisan berjalan sejak minggu pertama. Hasil bersihnya adalah pemadatan dari 20 hari menjadi 15 hari, dengan cakupan yang lebih dalam pada tiap domain.

### 6.2 Pembagian jalur

Minggu pertama dikerjakan keenam peneliti pada satu jenis pekerjaan yang sama, karena karakterisasi lima domain memang terbelah rapi. Mulai Minggu 2, tim terbagi menjadi tiga jalur tetap.

| Jalur | Orang | Tanggung jawab |
|---|---|---|
| A — Fondasi | 2 | Stack, ingestion ber-manifest, skema vintage, perlakuan B0 dan B1 |
| B — Perlakuan | 2 | Perlakuan B2, harness revisi tersuntik, eksekusi eksperimen |
| C — Bukti | 2 | Lineage sel indikator, audit reproducibility, verifikasi literatur, naskah |

Perlakuan B3 sebagai usulan utama dikerjakan bersama oleh Jalur A dan Jalur C, karena ia memerlukan skema dari A dan lineage dari C. Keputusan pada setiap gate dipegang ketua pengusul.

### 6.3 Minggu 1 — Membuktikan persoalannya memang ada

Seluruh artikel bergantung pada asumsi bahwa sumber-sumber BPS benar-benar berbeda. Minggu ini menguji asumsi tersebut, dengan lima peneliti memegang satu domain masing-masing.

| Hari | Lima peneliti domain | Satu peneliti fondasi |
|---|---|---|
| H1 | Inventarisasi cakupan tiap jalur BPS pada domain masing-masing | Menyiapkan harness perbandingan bersama |
| H2 | Menarik indikator dari minimal dua jalur, lalu membandingkan sel per sel | Harness selesai dan dipakai bersama |
| H3 | Perbandingan penuh pada rentang nasional dan provinsi | Menaikkan stack Docker Compose |
| H4 | Menyusun dan menguji aturan klasifikasi bersama pada kelima domain | Ingestion ber-manifest |
| H5 | Menelusuri jejak revisi antarwaktu, lalu mengonsolidasikan hasil kelima domain | Uji tulis-baca tabel Iceberg |

Perlengkapan H1 tersedia di [`config/indicators/`](config/indicators/), registry kanal di
[`config/sources/bps_sources.csv`](config/sources/bps_sources.csv), dan harness pada
[`scripts/h1.py`](scripts/h1.py). Alurnya berurutan:

1. `make h1-discover-webapi` menarik katalog variabel domain pusat dan mengusulkan kandidat `var_id`;
2. kandidat disaring manual menjadi [`config/sources/free_webapi_selection.csv`](config/sources/free_webapi_selection.csv);
3. `make h1-fetch-free-webapi` menarik deret terpilih sejak 2015 dan mencatat manifest ber-checksum;
4. `make h1-fetch-free-publications` menarik PDF TPB 2024 dan 2025 dari katalog resmi;
5. locator publikasi disimpan di [`config/sources/free_publication_selection.csv`](config/sources/free_publication_selection.csv);
6. `make h1-profile-coverage` mengukur cakupan nyata tiap variabel, yaitu tingkat geografi, rentang
   tahun, tahun bolong, kepadatan sel, dan `last_update`;
7. `make h1-apply-coverage` menuliskan keputusan status beserta locator ke inventaris, lalu memvalidasinya.

`make h1-validate`, `make h1-summary`, dan `make h1-example` dapat dijalankan kapan saja. Aturan
penurunan status ditetapkan di muka dan bukan hasil penafsiran setelah melihat data.

Status per 2026-09-08: H1 Hari 1 selesai dengan 14 baris `verified`, 17 `partial`, 4
`unavailable`, dan tidak ada `proposal_only`. Status ini membuktikan cakupan dan locator sumber;
perbandingan nilai antarrilis dimulai pada H2 dan menjadi syarat Gate G1. Temuan pemeriksaan
proposal, aturan status, manifest, dan batas penggunaan sumber dicatat di
[`docs/research/h1-data-audit.md`](docs/research/h1-data-audit.md).

H2 juga sudah selesai sebagai pilot satu indikator per domain. Empat indikator dapat dibandingkan
langsung antara snapshot WebAPI dan publikasi TPB 2024; tutupan hutan ditolak karena perbedaan
definisi dan satuan. Dari 19 sel yang beririsan, 16 sama dan 3 berbeda. Ketiga perbedaan berasal
dari bauran energi terbarukan tahun 2018-2020, sedangkan nilai publikasi 2023 tidak tersedia pada
variabel WebAPI terpilih. Jalankan `make h2-run` untuk membentuk ulang hasil. Laporan lengkap ada
di [`docs/research/h2-source-comparison.md`](docs/research/h2-source-comparison.md).

H3 sudah selesai untuk audit nasional-provinsi dan tambahan antarrilis. Audit utama membandingkan
1.435 sel dari WebAPI dan lampiran TPB 2024: 1.402 sama dan 33 berbeda, dengan 82 pemeriksaan
agregat nasional terhadap provinsi. Tambahan TPB 2025 membentuk 4.608 kunci sel dan menemukan
delapan perbedaan nilai pada tiga domain, yaitu energi, ekonomi, dan ekologi. Dengan demikian,
kriteria pertama Gate G1 terpenuhi. Klasifikasi delapan sel tersebut masih berupa kandidat dan
harus diuji pada H4; jejak empat perubahan langsung antara publikasi 2024 dan 2025 dibekukan pada
H5. Laporan serta perintah reproduksinya ada di
[`docs/research/h3-national-province-comparison.md`](docs/research/h3-national-province-comparison.md).

Fondasi H3 juga aktif pada VM `praktikum-sd`, yang sejak 11 September 2026 beralamat
`sigerciv@34.101.84.199` (sebelumnya `34.128.67.92`): MinIO, Iceberg REST, dan Spark/Jupyter
telah lolos pemeriksaan kesehatan dan Spark berhasil mengakses katalog `kkciv`. Versi serta digest
image dibekukan di [`infra/docker/`](infra/docker/). Jalankan `make stack-remote-status` untuk
memeriksa layanan dan `make stack-remote-up` untuk menyinkronkan konfigurasi lalu menaikkannya.
Sejak 11 September 2026, katalog Iceberg REST disimpan pada berkas SQLite di volume `iceberg-catalog`.
Sebelumnya image fixture memakai SQLite in-memory, sehingga reboot VM menghapus seluruh registrasi
tabel (lihat H10 Jalur A).

H4 menerapkan delapan aturan klasifikasi yang sama pada kelima domain dan membentuk batch ingestion
ber-manifest berisi 7.666 observasi. Dari 123 kejadian, 104 atau 84,55 persen masuk keluarga
vintage, metodologi, atau granularitas bila bukti kandidat ikut dihitung. Bukti terkonfirmasi baru
85 kejadian atau 69,11 persen, sedikit di bawah ambang 70 persen. Gate G1 karena itu tetap
`pending_H5`; H5 perlu mengonfirmasi minimal dua kandidat dan membekukan jejak revisinya. Hasil,
aturan, serta batas interpretasinya tersedia di
[`docs/research/h4-classification-and-ingestion.md`](docs/research/h4-classification-and-ingestion.md).

H5 sudah selesai dan **Gate G1 dinyatakan lolos**. Sepuluh kandidat revisi tahun 2022-2023
dikonfirmasi melalui urutan TPB 2024, TPB 2025, dan snapshot WebAPI 2026; satu kandidat tutupan
hutan dikonfirmasi sebagai perubahan metodologi. Bukti terkonfirmasi karena itu naik dari 85
menjadi 96 dari 123 kejadian, atau 78,05 persen. Empat perubahan langsung antarpublikasi dan
sepuluh jejak tiga-vintage dibekukan menjadi 14 jejak dengan 38 baris vintage. Pipeline dapat
dijalankan dengan `make h5-run`; laporan, batas klaim, dan uji tulis-baca Iceberg ada di
[`docs/research/h5-revision-trace-and-gate1.md`](docs/research/h5-revision-trace-and-gate1.md).
Uji pada VM menghasilkan marker `H5_VERIFY|38|14|1|3|1`, sehingga 38 baris dapat dibaca kembali
dari tabel Iceberg beserta data file fisiknya.

H6 Jalur A menetapkan kontrak dua tabel: `release_vintages` sebagai dimensi rilis/snapshot dan
`indicator_observations` sebagai fakta sel indikator. `cell_id` stabil lintas sumber, sedangkan
`vintage_id` eksplisit dan diturunkan dari sumber, tanggal vintage, serta checksum manifest. Nilai
numerik eksak dan bentuk angka yang diterbitkan disimpan terpisah agar perbandingan serta reproduksi
sama-sama terjaga. Fixture 38 baris H5 berhasil diproyeksikan menjadi tiga vintage, 38 observasi,
dan 14 sel tanpa kehilangan provenance. Jalankan `make h6-run`; keputusan lengkap ada di
[`docs/research/h6-explicit-vintage-schema.md`](docs/research/h6-explicit-vintage-schema.md).
Uji dua tabel pada VM lulus dengan marker `H6_VERIFY|3|38|14|2|3|1|3|0|0`.

H6 Jalur B membekukan skor kepercayaan untuk perlakuan B2 tanpa menyatakan satu vintage resmi
sebagai kebenaran. Lima dimensi berbobot menilai otoritas resmi, provenance, konteks semantik,
keterstrukturan, dan cakupan sel; nilai observasi serta hasil konflik dilarang masuk skor. Pada 14
sel H6, TPB 2025 dan TPB 2024 sama-sama memperoleh `0,962500`, sedangkan WebAPI memperoleh
`0,907143`; tie-break tanggal menempatkan TPB 2025 pertama. Preview diagnostik memilih TPB 2025
pada seluruh sel, termasuk sepuluh sel yang mempunyai vintage WebAPI lebih baru dan berbeda.
Jalankan `make h6b-run`; rumus dan batas interpretasinya ada di
[`docs/research/h6b-source-trust-score.md`](docs/research/h6b-source-trust-score.md).
Uji pada VM lulus dengan marker `H6B_VERIFY|3|14|4|10|10|frozen`.

H6 Jalur C memetakan lineage 38 observasi H6 menjadi 101 node, 235 edge, dan 38 core path untuk
14 `cell_id`, dengan kelengkapan `1,0000`. Jalur utamanya adalah manifest sumber → artefak →
rekaman sumber → observasi → sel indikator, ditambah konteks vintage, batch, run, dan versi
transformasi. Audit menemukan empat locator PDF yang dipakai ulang oleh 20 observasi; locator
mentah dipertahankan dan node rekaman di-resolve memakai koordinat sel H6 yang eksplisit, tanpa
fuzzy matching. Jalankan `make h6c-run`; model dan batas kelengkapannya ada di
[`docs/research/h6c-cell-lineage.md`](docs/research/h6c-cell-lineage.md).
Uji pada VM lulus dengan marker `H6C_VERIFY|101|235|38|14|4|20|1.0000|validated`.

H7 Jalur A mengimplementasikan B0 sebagai baseline overwrite dengan tepat satu baris terkini per
`cell_id`. Tiga vintage H6 diterapkan berurutan: 38 observasi masuk menjadi 14 baris current,
sementara 24 observasi lama ditimpa. Dari overwrite tersebut, 14 mengubah nilai dan 10 mengganti
baris dengan nilai numerik yang sama. Audit 38 alamat vintage hanya dapat memanggil ulang 14
observasi terkini (`0,3684`); 24 observasi historis gagal sesuai desain B0. Snapshot Iceberg lama
juga dihapus agar time travel tidak mengubah B0 menjadi penyimpanan multiversi. Jalankan
`make h7-run`; kontrak, hasil, dan batas interpretasinya ada di
[`docs/research/h7-b0-overwrite.md`](docs/research/h7-b0-overwrite.md).
Uji pada VM lulus dengan marker `H7_VERIFY|14|14|14|24|1|3|0|0|0`.

H7 Jalur B mengimplementasikan B2 dengan menyalin keputusan skor H6B yang telah dibekukan ke state
single-source. Dari 38 kandidat, 14 observasi TPB 2025 terpilih dan 24 dibuang: 10 karena skor
WebAPI lebih rendah serta 14 karena tie-break terhadap TPB 2024 yang berskor sama tetapi lebih
lama. Hanya empat pilihan merupakan vintage terbaru; sepuluh pilihan lain berbeda nilainya dari
latest-vintage. Audit baca ulang berhasil pada 14 observasi terpilih dan gagal pada 24 observasi
yang dibuang (`0,3684`). Jalankan `make h7b-run`; implementasi dan batas interpretasinya ada di
[`docs/research/h7b-b2-single-source.md`](docs/research/h7b-b2-single-source.md).
Uji idempoten pada VM lulus dengan marker `H7B_VERIFY|14|14|1|10|14|24|1|3|0|0|0`.

H7 Jalur C memperluas graf H6C ke seluruh keputusan B0 dan B2 tanpa mengubah identitas sumber yang
sudah dibekukan. Graf gabungan berisi 207 node, 491 edge, dan 76 path keputusan-ke-output dengan
kelengkapan `1,0000`; 28 alamat masih dapat dibaca dan 48 tidak dapat dibaca sesuai hasil kedua
perlakuan. H7C juga menutup 18 kemunculan status `daftar` yang mewakili 15 sumber unik pada
related work. Seluruhnya kini mempunyai metadata primer dan tidak ada baris `daftar` tersisa.
Jalankan `make h7c-run`; kontrak, koreksi bibliografi, dan batas interpretasinya ada di
[`docs/research/h7c-evidence-lineage.md`](docs/research/h7c-evidence-lineage.md).
Uji pada VM lulus dengan marker
`H7C_VERIFY|15|18|0|207|491|76|28|48|1.0000|4|validated`.

H8 Jalur A mengimplementasikan B1 sebagai tiga snapshot keadaan penuh pada workload yang sama
dengan B0. Setiap rilis membentuk state lengkap 14 sel, sehingga tiga snapshot memuat 42
kemunculan baris logis dan mempertahankan seluruh 38 identitas observasi. State terakhir sama
persis dengan latest-vintage B0, tetapi 24 observasi historis tetap dapat dipanggil melalui
snapshot lama; audit logis berhasil `38/38` (`1,0000`). Angka 42 belum merupakan ukuran byte dan
pengukuran ruang/waktu tetap dijadwalkan pada H10. Jalankan `make h8-run`; kontrak dan batas
interpretasi tersedia di
[`docs/research/h8-b1-full-snapshot.md`](docs/research/h8-b1-full-snapshot.md). Integrasi Iceberg
dijalankan dengan `make h8-apply` dan memeriksa ketiga state memakai `VERSION AS OF`. Uji VM lulus
dengan marker `H8_VERIFY|3|42|14|38|0|3|0|0|0|0`.

H8 Jalur B membangun harness revisi tersuntik deterministik di atas 14 sel latest-vintage. Profil
validasi memakai lima ukuran bertingkat `1-2-4-7-14` dengan seed eksplisit; totalnya 28 baris
injeksi pada lima run independen. Setiap perubahan bernilai tepat satu unit pada presisi publikasi,
mempertahankan dimensi sel, dan ditandai `synthetic_not_official`. Dua puluh route memastikan B0,
B1, B2, dan B3 menerima filter serta checksum payload yang sama untuk setiap skenario. Status route
masih `prepared_not_run`: eksekusi kecil dimulai H9 dan freeze ukuran eksperimen utama tetap H10.
Jalankan `make h8b-run`; rincian tersedia di
[`docs/research/h8b-injected-revision-harness.md`](docs/research/h8b-injected-revision-harness.md).
Uji dua run di VM menghasilkan marker identik
`H8B_VERIFY|14|5|1-2-4-7-14|28|4|20|0|0|3|validation_ready`. Pada 10 September
2026, peninjau manusia menyetujui latest-vintage sebagai nilai awal, perubahan satu unit presisi
publikasi, serta batas sweep utama tepat satu sumber yang direvisi per run. Ketiga keputusan
disimpan di [`config/h8b/human_decisions.csv`](config/h8b/human_decisions.csv).

H8 Jalur C membekukan prosedur audit reproducibility sepuluh langkah dan menerapkannya pada B0,
B1, serta B2. Addressability 114 permintaan dihitung ulang dari state perlakuan, bukan dipercaya
dari label sebelumnya: 66 dapat dipanggil dan 48 tidak tersedia, seluruhnya sesuai kontrak. Graf
H7C 207 node/491 edge diperluas menjadi 294 node/810 edge dengan 114 path lengkap sampai metrik,
tabel bukti, dan data gambar (`1,0000`). B3 tetap deferred dan data gambar belum dianggap sebagai
gambar manuskrip. Jalankan `make h8c-run`; rincian tersedia di
[`docs/research/h8c-reproducibility-lineage.md`](docs/research/h8c-reproducibility-lineage.md).
Commit implementasi `c123402` ditarik ke VM dengan fast-forward. Dua run VM menghasilkan marker
dan checksum artefak yang identik; 68 test lulus, satu test ekstraksi PDF dilewati karena PDF mentah
tidak disimpan di Git, dan working tree VM tetap bersih.

H9 Jalur A mengimplementasikan B3, perlakuan usulan. Setiap observasi disimpan di tabel append-only
dengan kunci eksplisit `(cell_id, vintage_id)`, sedangkan tabel serving hanya diperbarui untuk sel
yang ditandai kotor oleh edge lineage H6C. Pada tiga rilis nyata, 38 observasi masuk ke store dan
membentuk 14 baris serving. Sel yang dihitung ulang berjumlah 14, 14, lalu 10, sehingga totalnya
38 evaluasi dibanding 42 bila dihitung ulang penuh (`0,9048`). Setelah setiap kedatangan, hasil
inkremental sama persis dengan penghitungan ulang penuh. State akhir sama dengan B0/B1, dan ketiga
state as-of hasil rekonstruksi sama dengan snapshot B1. Semua `38/38` observasi dapat dipanggil
melalui kunci vintage tanpa bergantung pada snapshot tabel. Pada workload ini penghematan
inkremental kecil karena hampir semua sel direvisi. B3 juga menyimpan 52 baris logis (store dan
serving), lebih banyak daripada 42 pada B1. Angka ini bukan ukuran byte, dan pengukuran fisik tetap
dijadwalkan pada H10. Jalankan `make h9-run`; rincian ada di
[`docs/research/h9-b3-vintage-aware.md`](docs/research/h9-b3-vintage-aware.md).
Integrasi Iceberg `make h9-apply` lulus di VM. Commit `c2a249d` ditarik ke VM `praktikum-sd` (`sigerciv@34.101.84.199`). Dua run `make h9-run` menghasilkan checksum yang sama dengan lokal, dan dua run `make h9-apply` lulus dengan marker `H9_VERIFY|38|38|14|14|38|0|1|1|0|0|42|0`. Marker itu berarti 38/38 observasi tetap terbaca melalui kunci vintage setelah snapshot kedua tabel B3 dihapus sampai tersisa satu, dan ketiga state as-of sama dengan snapshot B1.

H9 Jalur B menjalankan harness H8B untuk pertama kalinya. Kelima skenario validasi `1-2-4-7-14`
dikirim tanpa perubahan ke B0–B3, sehingga ada 20 route yang dieksekusi secara logis. Checksum
payload setiap route cocok, dan replay tanpa injeksi menghasilkan kembali state manifest keempat
perlakuan. Vintage sintetis diberi tanggal sehari setelah rilis resmi terakhir (2026-09-09), sesuai
keputusan manusia 11 September 2026 yang juga menyetujui histori B3 sebagai baris, kunci resolusinya,
dan tabel serving yang dimaterialisasi (lihat
[`config/h9/human_decisions.csv`](config/h9/human_decisions.csv)). B0, B1, dan B3 menyajikan semua 28
revisi. B2 hanya menyajikan 8 revisi dan mengabaikan 20 revisi atas sel WebAPI karena skor sumbernya
lebih rendah. B0 kehilangan ke-28 nilai yang direvisi, sedangkan B1 dan B3 tetap dapat memanggil
seluruh observasi resmi dan sintetis. B3 menghitung ulang tepat 1, 2, 4, 7, dan 14 sel. Belum ada
waktu atau byte yang diukur. Jalankan `make h9b-run`; rincian ada di
[`docs/research/h9b-small-revision-execution.md`](docs/research/h9b-small-revision-execution.md).
Marker: `H9B_VERIFY|5|20|20|0|28|28|70|28|8|0|0|executed_logical`; dua run di VM identik dengan lokal, dan
83 test VM lulus dengan satu test PDF dilewati.

H9 Jalur C mengaudit 38 permintaan B3 dengan prosedur H8C yang dikunci checksum-nya, lalu
menurunkan ulang sel kotor B3 dari graf secara independen. Hasilnya, 38 baris impact cocok tanpa
selisih dan setiap baris serving terakhir dihitung ulang pada kedatangan terakhir yang menyentuh
selnya. Tabel empat perlakuan menunjukkan B0 `0,3684`, B1 `1,0000` melalui snapshot, B2 `0,3684`,
dan B3 `1,0000` melalui kunci vintage. Graf H8C diperluas menjadi 377 node dan 1.088 edge dengan
152 path lengkap (`1,0000`). Jalankan `make h9c-run`; rincian ada di
[`docs/research/h9c-b3-lineage-audit.md`](docs/research/h9c-b3-lineage-audit.md). Marker lokal:
`H9C_VERIFY|294|810|377|1088|152|104|48|1.0000|4|38|38|0|validated`.
Marker yang sama dan checksum identik juga muncul pada dua run di VM, dengan 78 test lulus dan satu
test PDF dilewati. Pada saat H9C ditutup, Gate G2 belum lolos karena keempat perlakuan belum
dijalankan pada workload tersuntik yang identik dan berkas freeze H10 belum ditulis. Keduanya
diselesaikan pada H10 Jalur B dan H10 Jalur C.

H10 Jalur A mengukur ruang fisik keempat perlakuan pada workload nyata H6, dalam tiga repetisi
purge-rebuild-ukur berurutan di VM 2 vCPU yang dinyatakan untuk pengukuran byte. Waktu belum diukur.
Pengukuran didahului satu perbaikan: katalog Iceberg REST ternyata in-memory sehingga hilang saat VM
reboot. Katalog dipindahkan ke SQLite persisten, dan semua tabel H5–H9 dibangun ulang dengan marker
yang identik dengan catatan lama. Footprint dihitung dari objek yang dirujuk metadata snapshot yang
dipertahankan, dengan ukuran dari MinIO. Median totalnya: B0 95.898 B, B1 190.261 B, B2 64.077 B,
dan B3 240.884 B. Pada fixture 14 sel, B3 terbesar karena tabel serving yang dimaterialisasi. Store
B3 saja (146.352 B) 23% lebih kecil daripada B1. Metadata Iceberg sebanding dengan data, bahkan
melampauinya pada B0 dan B3. Setelah katalog di-restart, B1 dan B3 tetap memanggil ulang 38/38
observasi secara persis, sedangkan B0 dan B2 14/38. Jalankan `make h10-run`; rincian ada di
[`docs/research/h10-storage-recall.md`](docs/research/h10-storage-recall.md). Marker:
`H10_VERIFY|3|95898|190261|64077|240884|14|38|14|38|variable|measured`. Label `variable` berasal dari
selisih 4–18 byte pada metadata antarrepetisi.

H10 Jalur B menjalankan revisi tersuntik H8B secara fisik di Iceberg, bukan lagi secara logis seperti
H9B. Dua skenario beku dieksekusi dalam tiga repetisi: `validation_001` (1 sel WebAPI, jalur B2 yang
menahan revisi) dan `validation_002` (2 sel, jalur B2 yang meneruskan satu revisi). Setiap siklus
membangun ulang keempat tabel dari workload nyata, menyuntikkan revisi melalui mekanisme tulis milik
tiap perlakuan, lalu mengukur waktu pernyataan dan pertambahan byte. Pada revisi satu sel, B1 justru
paling murah dalam waktu (5,4 s satu pernyataan, tanpa pemeliharaan) dan B3 paling mahal (13,4 s dua
pernyataan ditambah 21,0 s `expire_snapshots`), karena pada fixture 14 sel ongkos tetap per pernyataan
lebih besar daripada pekerjaan datanya. Dalam byte, B1 menambah 68.447 byte baik untuk satu maupun dua
sel karena selalu menulis ulang seluruh state, sedangkan B3 menambah 60.156 byte untuk satu sel dan
71.483 byte untuk dua sel. Metadata Iceberg mendominasi: revisi satu nilai di B0 mengubah 161 byte
data tetapi menambah 23.915 byte metadata. B2 membayar penuh ongkos tulis meskipun menahan revisinya.
Setelah revisi, B1 dan B3 tetap memanggil ulang seluruh observasi resmi dan sintetis (39/39 dan
40/40), sedangkan B0 dan B2 hanya 14. Seluruh hasil fisik sama persis dengan audit logis H9B.
Sebelum pengukuran, 64 objek sisa run 9 September (585.261 byte) dibersihkan dengan
`remove_orphan_files`. Jalankan `make h10b-prepare`, `make h10b-cleanup`, `make h10b-measure`, dan
`make h10b-run`; rincian ada di
[`docs/research/h10b-injected-revision-physical.md`](docs/research/h10b-injected-revision-physical.md).
Marker:
`H10B_VERIFY|3|2|8|64|585261|9.818|5.442|5.308|13.388|24076|68447|24564|60156|14|39|14|39|measured`.

H10 Jalur C menutup H10 dengan membekukan konfigurasi eksperimen sesuai daftar §4.4 dan mencatat
definisi kedelapan metrik §4.2. Lima keputusan disetujui peninjau pada 12 September 2026. Fixture 14
sel dipertahankan sebagai basis bukti P1, P2, dan P4, sedangkan sweep P3 dipindahkan ke panel
provinsi berisi 6.983 observasi pada 5.378 sel setelah 683 baris duplikat `(cell_id, source_id)`
yang nilainya terbukti identik dibuang. Alasannya diambil dari H10B: pada fixture 14 sel ongkos
tetap satu pernyataan mengalahkan pekerjaan datanya, sehingga titik impas tidak mungkin teramati.
Semesta sweep adalah `sdg08_productivity_growth` 2025 pada seluruh 38 provinsi dengan sumber tunggal
`bps_webapi`, dengan titik `1-2-4-8-16-38` dan seed `20260912`, sehingga titik terbesarnya benar-benar
satu tahun penuh seluruh provinsi dan aturan satu sumber per run terpenuhi di setiap titik. Tingkat
propagasi revisi dibekukan sebagai metrik pendukung, dan VM 2 vCPU dibekukan sebagai batas sumber
daya seluruh eksperimen. Freeze, alasan setiap nilai, dan cara verifikasinya ada di
[`docs/research/experiment-freeze.md`](docs/research/experiment-freeze.md); nilainya tersimpan di
[`config/experiments/`](config/experiments/) dan keputusannya di
[`config/h10c/human_decisions.csv`](config/h10c/human_decisions.csv). Dengan berkas freeze ini
kriteria keempat terpenuhi dan **Gate G2 dinyatakan lolos**. Seluruh 105 test lulus.

H11 menjalankan sweep utama P3 dan menutupnya dengan jawaban negatif untuk waktu. Panel provinsi
beku diproyeksikan ke skema vintage H6 menjadi 6.983 observasi pada 5.378 sel dan empat vintage,
setelah 683 baris duplikat `(cell_id, source_id)` yang nilainya terbukti identik dibuang. Keempat
perlakuan dibangun ulang di atas panel itu dengan mekanisme tulis masing-masing, lalu revisi
tersuntik berukuran 1, 2, 4, 8, 16, dan 38 sel dieksekusi dalam tiga repetisi, seluruhnya 72 route
selama 2 jam 9 menit. Waktu keempat perlakuan praktis datar: B1 10,1 detik, B2 23,1 sampai 24,6
detik, B0 24,7 sampai 26,0 detik, dan B3 35,6 sampai 38,0 detik, berapa pun besaran revisinya.
Penyebabnya terukur, yaitu pernyataan tulis 9,5 sampai 11,3 detik berapa pun ukuran revisi ditambah
`expire_snapshots` 13,3 sampai 22,1 detik; B1 tercepat justru karena mekanismenya tidak menuntut
pemeliharaan snapshot. Dalam ruang urutannya berbalik: B1 menambah sekitar 468 KB pada setiap revisi
karena selalu menulis salinan penuh 5.378 sel, sedangkan B3 menambah 49 sampai 53 KB, yaitu 8,9
sampai 9,5 kali lebih sedikit, dan B0 paling murah dengan 13,3 sampai 14,5 KB. Merevisi satu nilai di
B0 mengubah 279 byte data tetapi menambah 13.000 byte metadata. B0 dan B3 mengevaluasi tepat sel yang
direvisi sedangkan B1 dan B2 menghitung ulang seluruh 5.378 sel, sehingga penghematan inkremental
nyata dalam pekerjaan logis dan ruang tetapi habis diserap ongkos tetap pernyataan dalam waktu. Tidak
ada titik impas di dalam rentang beku pada kedua ukuran: B3 lebih murah daripada B1 dalam byte di
seluruh rentang dan lebih mahal dalam waktu di seluruh rentang. Recall B1 dan B3 tetap `1,0000` atas
6.983 permintaan panel plus permintaan sintetis, sedangkan B0 dan B2 `0,7660` sampai `0,7700`.
Propagasi revisi bernilai 1,0000 pada keempat perlakuan karena semesta sweep hanya dilayani satu
sumber, sehingga perilaku menahan B2 pada H9B tidak dapat muncul di sini. Jalankan `make h11-prepare`,
`make h11-measure` di host stack, lalu `make h11-run`; rincian, batas klaim, dan satu bug presedensi
SQL yang ditemukan serta diperbaiki sebelum run utama ada di
[`docs/research/h11-main-sweep.md`](docs/research/h11-main-sweep.md). Marker:
`H11_VERIFY|3|6|72|6983|5378|24.652|10.056|24.616|38.007|24.861|10.068|23.052|35.626|14459|469682|26363|52873|0.7660|1.0000|0.7660|1.0000|none|none|measured`.
Agregasi yang dijalankan ulang di VM menghasilkan marker dan checksum seluruh keluaran yang identik
dengan laptop, dan 133 test lulus dengan satu test PDF dilewati.

H12 sisi operator mengukur ongkos revisi yang benar-benar diterbitkan, bukan revisi buatan. Keempat
rilis yang membangun panel diterapkan satu per satu pada keempat perlakuan dalam tiga repetisi;
ketiga kedatangan terakhir menimpa 1.605 baris dan 43 di antaranya benar-benar mengubah nilai terbit,
sedangkan 1.562 sisanya menuliskan ulang nilai yang sama. Urutan biayanya sama persis dengan hasil
sweep tersuntik: B1 15,050 detik untuk keempat rilis, B2 47,688 detik, B0 52,184 detik, dan B3 88,929
detik, dengan pemeliharaan snapshot menghabiskan sekitar dua pertiga waktu B0, B2, dan B3. Temuan
H11 karena itu bukan artefak revisi buatan. Dua hal baru muncul di sini. Pertama, pada skala ini
`MERGE` lebih mahal daripada penulisan ulang penuh: rilis kedua membawa 62 baris tetapi `MERGE` B0
memakan 3,929 detik sedangkan `INSERT OVERWRITE` B1 yang menuliskan 3.144 baris hanya 2,315 detik.
Kedua, keunggulan ruang B3 ternyata bergantung pada seberapa besar bagian keadaan yang disentuh tiap
rilis; setelah keempat rilis nyata yang banyak menambah sel baru, byte terujuk B3 dan B1 praktis sama,
839.008 berbanding 837.744. Jalankan `make h12-measure` lalu `make h12-run`; rincian ada di
[`docs/research/h12-real-revision-cost.md`](docs/research/h12-real-revision-cost.md). Marker:
`H12_VERIFY|3|4|43|52.184|15.050|47.688|88.929|329276|837744|312945|839008|measured`; agregasi yang
diulang di VM menghasilkan checksum identik dan 143 test lulus dengan satu test PDF dilewati. Draf Metode
ditulis Jalur A dan C pada hari yang sama di
[`papers/vintage_reconciliation/draft/04-metode.md`](papers/vintage_reconciliation/draft/04-metode.md),
lengkap dengan bagian ancaman terhadap validitas.

H13 sisi operator menguji apakah angka yang sudah dilaporkan cukup stabil untuk dipakai. Aturan
keraguan ditetapkan lebih dahulu, yaitu sebaran fase tulis melebihi 20 persen mediannya, lalu
diterapkan secara mekanis pada seluruh 40 titik pengukuran H11 dan H12. Enam titik melewati ambang,
dan repetisi yang melar tidak berkumpul pada satu repetisi tertentu, sehingga penyebabnya derau node
bersama dan bukan efek pemanasan yang dapat dibuang. Kedua unit yang memuatnya dijalankan ulang
dengan tiga repetisi tambahan, sehingga 20 titik memperoleh enam repetisi: 18 stabil dan 2 bergeser.
Keempat titik paling meragukan justru bertahan, misalnya B2 pada `sweep_001` bergerak hanya dari
9,998 menjadi 9,956 detik. Dua yang bergeser berada pada H12, yaitu kedatangan 2 perlakuan B2 dari
2,064 menjadi 2,250 detik dan kedatangan 3 perlakuan B0 dari 3,497 menjadi 3,319 detik; keduanya
dikoreksi di laporan H12 dan dicatat di
[`docs/research/decision-log.md`](docs/research/decision-log.md) sebagai `dl-06`, dan tidak satu pun
kesimpulan berubah karenanya. Median terbitan tidak pernah diganti, melainkan dilaporkan berdampingan
dengan median gabungan. Jalankan `make h13-rerun` lalu `make h13-run`; rincian ada di
[`docs/research/h13-rerun-stability.md`](docs/research/h13-rerun-stability.md). Marker:
`H13_VERIFY|40|6|20|3|18|2|0.0901|verified`.

H13 Jalur C menjawab P4 pada skala panel dan menutup butir §13 tentang analisis kegagalan. Prosedur
audit sepuluh langkah yang dibekukan H8C dijalankan atas seluruh 6.983 angka terbit panel untuk
keempat perlakuan. B1 dan B3 memanggil ulang seluruhnya (`1,0000`), sedangkan B0 dan B2 sama-sama
gagal pada 1.605 permintaan (`0,7702`). Angka yang sama itu menyembunyikan perbedaan yang penting:
B0 kehilangan yang lama karena ditimpa, yaitu 1.556 baris TPB 2024 dan 49 baris TPB 2025, sedangkan
B2 kehilangan yang baru karena skornya lebih rendah, yaitu 1.567 baris WebAPI dan 38 baris TPB 2024.
Dari 1.605 kegagalan itu, hanya **43** membawa nilai yang berbeda dari yang kini disajikan; 1.562
sisanya duplikat nilai yang sama dari sumber lain. Empat puluh tiga angka itulah kerugian
reproducibility yang sebenarnya, dan seluruhnya dicatat baris per baris beserta nilai pengganti serta
locator sumbernya. Satu bentuk kegagalan ketiga tidak muncul pada tingkat keberhasilan sama sekali:
B2 menyajikan nilai yang sudah digantikan produsen pada 39 sel, karena ia memilih menurut skor
kepercayaan dan bukan menurut kebaruan. Tingkat keberhasilan juga sangat bergantung beban: pada
fixture yang setiap selnya direvisi B0 kehilangan 63 persen, pada panel ia kehilangan 23 persen, dan
keduanya dilaporkan berdampingan. Audit ini diturunkan dari panel beku lalu dicocokkan dengan recall
fisik sweep H11 pada 24 pasangan skenario-perlakuan tanpa satu pun selisih, dengan kelengkapan
lineage `1,0000`. Jalankan `make h13c-run`; rincian ada di
[`docs/research/h13c-reproducibility-audit.md`](docs/research/h13c-reproducibility-audit.md). Marker:
`H13C_VERIFY|6983|0.7702|1.0000|0.7702|1.0000|1605|0|1605|0|43|0|43|0|39|1.0000|125|validated`.

Semua angka dan tabel untuk naskah dikumpulkan di
[`papers/vintage_reconciliation/`](papers/vintage_reconciliation/README.md): 44 tabel per pertanyaan
penelitian, 3 tabel turunan, dan 160 angka kunci beserta sumber serta cara penurunannya. Paket dibentuk
dengan `make article-bundle`, yang memverifikasi checksum setiap sumber terhadap manifest tahapnya.
Bahan mentah sumber di `data/raw/` hanya ada di laptop peneliti. `make raw-backup` membuat arsip
beserta daftar checksum di `backups/`, dan arsip itu wajib disalin ke lokasi kedua.

Menaikkan fondasi sebelum G1 diputuskan adalah taruhan yang disengaja. Bila G1 gagal, yang hangus satu orang-minggu, bukan pekerjaan seluruh tim. Pada rencana peneliti tunggal, taruhan ini tidak diambil karena ongkos gagalnya menjadi seluruh minggu.

**Gate G1 — Objek penelitian terbukti ada**

Lolos bila ketiga hal berikut terpenuhi.

1. Ketidaksesuaian antarsumber terukur pada minimal tiga dari lima domain.
2. Sebagian besar ketidaksesuaian dapat dijelaskan oleh salah satu dari tiga sebab pada §1.1. Ambang yang diusulkan adalah 70 persen, ditetapkan di muka sebagai parameter rencana, bukan sebagai temuan.
3. Terdapat jejak revisi antarwaktu yang dapat diamati.

Bila kriteria 1 gagal, persoalan yang diteliti tidak ada dan pembangunan dihentikan. Desain dibalik ke salah satu alternatif yang sudah dipetakan, yaitu tata letak spasial SDG 15 atau pertanyaan tentang kapan arsitektur lakehouse berlebihan untuk statistik resmi.

Bila kriteria 3 gagal sementara kriteria 1 lolos, revisi nyata tidak dapat diamati. P1, P2, dan P4 tetap berjalan di atas ketidaksesuaian antarsumber, sedangkan P3 sepenuhnya bergantung pada revisi tersuntik. Keterbatasan ini wajib dinyatakan di dalam naskah, bukan disembunyikan.

### 6.4 Minggu 2 — Fondasi, perlakuan, dan lineage

Ketiga jalur berjalan serentak. Pembanding diselesaikan lebih dahulu daripada usulan agar B3 punya titik banding yang sudah terbukti berjalan.

| Hari | Jalur A — Fondasi | Jalur B — Perlakuan | Jalur C — Bukti |
|---|---|---|---|
| H6 | Merancang skema tabel indikator dengan vintage sebagai dimensi eksplisit | Menyusun skor kepercayaan sumber untuk B2 | Memetakan lineage dari sel indikator ke rekaman sumber |
| H7 | Mengimplementasikan B0 | Mengimplementasikan B2 | Melanjutkan lineage dan memverifikasi sumber bertanda `daftar` pada related-work |
| H8 | Mengimplementasikan B1 | Membangun harness revisi tersuntik | Menutup lineage dan menyusun prosedur audit reproducibility |
| H9 | Bersama Jalur C mengimplementasikan B3 | Menguji harness pada besaran revisi kecil | Bersama Jalur A mengimplementasikan B3 |
| H10 | Menguji pemanggilan ulang angka lama pada B1 dan mengukur ruang | Menjalankan keempat perlakuan pada satu skenario revisi kecil | Membekukan konfigurasi eksperimen, lalu menulis draf Pendahuluan dan Kedudukan terhadap Literatur |

Pada akhir H10 seluruh konfigurasi eksperimen dibekukan sesuai daftar pada §4.4.

**Gate G2 — Keempat perlakuan berjalan pada beban yang sama**

Lolos bila keempat perlakuan dapat dijalankan pada beban revisi yang identik, angka lama benar-benar dapat dipanggil ulang pada B1, seluruh harness dapat diulang dari script tanpa langkah manual, dan berkas freeze sudah ditulis.

**Gate G2 dinyatakan lolos pada 12 September 2026.** Keempat perlakuan dieksekusi pada beban yang
identik secara logis di H9B (20 route, checksum payload sama) dan secara fisik di H10B (8 route, tiga
repetisi, hasil sama persis dengan audit logis). B1 memanggil ulang 38/38 observasi setelah katalog
di-restart pada H10A, serta 39/39 dan 40/40 setelah revisi disuntikkan pada H10B. Seluruh harness
berjalan dari Makefile dengan marker dan checksum identik pada satu run lokal dan dua run VM. Berkas
freeze ditulis pada H10 Jalur C. Pemeriksaan per kriteria beserta buktinya ada di
[`docs/research/experiment-freeze.md`](docs/research/experiment-freeze.md).

Bila B3 gagal berjalan, turunkan cakupan alih-alih memaksakannya. Jalankan B0, B1, dan B2 saja, lalu laporkan B3 sebagai rancangan yang belum tervalidasi. Artikel berubah bentuk menjadi karakterisasi empiris ditambah perbandingan pembanding, dan itu tetap kontribusi yang sah.

### 6.5 Minggu 3 — Eksperimen, analisis, dan draf

Eksekusi eksperimen dipegang satu operator dari Jalur B dan dijalankan berurutan. Jalur lain tidak menyentuh node selama pengukuran berlangsung.

| Hari | Operator eksperimen | Jalur A dan C |
|---|---|---|
| H11 | Sweep revisi tersuntik dari satu sel sampai satu tahun penuh seluruh provinsi | Menyiapkan script analisis dan kerangka tabel hasil |
| H12 | Menjalankan keempat perlakuan pada revisi nyata dari H5 | Menulis draf Metode |
| H13 | Menjalankan ulang run yang gagal atau meragukan | Audit reproducibility keempat perlakuan untuk menjawab P4 |
| H14 | Mengumpulkan raw timing, query plan, dan log | Mencari titik impas inkremental dan mengerjakan analisis kegagalan |
| H15 | Memastikan seluruh hasil dapat dibentuk ulang dari `results/raw/` | Menyusun tabel dan gambar, lalu menulis draf bagian Hasil |

**Gate G3 — Pertanyaan penelitian terjawab**

Lolos bila keempat sub-pertanyaan terjawab dari hasil eksperimen, titik impas ditemukan atau dinyatakan secara eksplisit tidak ada, minimal satu analisis kegagalan tersedia, dan seluruh hasil dapat dibentuk ulang dari repository.

Jawaban negatif pada P3, yaitu pendekatan inkremental ternyata tidak lebih murah, tetap dihitung lolos sepanjang titik impasnya terukur dan alasannya dapat dijelaskan.

### 6.6 Yang dihasilkan dan yang belum

Tiga minggu ini menghasilkan inti eksperimen, draf Pendahuluan, Metode, dan Hasil. Pembahasan, Kesimpulan, serta penyuntingan akhir berada di luar jendela ini. Sebagai pembanding, katalog DSIC-RG memberi empat bulan untuk topik mahasiswa yang cakupannya lebih sempit daripada penelitian ini, sehingga jadwal ini hanya berjalan bila akses data lancar sejak hari pertama.

### 6.7 Bila jadwal meleset

Akhir pekan dipakai sebagai penyangga, bukan sebagai hari kerja tambahan yang direncanakan. Bila satu minggu meleset lebih dari dua hari, yang dipotong adalah cakupan, bukan gate. Urutan pemotongan yang disarankan: kurangi jumlah indikator yang diuji, lalu kurangi jumlah titik pada sweep H11, dan paling akhir kurangi jumlah domain dari lima menjadi tiga.

Keempat perlakuan dan ketiga gate dipertahankan dalam kondisi apa pun, karena keduanya yang menjaga hasil tetap dapat dipertanggungjawabkan.

Satu risiko khas kerja tim perlu dijaga sejak awal. Enam peneliti pada satu naskah mudah terpecah menjadi enam pekerjaan yang berdiri sendiri. Setiap jalur karena itu menyerahkan keluaran ke repository bersama pada akhir tiap hari, dan tidak ada jalur yang menyimpan hasil di mesin masing-masing sampai akhir minggu.

## 7. Target Luaran

Target utamanya adalah artikel jurnal Q1 Scopus, dengan kandidat berikut menurut urutan prioritas.

1. *Data & Knowledge Engineering* (Elsevier), yaitu venue tempat kelompok SDG-KG menerbitkan versi jurnalnya, sehingga topik ini terbukti diterima di sana.
2. *Information Systems* (Elsevier).
3. *Journal of Big Data* (Springer).

Bila hasilnya ternyata lebih condong ke audiens statistik resmi, *Statistical Journal of the IAOS* menjadi alternatif yang lebih sesuai.

Research track VLDB, SIGMOD, dan ICDE tidak dijadikan target. Skala data dan perangkat keras yang tersedia tidak mendukung klaim yang diharapkan venue tersebut, dan SDG-KG sendiri masuk VLDB melalui jalur demo.

---

## 8. Batas Klaim

Klaim yang boleh dibuat terbatas pada empat hal berikut.

- karakterisasi empiris ketidaksesuaian antarsumber resmi BPS pada lima domain;
- rancangan penyimpanan vintage indikator di atas format tabel terbuka;
- pengukuran ongkos penghitungan ulang dan titik impas inkremental;
- bukti reproducibility angka terbit.

Sebaliknya, hal-hal berikut tidak boleh diklaim.

- kebaruan algoritma truth discovery atau incremental view maintenance;
- klaim skalabilitas atau performa pada data besar;
- klaim tentang platform SDG nasional yang siap produksi;
- generalisasi ke seluruh 17 SDG atau ke negara lain.

---

## 9. Infrastruktur

Komponen yang diaktifkan hanya yang benar-benar dibutuhkan pertanyaan penelitian.

Wajib:

- MinIO — object storage;
- Apache Iceberg — format tabel terbuka, snapshot, dan time travel;
- Apache Spark / PySpark — pemrosesan;
- Docker Compose — deployment yang dapat diulang;
- Git — versioning kode dan konfigurasi.

Komponen opsional berikut sudah dinilai pada H7C dan **belum digunakan**:

| Komponen | Status sekarang | Pemicu penggunaan |
|---|---|---|
| Trino | Tidak digunakan; query saat ini memakai Spark SQL | Aktifkan hanya bila eksperimen lintas query engine disetujui |
| OpenMetadata | Tidak digunakan; lineage disimpan sebagai CSV/manifest deterministik | Aktifkan bila UI katalog atau integrasi governance menjadi objek evaluasi |
| Apache Airflow | Tidak digunakan; pipeline dijalankan sebagai batch beku melalui Makefile | Aktifkan bila penarikan terjadwal masuk protokol |
| GeoPandas | Tidak digunakan; workload geometri SDG 15 belum aktif | Aktifkan setelah sumber geometri gratis disetujui dan eksperimen spasial dibuka |

Keputusan mesin-baca dan pemicunya berada di
[`config/h7c/component_decisions.csv`](config/h7c/component_decisions.csv).

Tidak dipakai pada artikel ini: Sedona, PostGIS, agen AI text-to-SQL, dashboard, dan seluruh komponen MLOps. Semuanya di luar pertanyaan penelitian.

---

## 10. Struktur Repository

```text
.
├── README.md
├── .gitignore
├── .env.example
├── pyproject.toml
├── docker-compose.yml
├── Makefile
│
├── docs/
│   ├── research/
│   │   ├── related-work.md
│   │   ├── rq-main.md
│   │   ├── hypotheses.md
│   │   ├── scope-freeze.md
│   │   ├── experiment-freeze.md
│   │   └── decision-log.md
│   ├── architecture/
│   └── protocols/
│
├── config/
│   ├── domains/
│   ├── indicators/
│   └── experiments/
│
├── data/
│   ├── manifests/
│   ├── reference/
│   ├── raw/
│   ├── bronze/
│   ├── silver/
│   └── gold/
│
├── contracts/
│
├── infra/
│   ├── docker/
│   ├── minio/
│   ├── iceberg/
│   ├── spark/
│   ├── trino/
│   └── openmetadata/
│
├── src/
│   └── kkciv_vintage/
│       ├── ingestion/
│       ├── vintage/
│       ├── reconciliation/
│       ├── lineage/
│       ├── recomputation/
│       ├── evaluation/
│       └── utils/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── reproducibility/
│
├── experiments/
│   ├── E0_overwrite_baseline/
│   ├── E1_discrepancy_characterization/
│   ├── E2_vintage_storage/
│   ├── E3_recomputation_cost/
│   └── E4_reproducibility_audit/
│
├── results/
│   ├── raw/
│   ├── processed/
│   ├── tables/
│   ├── figures/
│   └── failure_cases/
│
├── papers/
│   └── vintage_reconciliation/
│
├── scripts/
└── notebooks/
    └── exploratory/
```

Direktori `research_tracks/` dan `papers/T*_student_paper/` dari rancangan sebelumnya tidak lagi dipakai.

---

## 11. Aturan Data

Raw data tidak di-commit ke Git.

Yang wajib di-version-control:

- source manifest;
- source URL atau identifier;
- tanggal penarikan;
- checksum;
- schema;
- data dictionary;
- versi preprocessing;
- versi kode referensi;
- konfigurasi eksperimen.

Karena penelitian ini justru tentang revisi, satu aturan tambahan berlaku: **setiap penarikan ulang dari sumber yang sama disimpan sebagai vintage baru, tidak menimpa yang lama.** Menimpa penarikan lama akan menghancurkan bukti yang menjadi objek penelitian.

---

## 12. Reproducibility

Setiap direktori eksperimen minimal memuat:

```text
README.md
config.yaml
run.sh
results-manifest.json
notes.md
```

Raw timing, query plan, statistik pembacaan, dan log disimpan sebelum agregasi statistik dilakukan. Hasil di `results/processed/` harus dapat dibentuk ulang dari `results/raw/` memakai script yang tersedia di dalam repository. Eksperimen yang gagal karena bug boleh diulang, tetapi alasan pengulangannya dicatat pada decision log.

---

## 13. Definition of Done

Artikel dianggap siap disubmit jika:

- keempat sub-pertanyaan terjawab dari hasil eksperimen, termasuk bila jawabannya negatif;
- keempat perlakuan dibandingkan pada beban revisi yang sama;
- metrik utama dan audit reproducibility tersedia;
- minimal satu analisis kegagalan dilakukan, yaitu kondisi ketika angka lama gagal dihasilkan ulang;
- seluruh hasil dapat dijalankan ulang dari repository;
- tidak ada klaim yang melampaui bukti, khususnya klaim skalabilitas;
- batas klaim terhadap SDG-KG dan literatur truth discovery dinyatakan eksplisit di dalam naskah.

---

## 14. Yang Berada di Luar Cakupan

Beberapa komponen sengaja tidak dikerjakan pada artikel ini.

- text-to-SQL agent;
- dashboard produksi;
- model peramalan;
- seluruh 17 SDG;
- Kubernetes, streaming, feature store, generative AI;
- analitik spasial SDG 15 di luar perlakuan geometri sebagai data referensi;
- platform SDG nasional siap produksi.

Komponen tersebut dapat menjadi penelitian lanjutan setelah artikel ini selesai.

---

**Research umbrella:** KK-CIV 2026  
**Research group:** Data Systems and Intelligent Computing (DSIC)  
**Fokus artikel:** Vintage-aware reconciliation and recomputation of official SDG indicators
