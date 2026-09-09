# H7 Jalur C — Lineage Perlakuan dan Verifikasi Related Work

H7 Jalur C mengerjakan dua keluaran yang direncanakan pada README: memperluas lineage H6C ke
perlakuan H7 yang sudah berjalan, serta memverifikasi seluruh sumber `related-work.md` yang masih
bertanda `daftar`. Tahap ini tidak memasang sistem katalog eksternal; bukti disimpan sebagai CSV,
kontrak, dan manifest ber-checksum agar dapat diaudit langsung dari Git.

## 1. Verifikasi related work

Audit awal menemukan 18 kemunculan `daftar` yang mewakili 15 sumber unik. Tiga sumber muncul pada
dua bagian berbeda: paper *Correct-by-Design Lakehouse*, paper harmonisasi agregat, dan paper
evaluasi discord. Setiap sumber diperiksa pada halaman primer berupa penerbit, prosiding resmi,
arXiv, ECB, rOpenSci, Microsoft Learn, atau repositori resmi Feldera.

Semua 15 sumber mempunyai metadata primer yang dapat dibuktikan dan dinaikkan menjadi `metadata`.
Status ini berarti judul, tahun, venue/bentuk publikasi, identifier, dan ringkasan pokok sudah
diperiksa. Status ini **bukan** klaim bahwa semua PDF sudah dibaca penuh.

Koreksi tahun bibliografis yang penting:

- artikel GCC dan survei lakehouse terbit daring pada 2024, tetapi berada pada volume 2025;
- survei IEEE tersedia daring pada 2024, tetapi volume finalnya tahun 2025;
- ECB Working Paper 846 terbit 20 Desember 2007, bukan 2008;
- paper discord dibawakan di ADBIS 2025, sedangkan bentuk sitasi Springer memakai tahun 2026;
- dokumentasi Materialized Lake Views yang diverifikasi adalah dokumentasi Microsoft tahun 2026.

Inventaris sumber dan alasan koreksi dibekukan di
`config/h7c/related_work_verification.csv`. Pipeline gagal jika jumlah sumber berubah, URL primer
tidak ditautkan dari related work, status selain `metadata` muncul, atau masih ada baris tabel
`daftar`.

## 2. Perluasan lineage perlakuan

Graf H6C sebanyak 101 node dan 235 edge dipertahankan tanpa mengubah satu pun identitas. H7C
menambahkan tiga jenis node:

- `treatment_run` untuk run B0 atau B2 yang diikat ke checksum manifest;
- `treatment_decision` untuk keputusan atas setiap kandidat observasi;
- `treatment_output` untuk satu keluaran serving per sel dan perlakuan.

Empat relasi baru menghubungkan observasi ke keputusan, run ke keputusan, keputusan ke output,
dan output ke `indicator_cell`. Seluruh hubungan memakai `observation_id`, `cell_id`, path lineage
H6C, atau checksum manifest; fuzzy matching tetap dilarang.

## 3. Hasil

| Ukuran | Hasil |
|---|---:|
| Sumber related work unik terverifikasi | 15 |
| Kemunculan `daftar` lama yang ditutup | 18 |
| Baris `daftar` tersisa | 0 |
| Node graf gabungan | 207 |
| Edge graf gabungan | 491 |
| Keputusan perlakuan | 76 |
| Alamat yang masih dapat dibaca | 28 |
| Alamat yang tidak dapat dibaca | 48 |
| Kelengkapan source-to-output path | 1,0000 |

Sebanyak 76 keputusan terdiri dari 38 kandidat B0 dan 38 kandidat B2. Masing-masing perlakuan
mempunyai 14 keluaran serving. Angka 28 alamat yang dapat dibaca adalah 14 alamat B0 ditambah 14
alamat B2; 48 kegagalan adalah 24 pada setiap perlakuan. H7C tidak mengubah hasil B0/B2, hanya
menghubungkan setiap hasil kembali ke path sumber H6C dan manifest perlakuannya.

## 4. Status komponen opsional

| Komponen | Dipakai sekarang? | Alasan |
|---|---|---|
| Trino | Tidak | Spark SQL sudah cukup untuk query dan pemeriksaan yang berjalan; tidak ada eksperimen lintas mesin. |
| OpenMetadata | Tidak | Lineage H6C/H7C disimpan sebagai graf CSV dan manifest deterministik; belum ada kebutuhan UI katalog yang diuji. |
| Apache Airflow | Tidak | Pipeline masih berupa batch beku yang dijalankan melalui Makefile; belum ada jadwal penarikan berulang. |
| GeoPandas | Tidak | Geometri belum menjadi workload aktif dan referensi SDG 15 masih `hold`. |

Keputusan ini diverifikasi terhadap `docker-compose.yml` dan `pyproject.toml`, lalu dicatat di
`config/h7c/component_decisions.csv`. Keempatnya boleh ditambahkan kelak hanya jika pemicu yang
tertulis di file tersebut benar-benar masuk protokol penelitian. Menambah komponen sebelum itu
hanya menambah ongkos operasional tanpa menghasilkan bukti untuk pertanyaan riset sekarang.

## 5. Artefak dan reproduksi

- `contracts/h7c-evidence-lineage.json`: kontrak verifikasi literatur, perluasan graf, dan status komponen;
- `config/h7c/related_work_verification.csv`: 15 rekaman metadata primer;
- `config/h7c/component_decisions.csv`: keputusan empat komponen opsional;
- `results/processed/h7c-lineage-nodes.csv`: 207 node gabungan;
- `results/processed/h7c-lineage-edges.csv`: 491 edge gabungan;
- `results/processed/h7c-treatment-lineage.csv`: 76 path keputusan perlakuan;
- `results/processed/h7c-related-work-verification.csv`: hasil verifikasi 15 sumber;
- `results/processed/h7c-component-status.csv`: status komponen yang tervalidasi;
- `results/processed/h7c-validation.csv`: sembilan invariant;
- `data/manifests/h7c-evidence-lineage.json`: checksum seluruh input dan output;
- `tests/unit/test_h7c.py`: determinisme, imutabilitas H6C, coverage B0/B2, dan negative tests.

Jalankan:

```bash
make h7c-run
make test
```

Marker yang diharapkan:

```text
H7C_VERIFY|15|18|0|207|491|76|28|48|1.0000|4|validated
```

Eksekusi diverifikasi pada 9 September 2026 di `sigerciv@34.128.67.92` setelah VM menarik commit
implementasi `01ed667` dari `main`. Marker yang dihasilkan sama persis dengan marker di atas.
Sebanyak 54 test lulus dan satu test ekstraksi PDF H3 dilewati karena payload mentah tidak berada
di Git. Working tree VM tetap bersih setelah pipeline dan test dijalankan.

## 6. Batas interpretasi dan audit manusia

Verifikasi bibliografi masih berada pada tingkat metadata. Sebelum sebuah paper dipakai untuk
klaim rinci, PDF-nya tetap harus dibaca penuh. Manusia perlu menilai relevansi 15 sumber, enam
koreksi tahun utama, serta apakah sumber produk seperti Microsoft Fabric dan Feldera sebaiknya
diperlakukan sebagai pembanding sistem atau hanya konteks industri.

Lineage lengkap `1,0000` berlaku pada 76 keputusan B0/B2 di fixture 38 observasi. Ia belum
mencakup B1, B3, metrik eksperimen waktu/ruang, tabel, atau gambar artikel. Penutupan rantai sampai
artefak publikasi tetap menjadi pekerjaan H8–H9 Jalur C.
