# Rekap Teknis dan Panduan Audit H1–H6C, H7A, dan H7B

Dokumen ini mencatat pekerjaan yang **sudah benar-benar dieksekusi** sampai H6 Jalur C, H7 Jalur A, dan H7 Jalur B. Tujuannya agar peneliti manusia dapat memeriksa ulang angka, keputusan metodologis, kode, serta bukti eksekusi di VM tanpa harus menebak alurnya dari riwayat Git.

Rekap ini membekukan keadaan implementasi sampai commit `4eec549` (`Record H6 track C VM verification`) pada 9 September 2026. File ini sendiri ditambahkan setelah batas tersebut. Sumber ringkas utama proyek tetap berada di [README proyek](../../README.md).

## 1. Ringkasan status

| Tahap | Yang sudah selesai | Bukti utama | Status |
|---|---|---|---|
| H1 | Inventaris sumber dan cakupan 35 indikator | 29 variabel WebAPI, 2 PDF, 27.826 sel | Selesai |
| H2 | Pilot perbandingan dua kanal | 19 sel beririsan; 16 sama, 3 berbeda | Selesai |
| H3 | Perbandingan nasional–provinsi dan antarrilis | 1.435 pasangan utama dan 4.608 kunci antarrilis | Selesai; stack VM sehat |
| H4 | Ingestion ber-manifest dan klasifikasi bersama | 7.666 observasi, 123 kejadian | Selesai; G1 masih menunggu H5 |
| H5 | Konfirmasi jejak revisi dan keputusan Gate G1 | 96/123 sebab inti terkonfirmasi | **Gate G1 lolos** |
| H6 Jalur A | Skema vintage eksplisit | 3 vintage, 38 observasi, 14 sel | Selesai dan diuji di Iceberg VM |
| H6 Jalur B | Skor sumber untuk perlakuan B2 | 3 sumber dinilai, 14 pilihan dipratinjau | Selesai dan dibekukan |
| H6 Jalur C | Lineage tingkat sel | 101 node, 235 edge, 38 path | Selesai dan divalidasi |
| H7 Jalur A | Perlakuan B0, overwrite | 38 masukan menjadi 14 current | Selesai dan diuji di Iceberg VM |
| H7 Jalur B | Perlakuan B2, single source | 14 dipilih, 24 dibuang | Selesai dan diuji di Iceberg VM |

Yang **belum** dikerjakan pada batas audit ini adalah H7 Jalur C, B1, harness revisi tersuntik, B3, penutupan lineage sampai metrik/tabel, pembekuan eksperimen H10, dan eksperimen H11–H15. Dengan demikian, Gate G2 belum boleh dinyatakan lolos. Perlakuan yang baru berjalan adalah B0 dan B2, yaitu 2 dari 4 perlakuan yang direncanakan.

## 2. Cara memahami bukti di repositori

Ada empat jenis berkas yang perlu dibedakan:

1. `config/` dan `contracts/` berisi keputusan atau aturan yang menjadi masukan. Perubahan manusia seharusnya dilakukan di sini.
2. `scripts/` dan `src/` berisi cara kerja pipeline.
3. `results/processed/` berisi keluaran yang dibentuk pipeline. Jangan mengoreksi angka langsung di CSV keluaran karena akan hilang saat pipeline dijalankan ulang.
4. `data/manifests/` mencatat input, output, jumlah baris, checksum SHA-256, versi kontrak, dan target tabel. Manifest adalah penghubung utama untuk membuktikan bahwa keluaran berasal dari input tertentu.

Data mentah WebAPI dan PDF berada di `data/raw/` dan sengaja tidak dimasukkan ke Git. Data itu dapat ditarik ulang dari manifest, tetapi penarikan WebAPI memerlukan kunci API BPS di `.env`. Kunci tidak pernah dicatat utuh; manifest hanya menyimpan fingerprint pendek. Akibat kebijakan ini, satu pengujian PDF di VM dilewati ketika PDF mentah tidak tersedia.

Istilah yang dipakai dalam dokumen ini:

- **observed**: ada bukti langsung yang cukup untuk menyatakan penyebab;
- **candidate**: gejalanya cocok, tetapi bukti belum cukup untuk mengunci penyebab;
- **vintage**: keadaan data pada rilis atau tanggal snapshot tertentu;
- **sel stabil**: identitas indikator, seri, periode observasi, level geografi, dan kode geografi yang tetap sama lintas rilis;
- **marker VM**: satu baris ringkas dari script integrasi yang hanya dicetak setelah pemeriksaan wajib lulus.

## 3. Jalur eksekusi Git dan VM

Pekerjaan dilakukan melalui jalur berikut:

```text
ubah dan uji di repositori lokal
        ↓
commit ke branch main
        ↓
push ke origin
        ↓
VM sigerciv@34.128.67.92 menarik commit dengan git pull --ff-only
        ↓
pipeline/test/integrasi dijalankan di /home/sigerciv/DSIC-SDG
        ↓
bukti marker dicatat kembali dalam dokumentasi/manifest, lalu commit dan push
```

Repo di VM menggunakan SSH untuk origin. Pull selalu memakai `--ff-only` agar VM tidak membuat merge commit diam-diam. Tahap yang mempunyai marker VM eksplisit adalah H5, H6A, H6B, H6C, H7A, dan H7B. H3 mempunyai bukti kesehatan stack. Tidak ada marker VM khusus H1 atau H2, sehingga keduanya jangan disebut sudah diverifikasi terpisah di VM.

Stack yang sudah dinaikkan dan diperiksa di VM:

- MinIO `2024-06-13` dan MinIO Client `2024-06-12`;
- Iceberg REST `1.8.1`;
- Spark `3.5.5` dengan Iceberg `1.8.1`;
- Jupyter/Spark endpoint.

Pemeriksaan H3 memastikan health endpoint MinIO, Iceberg REST, dan Jupyter merespons, lalu Spark berhasil menjalankan `SHOW NAMESPACES IN kkciv`. Port layanan hanya diikat ke localhost VM. Trino, OpenMetadata, dan Airflow belum dipasang karena belum dibutuhkan untuk gate yang sudah dijalankan.

VM yang tersedia bernama `praktikum-sd` dan pada pemeriksaan mempunyai 2 vCPU, RAM sekitar 7,7 GiB, serta disk 19 GiB. Angka ini lebih kecil daripada rancangan eksperimen 8 vCPU, 16 GB RAM, dan 256 GB. Karena itu seluruh eksekusi sampai dokumen ini adalah bukti **kebenaran fungsi**, bukan bukti performa atau skalabilitas.

## 4. H1 — Inventaris sumber dan cakupan indikator

### Tujuan

Membuktikan kanal gratis BPS mana yang benar-benar menyediakan data untuk lima domain: pendidikan, lingkungan, energi, ekonomi, dan ekologi.

### Langkah yang dieksekusi

1. Membuat registry kanal di [config/sources/bps_sources.csv](../../config/sources/bps_sources.csv) dan daftar indikator per domain di [config/indicators/](../../config/indicators/).
2. Menarik katalog variabel WebAPI domain pusat `0000`. Katalog berisi 1.753 variabel.
3. Mencocokkan istilah indikator dengan katalog. Pencarian awal menghasilkan 175 kandidat.
4. Menyaring kandidat secara manual menjadi 29 variabel di [free_webapi_selection.csv](../../config/sources/free_webapi_selection.csv).
5. Menarik data sejak 2015. Downloader membatasi paling banyak tiga ID periode `th` per request agar sesuai perilaku API.
6. Mengunduh dua PDF resmi TPB, edisi 2024 dan 2025, melalui katalog publikasi gratis. Locator disimpan di [free_publication_selection.csv](../../config/sources/free_publication_selection.csv).
7. Mengukur level geografi, rentang tahun, tahun yang hilang, kepadatan sel, dan `last_update` setiap variabel.
8. Menuliskan hasil cakupan ke inventaris indikator lalu menjalankan validasi.

Perintah yang digunakan:

```bash
make h1-discover-webapi
make h1-fetch-free-webapi
make h1-fetch-free-publications
make h1-apply-coverage
make h1-summary
make test
```

`make h1-apply-coverage` sudah mencakup profiling, penerapan status, dan validasi akhir.

### Hasil

- 29 variabel WebAPI terpilih;
- 240 ID periode sejak 2015;
- 27.826 sel data;
- 35 indikator dinilai: 14 `verified`, 17 `partial`, 4 `unavailable`, dan 0 `proposal_only`.

Empat indikator dinyatakan tidak tersedia karena proksi yang ditemukan tidak mempunyai arti yang sama:

- angka putus sekolah tidak menggantikan indikator anak tidak sekolah;
- akses air layak tidak menggantikan rincian sumber air;
- proksi HCV tidak menggantikan proporsi kawasan penting keanekaragaman hayati yang dilindungi;
- jumlah KPH maju tidak menggantikan indikator pengelolaan hutan lestari global.

Keputusan lain yang perlu diperiksa manusia: kanal BPS dipisahkan dari instansi produsen; air `layak` tidak otomatis berarti `aman`; rasio elektrifikasi ESDM tidak sama dengan pemakaian listrik rumah tangga; dan tutupan hutan memerlukan denominator serta pemetaan kategori yang sama sebelum dibandingkan.

### Bukti yang dapat diaudit

- [manifest katalog WebAPI](../../data/manifests/h1-webapi-variable-catalog.json)
- [manifest data WebAPI](../../data/manifests/h1-free-webapi-data.json)
- [manifest publikasi](../../data/manifests/h1-free-publications.json)
- [cakupan WebAPI](../../results/processed/h1-webapi-coverage.csv)
- [keputusan cakupan indikator](../../results/processed/h1-indicator-coverage.csv)
- [laporan audit H1](../../docs/research/h1-data-audit.md)

Commit jangkar: `5c41c89` dan `3d9d123`.

### Yang harus dikoreksi manusia bila perlu

Periksa istilah pencarian, pilihan 29 `var_id`, kesetaraan konsep, alasan empat penolakan proksi, serta apakah suatu indikator pantas berstatus `verified` atau hanya `partial`. H1 hanya membuktikan cakupan dan locator; H1 belum membuktikan adanya revisi nilai dan belum meloloskan G1.

## 5. H2 — Pilot perbandingan dua kanal

### Tujuan

Menguji apakah satu sel dapat dinormalisasi dan dibandingkan secara adil antara snapshot WebAPI 8 September 2026 dan publikasi TPB 2024 bertanggal 31 Desember 2024.

### Langkah yang dieksekusi

1. Memilih satu kandidat dari setiap domain.
2. Menyamakan kunci perbandingan: indikator, seri, periode observasi, level dan kode geografi, serta unit.
3. Menyalin 25 angka publikasi yang sudah diperiksa visual ke referensi pilot.
4. Menormalisasi nilai WebAPI dan publikasi ke struktur yang sama.
5. Membandingkan hanya sel dengan konsep, periode, geografi, dan unit yang benar-benar sepadan.
6. Menahan tutupan hutan karena unit dan definisinya tidak sepadan.

Perintah:

```bash
make h2-run
make test
```

### Hasil

Empat indikator dapat dibandingkan:

- penyelesaian pendidikan;
- fasilitas cuci tangan;
- bauran energi terbarukan;
- upah per jam.

Pipeline menghasilkan 19 baris WebAPI, 20 baris publikasi, 39 baris ternormalisasi, 20 baris evaluasi sel, 4 baris perbedaan/missing, dan 5 baris ringkasan indikator. Pada 19 sel yang beririsan, 16 sama dan 3 berbeda. Satu sel energi 2023 hanya tersedia pada publikasi.

Tiga nilai bauran energi terbarukan yang berbeda:

| Tahun | WebAPI | TPB 2024 |
|---|---:|---:|
| 2018 | 9,00 | 8,60 |
| 2019 | 9,15 | 9,19 |
| 2020 | 11,20 | 11,27 |

Perbedaan ini sengaja dibiarkan belum terklasifikasi pada H2. Dua angka berbeda belum cukup untuk membuktikan mana yang direvisi atau mengapa berbeda.

### Bukti yang dapat diaudit

- [konfigurasi indikator pilot](../../config/h2/pilot_indicators.csv)
- [konfigurasi seri pilot](../../config/h2/pilot_series.csv)
- [hasil perbandingan sel](../../results/processed/h2-cell-comparison.csv)
- [ringkasan indikator](../../results/processed/h2-indicator-summary.csv)
- [manifest normalisasi](../../data/manifests/h2-normalization.json)
- [laporan H2](../../docs/research/h2-source-comparison.md)

Commit jangkar: `4406666`.

### Yang harus dikoreksi manusia bila perlu

Periksa ulang 25 angka terhadap gambar/tabel PDF, terutama posisi kolom dan catatan kaki. Pastikan tutupan hutan memang harus ditahan. H2 baru menemukan perbedaan pada satu domain, sehingga G1 belum lolos pada tahap ini.

## 6. H3 — Perbandingan nasional–provinsi dan antarrilis

### Tujuan

Memperbesar pilot menjadi beban yang cukup untuk membuktikan bahwa ketidaksesuaian muncul di beberapa domain, serta menyiapkan stack penyimpanan penelitian.

### Langkah yang dieksekusi

1. Mengekstrak 14 halaman lampiran PDF dengan `pdftotext -layout`.
2. Menangani watermark diagonal, superscript catatan kaki, tanda pisah, dan elipsis sebagai bentuk missing yang eksplisit.
3. Memaksa setiap halaman mempunyai tepat 39 baris wilayah dan jumlah kolom yang diharapkan. Pipeline berhenti jika struktur bergeser.
4. Memeriksa silang 13 angka nasional hasil ekstraksi otomatis dengan referensi manual; seluruh 13 sama.
5. Membandingkan 10 indikator sepadan pada tingkat nasional dan provinsi.
6. Membandingkan rilis TPB 2024, TPB 2025, dan snapshot WebAPI untuk melihat perubahan antarrilis.
7. Memeriksa apakah nilai nasional berada di dalam rentang provinsi dan apakah nilai nasional sekadar rata-rata provinsi tanpa bobot.
8. Menaikkan stack MinIO, Iceberg REST, dan Spark/Jupyter di VM serta memeriksa health endpoint dan akses katalog.

Perintah data dan pengujian:

```bash
make h3-run
make h3-releases
make test
```

Perintah stack yang sudah digunakan sesuai kebutuhan lokal/VM:

```bash
make stack-up
make stack-freeze
make stack-down
make stack-remote-up
make stack-remote-status
make stack-remote-verify
make stack-remote-freeze
make stack-remote-down
```

### Hasil audit utama

- 1.435 sel WebAPI dan 1.435 sel publikasi dibandingkan;
- 1.402 sama dan 33 berbeda;
- 19 perbedaan hanya digit terakhir/presentasi;
- 14 perbedaan menjadi kandidat revisi;
- perbedaan terbesar yang terlihat antara lain Maluku Utara 2023 sebesar `+0,99`;
- pada Maluku 2021 ditemukan perbedaan tanda `-0,18` versus `0,38`.

Sebanyak 82 dari 82 nilai nasional berada dalam rentang nilai provinsi. Tidak satu pun sama dengan rata-rata provinsi tanpa bobot. Artinya nilai nasional tidak boleh dihitung ulang dengan rata-rata sederhana provinsi; ini bukti masalah granularitas, bukan revisi nilai.

Tahun cetak seri NEET pernah tampak bergeser. Konfigurasi dipertahankan mengikuti tahun yang benar-benar tercetak. Jika koreksi ini tidak diterapkan, pipeline akan menghasilkan 140 perbedaan palsu.

### Hasil tambahan antarrilis

- 4.591 observasi WebAPI dan 205 observasi publikasi, total 4.796;
- 4.608 kunci sel;
- 156 kunci mempunyai lebih dari satu rilis: 148 sama dan 8 berbeda;
- 4.452 kunci hanya ada pada satu sumber/rilis;
- 8 perbedaan muncul di tiga domain: energi 5, ekonomi 2, ekologi 1;
- 4 perubahan terlihat langsung antara publikasi 2024 dan 2025.

Dengan hasil ini, kriteria G1 tentang perbedaan pada minimal tiga domain sudah terpenuhi, tetapi penyebabnya masih harus diuji H4–H5.

### Bukti yang dapat diaudit

- [perbandingan sel utama](../../results/processed/h3-cell-comparison.csv)
- [daftar perbedaan utama](../../results/processed/h3-discrepancies.csv)
- [audit granularitas](../../results/processed/h3-granularity.csv)
- [perbandingan sel antarrilis](../../results/processed/h3-release-cell-comparison.csv)
- [perbedaan antarrilis](../../results/processed/h3-release-discrepancies.csv)
- [manifest audit utama](../../data/manifests/h3-comparison.json)
- [manifest audit antarrilis](../../data/manifests/h3-release-reconciliation.json)
- [laporan H3](../../docs/research/h3-national-province-comparison.md)
- [versi dan digest stack](../../infra/docker/)

Commit jangkar: `6a63179`.

### Yang harus dikoreksi manusia bila perlu

Pemeriksaan paling penting adalah 14 halaman PDF, 13 angka kontrol, penanganan catatan kaki/missing, dan keputusan pergeseran tahun NEET. Audit juga harus membedakan perbedaan digit akhir, perubahan nilai, perbedaan metodologi, dan agregasi nasional. Stack H3 membuktikan layanan berjalan, belum membuktikan kemampuan tulis tabel Iceberg; uji tulis-baca baru dilakukan di H5.

## 7. H4 — Ingestion ber-manifest dan klasifikasi

### Tujuan

Memasukkan seluruh keluaran H3 secara deterministik, memeriksa integritasnya, dan menerapkan aturan penyebab yang sama untuk semua domain.

### Langkah yang dieksekusi

1. Membaca hanya keluaran H3 yang path, checksum, dan jumlah barisnya cocok dengan manifest.
2. Memeriksa kolom wajib, domain, nilai numerik hingga, dan duplikasi.
3. Menggabungkan 1.435 observasi WebAPI, 1.435 observasi TPB audit utama, serta 4.796 observasi audit antarrilis menjadi 7.666 observasi.
4. Membentuk batch deterministik `h4-2981e0fb3bc2d960`.
5. Menerapkan delapan aturan di [classification_rules.csv](../../config/h4/classification_rules.csv).
6. Membuat event klasifikasi dan ringkasan Gate G1 sementara.
7. Mempublikasikan empat CSV dan satu manifest ke MinIO pada prefix `s3://kkciv-warehouse/ingest/h4/h4-2981e0fb3bc2d960/`.
8. Membaca kembali kelima objek dan membandingkan checksum SHA-256.

Perintah:

```bash
make h4-run
make test
make h4-publish
```

### Hasil

Ada 123 kejadian yang diklasifikasikan:

- 82 granularitas teramati;
- 19 pembulatan/presentasi teramati;
- 3 vintage teramati pada H4;
- 17 kandidat vintage;
- 2 kandidat metodologi atau metodologi/unit.

Jika kandidat ikut dihitung, 104/123 atau 84,55% masuk keluarga penyebab inti. Namun yang benar-benar terkonfirmasi saat H4 baru 85/123 atau 69,11%, masih di bawah ambang 70%. Karena itu keputusan yang benar pada H4 adalah `pending_H5`, bukan `passed`.

### Bukti yang dapat diaudit

- [aturan klasifikasi](../../config/h4/classification_rules.csv)
- [observasi hasil ingestion](../../results/processed/h4-ingested-observations.csv)
- [123 event terklasifikasi](../../results/processed/h4-classified-events.csv)
- [ringkasan klasifikasi](../../results/processed/h4-classification-summary.csv)
- [manifest H4](../../data/manifests/h4-ingestion-classification.json)
- [laporan H4](../../docs/research/h4-classification-and-ingestion.md)

Commit jangkar: `4d006a8`, `07056b3`, `97576df`, dan `a069924`.

### Yang harus dikoreksi manusia bila perlu

Periksa delapan aturan satu per satu, terutama event berlabel `candidate`. Kandidat bukan fakta dan tidak boleh dihitung sebagai penyebab terkonfirmasi. Periksa pula bahwa lima objek di MinIO sesuai manifest, bukan hanya ada dengan nama yang benar.

## 8. H5 — Konfirmasi jejak revisi dan penutupan Gate G1

### Tujuan

Mencari bukti bertanggal yang cukup untuk menaikkan kandidat menjadi observed, membekukan jejak antarrilis, dan membuat keputusan G1 yang dapat diulang.

### Langkah yang dieksekusi

1. Membaca 123 event H4 beserta manifest sumber.
2. Menerapkan 11 keputusan bukti eksplisit di [evidence_decisions.csv](../../config/h5/evidence_decisions.csv).
3. Hanya mempromosikan kandidat jika ada urutan rilis/snapshot bertanggal dan bukti yang menjelaskan perubahan.
4. Mengonfirmasi 10 sel produktivitas: TPB 2024 memberi tanda sementara/sangat sementara, TPB 2025 mempertahankan jejaknya, lalu WebAPI 2026 mempunyai nilai berubah.
5. Mengonfirmasi satu event tutupan hutan sebagai perbedaan metodologi.
6. Menahan delapan kandidat lain karena bukti belum cukup.
7. Membentuk 14 jejak revisi dengan total 38 baris vintage.
8. Menulis 38 baris ke `kkciv.gate1.h5_revision_trace` dengan `INSERT OVERWRITE`, membacanya kembali, lalu memeriksa file data fisik.

Perintah:

```bash
make h5-run
make test
make h5-iceberg
```

### Hasil dan keputusan Gate G1

| Kriteria | Hasil | Ambang | Keputusan |
|---|---:|---:|---|
| G1.1 domain yang mempunyai perbedaan | 3 | 3 | Lolos |
| G1.2 sebab inti terkonfirmasi | 96/123 = 78,05% | 70% | Lolos |
| G1.3 jejak revisi antarrilis | 4 langsung; 14 jejak beku | minimal 1 | Lolos |

**Gate G1 resmi lolos di H5.** Batch H5 adalah `h5-4439733db96507a1`.

Empat jejak mempunyai dua vintage dan sepuluh jejak mempunyai tiga vintage. Delapan kandidat tidak dipromosikan: empat produktivitas 2021 tidak memiliki penanda sementara, tiga energi 2018–2020 hanya mempunyai satu snapshot WebAPI lawan satu publikasi, dan satu intensitas energi masih kabur antara masalah metode dan unit.

Marker VM:

```text
H5_VERIFY|38|14|1|3|1
```

Artinya: 38 baris terbaca, 14 jejak, urutan vintage minimum 1 dan maksimum 3, serta satu data file Iceberg.

### Bukti yang dapat diaudit

- [11 keputusan bukti](../../config/h5/evidence_decisions.csv)
- [123 event setelah konfirmasi](../../results/processed/h5-confirmed-events.csv)
- [38 baris jejak revisi](../../results/processed/h5-revision-traces.csv)
- [ringkasan Gate G1](../../results/processed/h5-gate-g1-summary.csv)
- [manifest H5](../../data/manifests/h5-gate1.json)
- [laporan H5](../../docs/research/h5-revision-trace-and-gate1.md)

Commit jangkar: `81f1f7a`, `89a9bd4`, dan `18c0753`.

### Yang harus dikoreksi manusia bila perlu

Audit utama H5 adalah 11 keputusan bukti dan alasan delapan kandidat yang tetap ditahan. Sebagian jejak bersifat lintas kanal: publikasi lama dibandingkan dengan snapshot WebAPI yang baru, bukan histori snapshot WebAPI murni. Klaim harus tetap berbunyi “jejak lintas rilis/kanal yang teramati”, bukan “log revisi internal BPS”.

## 9. H6 Jalur A — Skema dengan vintage eksplisit

### Tujuan

Mengubah 38 baris H5 menjadi model data yang menyimpan identitas sel stabil dan vintage sebagai dua hal terpisah.

### Langkah yang dieksekusi

1. Menetapkan kontrak [h6-vintage-schema.json](../../contracts/h6-vintage-schema.json).
2. Mendefinisikan tabel Iceberg melalui [h6-vintage-schema.sql](../../infra/spark/h6-vintage-schema.sql).
3. Membentuk `cell_id` dari indikator, seri, periode observasi, level geografi, dan kode geografi.
4. Membentuk `vintage_id` dari sumber, tanggal vintage, dan checksum manifest.
5. Membentuk `observation_id` dari sel, vintage, dan rekaman sumber.
6. Menyimpan nilai sebagai `DECIMAL(38,10)` serta mempertahankan `value_lexeme` dan jumlah desimal agar tampilan asli tidak hilang.
7. Menyimpan kolom provenance: path dan hash artefak, rekaman sumber, batch, run, versi transformasi, dan trace.
8. Menjalankan enam invariant serta pemeriksaan proyeksi tanpa kehilangan baris.
9. Membuat dan membaca ulang dua tabel Iceberg di VM.

Perintah:

```bash
make h6-run
make test
make h6-apply
```

### Hasil

- `kkciv.research.release_vintages`: 3 baris vintage;
- `kkciv.research.indicator_observations`: 38 observasi;
- 14 `cell_id` stabil;
- setiap sel memiliki 2–3 vintage;
- tidak ada orphan dan tidak ada ketidakcocokan nilai numerik;
- tabel observasi dipartisi berdasarkan domain;
- status current dihitung dari urutan vintage, tidak disimpan sebagai flag yang mudah basi.

`cell_id` sengaja tidak memasukkan sumber, vintage, nilai, unit, atau metode. Ini membuat sel yang sama dapat dilacak lintas rilis, tetapi juga merupakan keputusan desain yang harus disetujui manusia.

Marker VM:

```text
H6_VERIFY|3|38|14|2|3|1|3|0|0
```

Artinya: 3 vintage, 38 observasi, 14 sel, 2–3 vintage per sel, 1 data file tabel vintage, 3 data file tabel observasi, 0 orphan, dan 0 mismatch numerik.

### Bukti yang dapat diaudit

- [kontrak skema](../../contracts/h6-vintage-schema.json)
- [DDL Iceberg](../../infra/spark/h6-vintage-schema.sql)
- [dimensi vintage](../../results/processed/h6-release-vintages.csv)
- [fakta observasi](../../results/processed/h6-indicator-observations.csv)
- [hasil enam invariant](../../results/processed/h6-schema-validation.csv)
- [manifest H6A](../../data/manifests/h6-vintage-schema.json)
- [laporan H6A](../../docs/research/h6-explicit-vintage-schema.md)

Commit jangkar: `e0c8aca`, `c8d550c`, dan `dd62e4a`.

### Yang harus dikoreksi manusia bila perlu

Putuskan apakah komponen identitas `cell_id` sudah cukup stabil dan apakah unit/metode memang boleh tetap di tingkat observasi. Beban saat ini sangat kecil; partisi hanya berdasarkan domain belum membuktikan desain partisi terbaik untuk beban besar.

## 10. H6 Jalur B — Skor kepercayaan sumber untuk B2

### Tujuan

Membekukan aturan pemilihan satu sumber untuk perlakuan B2 sebelum hasil konflik dipakai. Skor ini mengukur kecocokan sumber untuk workload, bukan menentukan “sumber yang benar”.

### Langkah yang dieksekusi

1. Menetapkan kontrak [h6b-source-trust.json](../../contracts/h6b-source-trust.json).
2. Menyaring sumber yang aktif, gratis, terverifikasi, dan mempunyai peran yang sesuai.
3. Menghitung lima dimensi dengan bobot tetap:

   | Dimensi | Bobot |
   |---|---:|
   | otoritas resmi | 0,30 |
   | provenance ber-manifest | 0,20 |
   | konteks semantik | 0,20 |
   | keterstrukturan langsung | 0,15 |
   | cakupan sel workload | 0,15 |

4. Melarang nilai observasi, tingkat kesepakatan, hasil konflik, dan dugaan pemenang masuk ke rumus skor.
5. Mengurutkan skor; jika sama, gunakan tanggal vintage, lalu ID sumber dan ID observasi sebagai tie-break deterministik.
6. Membuat preview pilihan untuk 14 sel tanpa mengubah lagi skor setelah melihat konflik.

Perintah:

```bash
make h6b-run
make test
```

### Hasil

| Peringkat | Sumber | Skor |
|---:|---|---:|
| 1 | TPB 2025 | 0,962500 |
| 2 | TPB 2024 | 0,962500 |
| 3 | WebAPI 2026 | 0,907143 |

TPB 2025 menang atas TPB 2024 karena tanggal rilis, bukan karena skornya lebih tinggi. Preview memilih TPB 2025 untuk seluruh 14 sel. Hanya 4 pilihan yang juga merupakan vintage terbaru; 10 pilihan lebih lama daripada WebAPI dan nilainya berbeda dari latest-vintage.

Marker VM:

```text
H6B_VERIFY|3|14|4|10|10|frozen
```

Artinya: 3 sumber dinilai, 14 sel dipilih, 4 pilihan latest, 10 pilihan lebih lama, 10 berbeda dari latest, dan kontrak sudah dibekukan.

### Bukti yang dapat diaudit

- [kontrak skor](../../contracts/h6b-source-trust.json)
- [skor tiga sumber](../../results/processed/h6b-source-trust-scores.csv)
- [preview pilihan 14 sel](../../results/processed/h6b-selection-preview.csv)
- [validasi skor](../../results/processed/h6b-source-trust-validation.csv)
- [manifest H6B](../../data/manifests/h6b-source-trust.json)
- [laporan H6B](../../docs/research/h6b-source-trust-score.md)

Commit jangkar: `bc6fd31` dan `c0d0042`.

### Yang harus dikoreksi manusia bila perlu

Bobot merupakan keputusan penelitian yang dipraregistrasikan, bukan hasil pembelajaran data. Audit harus menilai apakah bobot dan tie-break masuk akal. Hasil ini hanya berlaku pada tiga instance sumber dan 14 sel fixture; belum layak digeneralisasi menjadi peringkat mutu seluruh produk BPS. Analisis sensitivitas bobot masih dapat ditambahkan sebagai versi eksperimen baru.

## 11. H6 Jalur C — Lineage tingkat sel

### Tujuan

Membuktikan bahwa setiap angka H6 dapat ditelusuri kembali melalui artefak dan manifest yang tepat tanpa pencocokan samar.

### Langkah yang dieksekusi

1. Menetapkan kontrak [h6c-cell-lineage.json](../../contracts/h6c-cell-lineage.json).
2. Membentuk graf dengan 9 jenis node dan 9 jenis relasi.
3. Membentuk jalur inti `manifest → artifact → source_record → observation → indicator_cell`.
4. Menambahkan cabang konteks vintage, batch, run, dan versi transformasi.
5. Menguji keunikan ID node/edge, kelengkapan path, resolusi rekaman sumber, dan keterjangkauan setiap sel.
6. Mengungkap benturan locator PDF apa adanya dan menyelesaikan identitas rekaman dengan kunci eksplisit.

Perintah:

```bash
make h6c-run
make test
```

### Hasil

- 101 node;
- 235 edge;
- 38 core path untuk 38 observasi;
- 14 sel, masing-masing mempunyai 2–3 path;
- kelengkapan `1,0000` pada fixture H6;
- tidak memakai fuzzy matching.

Audit menemukan empat locator PDF mentah dipakai ulang oleh 20 observasi provinsi. Locator tersebut hanya menyebut halaman/kolom/tahun dan tidak menyebut wilayah. Masalah ini tidak disembunyikan. Node `source_record` dibuat unik dengan gabungan checksum artefak, locator mentah, indikator, seri, periode, level geografi, dan kode geografi. Dengan cara ini semua 38 observasi tetap menunjuk satu rekaman sumber yang tepat.

Marker VM:

```text
H6C_VERIFY|101|235|38|14|4|20|1.0000|validated
```

Artinya: 101 node, 235 edge, 38 path, 14 sel, 4 locator bertabrakan yang memengaruhi 20 observasi, kelengkapan 1,0000, dan seluruh validasi lulus.

### Bukti yang dapat diaudit

- [kontrak lineage](../../contracts/h6c-cell-lineage.json)
- [node lineage](../../results/processed/h6c-lineage-nodes.csv)
- [edge lineage](../../results/processed/h6c-lineage-edges.csv)
- [path sel ke sumber](../../results/processed/h6c-cell-source-paths.csv)
- [hasil validasi](../../results/processed/h6c-lineage-validation.csv)
- [manifest H6C](../../data/manifests/h6c-cell-lineage.json)
- [laporan H6C](../../docs/research/h6c-cell-lineage.md)

Commit jangkar: `3211bb6` dan `4eec549`.

### Yang harus dikoreksi manusia bila perlu

Periksa apakah identitas komposit benar-benar cukup untuk locator yang bertabrakan. Angka kelengkapan 1,0000 hanya berlaku pada 38 observasi fixture H6, bukan seluruh 7.666 observasi H4. Node untuk keluaran metrik, tabel, dan gambar belum dibangun; pekerjaan itu berada pada H7C–H9C.

## 12. H7 Jalur A — Perlakuan B0 overwrite

### Tujuan

Membuat kontrol negatif B0: hanya satu keadaan terbaru per sel yang dipertahankan, sedangkan histori sengaja tidak dapat dipanggil ulang.

### Langkah yang dieksekusi

1. Menetapkan kontrak [h7-b0-overwrite.json](../../contracts/h7-b0-overwrite.json) dan DDL [h7-b0.sql](../../infra/spark/h7-b0.sql).
2. Mengurutkan tiga batch secara kronologis: TPB 2024, TPB 2025, lalu WebAPI 2026.
3. Menerapkan setiap batch ke `kkciv.experiments.b0_indicator_current` dengan tepat satu baris per `cell_id`.
4. Mencatat apakah overwrite mengubah nilai atau hanya mengganti provenance dengan nilai numerik yang sama.
5. Menguji ulang seluruh 38 alamat observasi/vintage.
6. Menghapus snapshot Iceberg lama dan menyisakan satu snapshot terbaru agar time travel tidak secara tidak sengaja mengubah B0 menjadi perlakuan multiversi.
7. Membaca state dan metadata Iceberg kembali dari VM.

Perintah:

```bash
make h7-run
make test
make h7-apply
```

### Hasil

| Batch | Baris masuk | Keadaan akhir | Perubahan |
|---|---:|---:|---|
| TPB 2024 | 14 | 14 | 14 insert awal |
| TPB 2025 | 14 | 14 | 4 nilai berubah, 10 sama |
| WebAPI 2026 | 10 | 14 | 10 nilai berubah |

Secara total 38 observasi menjadi 14 baris current. Sebanyak 24 alamat lama hilang dari state: 14 overwrite mengubah nilai dan 10 overwrite mengganti baris dengan nilai yang sama. Audit baca ulang berhasil untuk 14 observasi current dan gagal untuk 24 observasi historis, sehingga tingkat keberhasilan `14/38 = 0,3684`.

Nilai `0,3684` adalah hasil negatif untuk pertanyaan reproducibility, bukan angka performa. Kolom `replaced_observation_id` hanya memberi petunjuk ID yang pernah diganti; kolom itu tidak menyimpan kembali nilai lama.

Marker VM:

```text
H7_VERIFY|14|14|14|24|1|3|0|0|0
```

Artinya: 14 baris, 14 sel, 14 baca sukses, 24 gagal, 1 snapshot, 3 data file, 0 duplikasi, 0 state mismatch, dan 0 audit mismatch.

### Masalah integrasi yang benar-benar ditemukan dan diperbaiki

1. Script awal menyembunyikan error Spark SQL di dalam command substitution. Commit `64e3945` memperlihatkan exit status dan output sebenarnya.
2. Parser prosedur Iceberg menolak `current_timestamp()` pada `CALL expire_snapshots`. Commit `55baa45` menggantinya dengan literal `TIMESTAMP` masa depan yang valid untuk eksperimen ini.
3. Query verifikasi mempunyai error alias scalar di bagian `audit_mismatches`. Commit `010f6c6` memperbaiki sintaksnya.

### Bukti yang dapat diaudit

- [kontrak B0](../../contracts/h7-b0-overwrite.json)
- [DDL B0](../../infra/spark/h7-b0.sql)
- [operasi tiga batch](../../results/processed/h7-b0-operations.csv)
- [state akhir 14 sel](../../results/processed/h7-b0-final-state.csv)
- [audit 38 alamat](../../results/processed/h7-b0-reproducibility.csv)
- [ringkasan B0](../../results/processed/h7-b0-summary.csv)
- [manifest B0](../../data/manifests/h7-b0-overwrite.json)
- [laporan H7A](../../docs/research/h7-b0-overwrite.md)

Commit jangkar: `ec2a7bb`, `64e3945`, `55baa45`, `010f6c6`, dan `617af5d`.

### Yang harus dikoreksi manusia bila perlu

Pastikan penghapusan snapshot memang bagian yang disetujui dari definisi B0. Tindakan ini sengaja destruktif terhadap histori tabel eksperimen B0, tetapi tidak menghapus fixture H6. Jangan menilai B0 buruk karena lambat/cepat—belum ada pengukuran waktu—melainkan karena 24 observasi lama tidak dapat direproduksi.

## 13. H7 Jalur B — Perlakuan B2 single source

### Tujuan

Mewujudkan keputusan skor H6B menjadi state satu sumber, lalu mengukur konsekuensinya terhadap pemanggilan ulang semua kandidat.

### Langkah yang dieksekusi

1. Menetapkan kontrak [h7b-b2-single-source.json](../../contracts/h7b-b2-single-source.json) dan DDL [h7b-b2.sql](../../infra/spark/h7b-b2.sql).
2. Membaca 38 observasi H6 dan keputusan skor H6B yang sudah dibekukan.
3. Memilih tepat satu observasi per sel tanpa menghitung ulang skor setelah konflik diketahui.
4. Menulis 14 pilihan ke `kkciv.experiments.b2_indicator_selected`.
5. Menyimpan 24 kandidat yang tidak terpilih sebagai artefak audit CSV, bukan sebagai baris serving table.
6. Menguji ulang alamat 14 pilihan dan 24 kandidat yang dibuang.
7. Menghapus snapshot lama dan menyisakan satu snapshot agar B2 benar-benar merepresentasikan single-source state.
8. Menjalankan apply dua kali; state dan marker identik, sehingga proses terbukti idempoten pada fixture ini.

Perintah:

```bash
make h7b-run
make test
make h7b-apply
```

### Hasil

- 38 kandidat menjadi 14 observasi TPB 2025;
- 24 kandidat dibuang: 10 WebAPI karena skor lebih rendah dan 14 TPB 2024 karena tie-break tanggal;
- hanya 4 pilihan merupakan vintage paling baru;
- 10 pilihan lebih tua daripada WebAPI;
- nilai 10 pilihan tersebut berbeda dari jawaban latest-vintage/B0;
- audit baca ulang berhasil pada 14 pilihan dan gagal pada 24 kandidat yang dibuang;
- tingkat keberhasilan sama-sama `0,3684`, tetapi alasan kegagalan B2 berbeda dari B0.

B2 tidak menyatakan TPB 2025 sebagai kebenaran. Ia hanya menjalankan kebijakan “pilih sumber dengan skor tertinggi” yang sudah dibekukan.

Marker VM:

```text
H7B_VERIFY|14|14|1|10|14|24|1|3|0|0|0
```

Artinya: 14 baris, 14 sel, 1 sumber terpilih, 10 pilihan non-latest, 14 baca sukses, 24 gagal, 1 snapshot, 3 data file, 0 duplikasi, 0 state mismatch, dan 0 audit mismatch.

### Bukti yang dapat diaudit

- [kontrak B2](../../contracts/h7b-b2-single-source.json)
- [DDL B2](../../infra/spark/h7b-b2.sql)
- [14 pilihan](../../results/processed/h7b-b2-selected-state.csv)
- [24 kandidat dibuang](../../results/processed/h7b-b2-discarded-candidates.csv)
- [audit 38 alamat](../../results/processed/h7b-b2-reproducibility.csv)
- [ringkasan B2](../../results/processed/h7b-b2-summary.csv)
- [validasi B2](../../results/processed/h7b-b2-validation.csv)
- [manifest B2](../../data/manifests/h7b-b2-single-source.json)
- [laporan H7B](../../docs/research/h7b-b2-single-source.md)

Commit jangkar: `93b2f2e` dan `d93cd3f`.

### Yang harus dikoreksi manusia bila perlu

Periksa alasan skor, tie-break, dan daftar 24 kandidat yang dibuang. B0 dan B2 sama-sama hanya dapat mengembalikan 14/38 alamat, tetapi state akhirnya berbeda pada 10 sel. Perbedaan itu penting dan harus tetap terlihat dalam eksperimen berikutnya.

## 14. Pemeriksaan akhir yang sudah lulus

Pada keadaan terakhir sebelum dokumen audit ini dibuat:

- seluruh 49 unit test lokal lulus;
- di VM, 48 test lulus dan 1 test dilewati karena PDF mentah tidak disimpan di Git;
- working tree VM bersih setelah pull dan verifikasi terakhir;
- H4 berhasil menulis dan membaca ulang objek MinIO dengan checksum sama;
- H5, H6A, H7A, dan H7B berhasil menulis serta membaca tabel Iceberg;
- H6B dan H6C menghasilkan artefak deterministik dan marker validasi di VM.

Urutan pemeriksaan cepat tanpa menarik ulang data mentah:

```bash
make h1-validate
make h1-summary
make h4-run
make h5-run
make h6-run
make h6b-run
make h6c-run
make h7-run
make h7b-run
make test
```

H2 dan H3 membutuhkan PDF mentah untuk ekstraksi penuh. H1 fetch membutuhkan jaringan dan API key. Perintah `*-apply`, `h5-iceberg`, dan `h4-publish` membutuhkan stack yang sedang hidup.

Untuk pemeriksaan VM saat ini:

```bash
ssh sigerciv@34.128.67.92
cd /home/sigerciv/DSIC-SDG
git status --short
git log -1 --oneline
docker compose --env-file infra/docker/versions.env ps
```

## 15. Daftar audit manusia yang disarankan

- [ ] Cocokkan 29 pilihan WebAPI H1 dengan definisi indikator, bukan hanya kemiripan nama.
- [ ] Setujui atau koreksi 14 `verified`, 17 `partial`, dan 4 `unavailable`.
- [ ] Periksa visual 25 angka referensi H2 terhadap PDF.
- [ ] Periksa 14 halaman lampiran H3, catatan kaki, missing, dan koreksi tahun NEET.
- [ ] Bedakan rounding, vintage, metodologi, dan granularitas pada 123 event H4.
- [ ] Nilai ulang 11 keputusan bukti H5 dan delapan kandidat yang tidak dipromosikan.
- [ ] Setujui komponen `cell_id`, `vintage_id`, tipe angka, dan partisi H6A.
- [ ] Tinjau bobot dan tie-break skor H6B; jangan memperlakukannya sebagai ukuran kebenaran.
- [ ] Periksa empat locator PDF H6C yang dipakai ulang oleh 20 observasi.
- [ ] Setujui penghapusan snapshot lama sebagai bagian definisi B0 dan B2.
- [ ] Bandingkan 10 sel yang berbeda antara hasil latest-vintage/B0 dan hasil B2.
- [ ] Putuskan spesifikasi VM sebelum pengukuran performa dimulai.

## 16. Cara melakukan koreksi tanpa merusak jejak audit

Jika audit manusia menemukan kesalahan:

1. jangan mengedit CSV di `results/processed/` secara langsung;
2. ubah sumber keputusan di `config/`, kontrak di `contracts/`, atau logika pipeline di `src/`/`scripts/`;
3. jika makna eksperimen berubah, naikkan versi kontrak atau buat versi eksperimen baru;
4. jalankan ulang tahap yang dikoreksi dan seluruh tahap turunannya;
5. pastikan manifest baru mempunyai checksum dan jumlah baris yang benar;
6. jalankan seluruh unit test;
7. commit dan push perubahan;
8. di VM, jalankan `git pull --ff-only origin main`, lalu ulangi validasi/integrasi yang terdampak;
9. catat alasan koreksi, angka sebelum/sesudah, serta marker VM baru.

Dengan prosedur tersebut, koreksi manusia menjadi bagian dari provenance penelitian dan tidak menghapus bukti keputusan sebelumnya dari riwayat Git.

## 17. Batas klaim pada posisi sekarang

Yang sudah dapat diklaim:

- sumber resmi BPS yang seharusnya sepadan memang dapat menghasilkan nilai berbeda;
- perbedaan teramati pada sedikitnya tiga domain;
- lebih dari 70% event sudah mempunyai sebab inti terkonfirmasi menurut aturan yang dibekukan;
- jejak vintage dapat disimpan, dibaca, dan dilacak sampai rekaman sumber;
- dua baseline, B0 dan B2, sudah berjalan pada workload 38 observasi/14 sel.

Yang belum dapat diklaim:

- bahwa satu sumber selalu paling benar;
- bahwa semua perbedaan adalah revisi;
- bahwa lineage sudah mencakup seluruh 7.666 observasi H4 atau sampai semua tabel/gambar;
- bahwa salah satu perlakuan lebih cepat, lebih hemat ruang, atau lebih skalabel;
- bahwa Gate G2 atau G3 sudah lolos;
- bahwa hasil 14 sel dapat digeneralisasi ke seluruh indikator BPS.

Posisi audit yang tepat adalah: **Gate G1 sudah ditutup dengan bukti; fondasi tiga jalur H6 selesai; B0 dan B2 selesai; eksperimen pembanding lengkap dan pengukuran utama belum dimulai.**
