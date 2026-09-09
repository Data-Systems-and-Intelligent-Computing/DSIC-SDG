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
- proporsi ketidaksesuaian yang dapat dijelaskan otomatis sebagai vintage, metodologi, atau granularitas.

### 4.3 Beban kerja revisi

Revisi yang diuji berasal dari dua sumber, dan keduanya diperlukan untuk alasan yang berbeda.

Revisi nyata diambil dari perbedaan antarsumber dan antarrilis BPS yang benar-benar terjadi pada rentang yang ditarik. Inilah yang menjadi bukti utama untuk P1.

Revisi tersuntik diperlukan karena besaran revisi nyata tidak dapat dikendalikan. Revisi sintetis dengan besaran terkontrol, mulai dari satu sel sampai satu tahun penuh untuk seluruh provinsi, disuntikkan agar titik impas pada P3 dapat dicari secara sistematis. Prosedur penyuntikannya dicatat dan dapat dijalankan ulang.

### 4.4 Yang dibekukan sebelum eksperimen utama

1. snapshot dataset dan tanggal penarikan;
2. daftar indikator yang diuji per domain;
3. definisi ketidaksesuaian dan aturan klasifikasinya;
4. keempat perlakuan;
5. metrik utama;
6. besaran revisi tersuntik;
7. batas sumber daya.

Konfigurasi tidak boleh diubah setelah melihat hasil tanpa membuat versi eksperimen baru.

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

Fondasi H3 juga aktif pada VM `sigerciv@34.128.67.92`: MinIO, Iceberg REST, dan Spark/Jupyter
telah lolos pemeriksaan kesehatan dan Spark berhasil mengakses katalog `kkciv`. Versi serta digest
image dibekukan di [`infra/docker/`](infra/docker/). Jalankan `make stack-remote-status` untuk
memeriksa layanan dan `make stack-remote-up` untuk menyinkronkan konfigurasi lalu menaikkannya.

H4 menerapkan delapan aturan klasifikasi yang sama pada kelima domain dan membentuk batch ingestion
ber-manifest berisi 7.666 observasi. Dari 123 kejadian, 104 atau 84,55 persen masuk keluarga
vintage, metodologi, atau granularitas bila bukti kandidat ikut dihitung. Bukti terkonfirmasi baru
85 kejadian atau 69,11 persen, sedikit di bawah ambang 70 persen. Gate G1 karena itu tetap
`pending_H5`; H5 perlu mengonfirmasi minimal dua kandidat dan membekukan jejak revisinya. Hasil,
aturan, serta batas interpretasinya tersedia di
[`docs/research/h4-classification-and-ingestion.md`](docs/research/h4-classification-and-ingestion.md).

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
| H10 | Menguji pemanggilan ulang angka lama pada B1 dan mengukur ruang | Menjalankan keempat perlakuan pada satu skenario revisi kecil | Menulis draf Pendahuluan dan Kedudukan terhadap Literatur |

Pada akhir H10 seluruh konfigurasi eksperimen dibekukan sesuai daftar pada §4.4.

**Gate G2 — Keempat perlakuan berjalan pada beban yang sama**

Lolos bila keempat perlakuan dapat dijalankan pada beban revisi yang identik, angka lama benar-benar dapat dipanggil ulang pada B1, seluruh harness dapat diulang dari script tanpa langkah manual, dan berkas freeze sudah ditulis.

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

Dipakai bila diperlukan:

- Trino — query analitik;
- OpenMetadata — bukti lineage dan governance;
- Apache Airflow — orkestrasi bila jadwal penarikan perlu otomatis;
- GeoPandas — hanya untuk geometri referensi SDG 15.

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
