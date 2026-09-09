# H3 - Perbandingan penuh nasional dan provinsi

Snapshot WebAPI utama: 8 September 2026. Publikasi pembanding: Indikator TPB Indonesia 2024,
rilis 31 Desember 2024. Tambahan antarrilis memakai snapshot WebAPI H3 tanggal 9 September 2026
serta publikasi TPB 2025. Seluruh input gratis; SIRuSa, DNA, dan Silastik/PST tidak dipakai.

## Keputusan H3

H3 memperluas perbandingan H2 dari 20 sel nasional menjadi **1.435 sel pada 41 sel nasional dan
1.394 sel provinsi**, mencakup sepuluh indikator di empat domain. Perluasan ini dimungkinkan oleh
temuan baru: publikasi TPB 2024 memuat **lampiran per provinsi** yang dapat diekstraksi mesin,
bukan hanya grafik nasional yang pada H2 harus ditranskripsi manual.

Hasilnya: 1.402 sel identik dan 33 sel berbeda. Perbedaan nilai antarsumber hanya muncul pada dua
domain, sedangkan ketidaksesuaian granularitas muncul pada keempat domain yang dapat dibandingkan.

## Cara lampiran publikasi diekstraksi

`pdftotext -layout` dipakai karena PDF-nya berbasis teks, bukan hasil pindaian. Tiga hal harus
ditangani sebelum angkanya dapat dipercaya.

1. **Watermark diagonal.** Tulisan `https://www.bps.go.id` disisipkan sebagai potongan pendek di
   antara kolom angka, dan pada beberapa baris ia memecah satu baris provinsi menjadi dua. Baris
   lanjutan disambung kembali ke provinsi terakhir.
2. **Penanda catatan kaki superskrip.** Superskrip menempel pada angka, sehingga `0,12` dengan
   catatan kaki 1 terbaca sebagai `0,121`. Jumlah desimal modal per kolom dipakai untuk
   memisahkannya; penandanya disimpan pada `methodology_version`, tidak dibuang.
3. **Sel kosong.** `–` berarti provinsi belum terbentuk dan `…` berarti nilainya ditahan. Keduanya
   menjadi sel tanpa nilai, bukan nol.

Setiap halaman wajib menghasilkan tepat 39 baris, yaitu 38 provinsi dan agregat Indonesia. Jumlah
sel per baris harus sama dengan jumlah kolom yang tercetak di header `(1) (2) ...`. Baris yang
tidak memenuhinya menggagalkan ekstraksi, bukan ditebak. Empat belas halaman lampiran lolos syarat
ini tanpa kegagalan.

**Validasi silang.** Tiga belas nilai nasional yang pada H2 ditranskripsi manual dari grafik
dibandingkan dengan hasil ekstraksi lampiran ini: **13 identik, 0 berbeda**. Jalur otomatis dan
jalur manual saling mengonfirmasi.

## Cakupan yang dibandingkan

| Domain | Indikator | Kode | WebAPI | Halaman lampiran | Status |
|---|---|---|---|---|---|
| Pendidikan | Tingkat penyelesaian SD/SMP/SMA | 4.1.2* | `var=1980` | 254-255 | Dibandingkan |
| Lingkungan | Akses sanitasi layak | 6.2.1* | `var=847` | 269 | Dibandingkan |
| Lingkungan | Fasilitas cuci tangan | 6.2.1* | `var=1273` | 269 | Dibandingkan |
| Energi | Rasio penggunaan gas rumah tangga | 7.1.2.(b) | `var=150` kategori Gas/Elpiji | 272 | Dibandingkan |
| Ekonomi | Laju pertumbuhan PDB per tenaga kerja | 8.2.1* | `var=1161` | 274 | Dibandingkan |
| Ekonomi | Proporsi pekerja informal | 8.3.1* | `var=2153` | 274 | Dibandingkan |
| Ekonomi | Upah rata-rata per jam | 8.5.1* | `var=1172` | 275 | Dibandingkan |
| Ekonomi | Tingkat pengangguran terbuka | 8.5.2* | `var=543` periode Agustus | 275 | Dibandingkan |
| Ekonomi | NEET | 8.6.1* | `var=1186` | 276 | Dibandingkan |
| Energi | Rasio elektrifikasi | 7.1.1* | — | 272 | `concept_mismatch` |
| Ekologi | Lahan terdegradasi | 15.3.1* | — | 288 | `no_webapi_series` |

Dua penolakan dicatat sebagai keputusan, bukan sebagai kekosongan.

7.1.1* pada publikasi adalah **rasio elektrifikasi** milik ESDM, sedangkan `var=2832` adalah
**persentase rumah tangga pengguna listrik** milik BPS. Keduanya konsep berbeda, persis seperti
peringatan `concept_mixture` pada H1. WebAPI memang memuat rasio elektrifikasi pada `var=1155`,
tetapi hanya nasional, sehingga tidak dapat dipakai untuk uji provinsi.

Ekologi tetap tidak dapat dibandingkan pada tingkat provinsi. Lampiran 12 hanya memuat 15.3.1,
sedangkan H1 sudah membuktikan tidak ada tabel WebAPI gratis untuk indikator itu.

## Hasil perbandingan sel

| Domain | Indikator | Sel nasional | Sel provinsi | Sama | Berbeda |
|---|---|---:|---:|---:|---:|
| Pendidikan | Tingkat penyelesaian | 12 | 408 | 420 | 0 |
| Lingkungan | Akses sanitasi layak | 3 | 102 | 105 | 0 |
| Lingkungan | Fasilitas cuci tangan | 3 | 102 | 105 | 0 |
| Energi | Rasio penggunaan gas | 3 | 102 | 99 | 6 |
| Ekonomi | PDB per tenaga kerja | 4 | 136 | 113 | 27 |
| Ekonomi | Pekerja informal | 4 | 136 | 140 | 0 |
| Ekonomi | Upah per jam | 4 | 136 | 140 | 0 |
| Ekonomi | Pengangguran terbuka | 4 | 136 | 140 | 0 |
| Ekonomi | NEET | 4 | 136 | 140 | 0 |
| **Total** | | **41** | **1.394** | **1.402** | **33** |

Tidak ada sel yang hanya ada pada satu sumber. Keempat provinsi pemekaran Papua absen pada
2020-2022 di **kedua** kanal, sehingga temuan H1 tentang pemekaran Papua terkonfirmasi dari sisi
publikasi juga.

### Pemisahan sebab

33 perbedaan dipilah dengan aturan yang ditetapkan di muka.

| Klasifikasi | Jumlah | Aturan |
|---|---:|---|
| `last_digit_difference` | 19 | Selisih tidak lebih dari satu satuan pada desimal terakhir yang diterbitkan, yaitu sesuatu yang pembulatan saja sudah dapat menghasilkannya |
| `candidate_revision` | 14 | Selisih lebih besar, dan `last_update` tabel WebAPI lebih baru daripada tanggal terbit publikasi |

Perbedaan terbesar seluruhnya pada laju pertumbuhan PDB per tenaga kerja:

| Provinsi | Tahun | WebAPI 2026-09-08 | TPB 2024 | Selisih |
|---|---|---:|---:|---:|
| Maluku Utara | 2023 | 12,04 | 11,05 | 0,99 |
| Maluku | 2021 | -0,18 | 0,38 | 0,56 |

Kasus Maluku 2021 patut diperhatikan karena **tandanya berubah**, dari kontraksi menjadi
pertumbuhan. Ini kandidat revisi yang paling kuat sekaligus contoh konkret mengapa angka lama perlu
tetap dapat dipanggil ulang.

Label `candidate_revision` sengaja tidak disebut revisi. Bukti yang ada baru berupa `last_update`
yang lebih baru; membuktikannya sebagai revisi memerlukan dua penarikan WebAPI pada tanggal
berbeda, dan itu belum tersedia.

## Ketidaksesuaian granularitas

Setiap agregat nasional diuji terhadap baris provinsinya sendiri, di dalam sumbernya masing-masing.
Hasilnya konsisten pada 82 kombinasi yang diuji, 41 per kanal:

- **82 dari 82** nilai nasional berada di dalam rentang nilai provinsi;
- **0 dari 82** nilai nasional sama dengan rata-rata provinsi tanpa bobot.

| Indikator | Selisih terbesar terhadap rata-rata provinsi |
|---|---:|
| Upah rata-rata per jam | Rp 1.841,76 per jam |
| Rasio penggunaan gas | 10,15 poin persen |
| Fasilitas cuci tangan | 2,57 poin persen |
| Tingkat penyelesaian | 1,45 poin persen |
| Pengangguran terbuka | 1,04 poin persen |

Artinya angka nasional tidak dapat dibentuk ulang dari angka provinsi tanpa penimbang populasi.
Inilah sebab ketiga pada §1.1 README, dan ia terukur pada **keempat** domain yang dapat
dibandingkan, bukan hanya pada dua domain yang menunjukkan perbedaan antarsumber.

## Cacat pelabelan tahun pada publikasi

Kolom 8.6.1* (NEET) pada halaman 276 diberi header tahun 2019, 2020, 2021, dan 2022. Keempat nilai
Indonesia pada kolom itu adalah 24,28; 22,40; 23,22; dan 22,25, sedangkan deret WebAPI `var=1186`
untuk 2020 sampai 2023 adalah 24,28; 22,40; 23,22; dan 22,25. Kecocokannya persis pada empat titik
berurutan, sehingga label tahun yang tercetak bergeser satu tahun.

Pemetaan H3 memakai tahun yang terbukti dari datanya, dan label yang tercetak tetap disimpan pada
kolom `publication_printed_period` di `config/h3/province_columns.csv` agar koreksi ini dapat
diaudit. Tanpa koreksi, indikator ini akan tampil sebagai 140 sel berbeda, yaitu kesalahan
penyelarasan yang menyamar sebagai temuan.

## Tambahan rekonsiliasi antarrilis

Audit provinsi di atas tetap menjadi hasil utama H3. Sebagai penguat Gate G1, jalur tambahan
membandingkan grafik nasional TPB 2024, grafik nasional TPB 2025, dan snapshot WebAPI H3. Jalur
ini membaca 4.591 observasi WebAPI dan 205 observasi publikasi, lalu membentuk 4.608 kunci sel.
Sebanyak 156 kunci hadir pada minimal dua rilis: 148 identik dan 8 berbeda. Sebanyak 4.452 kunci
lain dipertahankan sebagai `single_source`, tidak dipaksa menjadi perbandingan.

| Domain | Sel berbeda | Contoh |
|---|---:|---|
| Energi | 5 | Bauran energi terbarukan 2018-2020 dan 2023; intensitas energi 2018 |
| Ekonomi | 2 | Pertumbuhan PDB per kapita 2020 dan 2021 |
| Ekologi | 1 | Tutupan hutan 2022 |

Empat sel menunjukkan perubahan langsung antara dua publikasi bertanggal: bauran energi
terbarukan 2023, pertumbuhan PDB per kapita 2020 dan 2021, serta tutupan hutan 2022. Ini adalah
jejak antarrilis resmi yang dapat diamati. Empat perbedaan lain melibatkan snapshot WebAPI dan
publikasi.

Klasifikasi jalur tambahan masih berstatus kandidat sampai H4. Enam sel diberi
`release_revision_candidate`. Tutupan hutan 2022 diberi
`methodology_or_denominator_change_candidate` karena judul dan denominator publikasi berubah.
Intensitas energi 2018 berbeda 287,98 SBM per miliar rupiah, terlalu besar untuk dianggap
pembulatan atau revisi kecil, sehingga diberi `methodology_or_unit_change_candidate`.

Berkas `h3-release-chart-scope.csv` hanya menjelaskan ruang lingkup grafik tambahan ini. Nol sel
provinsi publikasi pada berkas tersebut berarti grafik TPB yang dipilih bersifat nasional; hal itu
tidak meniadakan 1.394 sel provinsi yang sudah dibandingkan dari lampiran TPB 2024 pada hasil utama.

## Kaitannya dengan Gate G1

| Kriteria G1 | Status |
|---|---|
| 1. Ketidaksesuaian terukur pada minimal tiga dari lima domain | **Terpenuhi oleh bukti gabungan H3.** Jalur antarrilis menemukan perbedaan nilai pada energi, ekonomi, dan ekologi. Audit granularitas juga menemukan ketidaksesuaian pada empat domain. |
| 2. Sebagian besar ketidaksesuaian dapat dijelaskan oleh salah satu dari tiga sebab | **Menunggu H4.** Audit utama memberi label awal pada 33 dari 33 perbedaan; delapan perbedaan antarrilis baru memiliki klasifikasi kandidat yang harus diuji dengan aturan bersama. |
| 3. Terdapat jejak revisi antarwaktu yang dapat diamati | **Bukti awal tersedia.** Empat sel berubah antara TPB 2024 dan TPB 2025; H5 harus membekukan jejak waktunya sebagai input eksperimen. |

Gate G1 belum dinyatakan lolos karena kriteria kedua baru diuji pada H4. Manifest tambahan mencatat
`criterion_1_passed=true` dan mempertahankan status keseluruhan
`pending_H4_classification_and_H5_revision_trace` agar hasil H3 tidak melampaui bukti yang ada.

## Artefak

- `config/h3/province_indicators.csv`: keputusan penyelarasan sepuluh indikator dan dua penolakan.
- `config/h3/province_columns.csv`: pemetaan 45 kolom lampiran ke seri, tahun, dan kategori WebAPI.
- `results/processed/h3-webapi-observations.csv` dan `h3-publication-observations.csv`: masing-masing
  1.435 observasi ternormalisasi.
- `results/processed/h3-cell-comparison.csv`: 1.435 kunci sel.
- `results/processed/h3-discrepancies.csv`: 33 perbedaan beserta klasifikasinya.
- `results/processed/h3-granularity.csv`: 82 uji nasional terhadap provinsi.
- `results/processed/h3-indicator-summary.csv`: ringkasan per indikator dan per tingkat geografi.
- `data/manifests/h3-comparison.json`: checksum seluruh input dan keluaran.
- `config/h3/webapi_series.csv` dan `publication_series.csv`: seri untuk tambahan antarrilis.
- `results/processed/h3-release-cell-comparison.csv`: 4.608 kunci antarrilis.
- `results/processed/h3-release-discrepancies.csv`: delapan perbedaan pada tiga domain.
- `results/processed/h3-release-chart-scope.csv`: batas cakupan geografi grafik tambahan.
- `data/manifests/h3-release-reconciliation.json`: checksum dan status Gate G1 tambahan.

Jalankan ulang dengan:

```bash
make h3-run
make h3-releases
make test
```

## Stack fondasi

`docker-compose.yml` menaikkan MinIO, katalog Iceberg REST, dan Spark. Hanya komponen wajib pada §9
README yang diaktifkan; Trino, OpenMetadata, dan Airflow belum. Versi image ada di
`infra/docker/versions.env` dan konfigurasi katalog Spark di `infra/spark/spark-defaults.conf`.

```bash
make stack-up
make stack-freeze   # menulis infra/docker/image-digests.txt
make stack-down
```

Stack telah diverifikasi pada 9 September 2026 di VM `sigerciv@34.128.67.92` dengan hostname
`praktikum-sd`. VM mempunyai 2 vCPU, RAM 7,7 GiB, dan disk 19 GiB. MinIO dan Iceberg REST
mencapai status sehat; endpoint MinIO, REST, dan Jupyter merespons, lalu `spark-sql` berhasil
menjalankan `SHOW NAMESPACES IN kkciv` melalui REST catalog. Port 9000, 9001, 8181, 8888, dan
4040 diikat ke `127.0.0.1` pada VM dan dapat diteruskan melalui SSH bila perlu.

Image yang teruji adalah MinIO rilis 2024-06-13, MinIO Client rilis 2024-06-12, Iceberg REST
1.8.1, serta Spark 3.5.5 dengan Iceberg 1.8.1. Digest tersimpan di
`infra/docker/image-digests.txt`. Saat idle ketiga layanan memakai sekitar 1 GiB RAM; setelah image
ditarik, disk VM menyisakan 3,4 GiB. VM ini cukup untuk validasi fondasi H3, tetapi belum memenuhi
batas eksperimen proposal 8 vCPU, 16 GB RAM, dan penyimpanan 256 GB. Kapasitas harus dinaikkan atau
batas eksperimen diubah dan dibekukan sebelum pengukuran performa.

```bash
make stack-remote-up
make stack-remote-status
make stack-remote-verify
make stack-remote-freeze
make stack-remote-down
```

Uji tulis-baca tabel Iceberg tetap menjadi pekerjaan H5; H3 hanya memverifikasi layanan dan jalur
Spark ke katalog.
