# Tabel, Gambar, dan Draf Hasil (H15 Jalur A dan C)

## Status

H15 Jalur A dan C menyusun tabel dan gambar bagian Hasil, lalu menulis draf bagian tersebut dalam
bahasa Indonesia. Bentuk tabel dan gambarnya sudah dibekukan pada H11 di
[`papers/vintage_reconciliation/draft/03-kerangka-tabel-hasil.md`](../../papers/vintage_reconciliation/draft/03-kerangka-tabel-hasil.md),
yaitu sebelum angka sweep ditafsirkan, sehingga pemilihan tabel tidak dipengaruhi hasil yang sudah
dilihat.

Kontrak ada di
[`contracts/h15-result-tables-and-figures.json`](../../contracts/h15-result-tables-and-figures.json).
Jalankan `make h15-run` lalu `make h15-figures`. Marker: `H15_VERIFY|7|2|5|88|10|validated` dan
`H15F_VERIFY|5|5|5|10|rendered`.

## Yang disusun

Tujuh tabel dibentuk di sini karena memerlukan penggabungan lintas tahap; sisanya disalin apa adanya
oleh paket naskah dan cukup dicatat pada inventaris.

| ID | Pertanyaan | Isi | Asal |
|---|---|---|---|
| T7 | P3 | keadaan dasar sweep dan yang ditulis tiap perlakuan | kerangka beku |
| T8 | P3 | waktu penghitungan ulang per titik sweep | kerangka beku |
| T9 | P3 | pertambahan byte per titik sweep | kerangka beku |
| T10 | P3 | titik impas dan syaratnya | kerangka beku |
| T13 | P4 | recall pada fixture dan pada panel | kerangka beku |
| T15 | P3 | ongkos menerapkan keempat rilis nyata | ditambahkan setelah kerangka dibekukan |
| T16 | P3 | byte yang dibaca dan rencana eksekusi tiap pernyataan | ditambahkan setelah kerangka dibekukan |

Dua tabel terakhir ditandai sebagai tambahan beserta alasannya. T15 lahir dari pengukuran rilis nyata
yang dikerjakan setelah kerangka dibekukan, dan T16 lahir dari penutupan metrik byte yang dibaca,
yang pada kerangka masih dinyatakan tidak terukur. Penandaan ini disimpan pada kolom `origin` di
inventaris, bukan diselesaikan dengan menulis ulang kerangkanya.

Lima gambar dibentuk dengan 88 titik data. Empat di antaranya mengikuti kerangka beku, sedangkan G5
ditandai sebagai tambahan karena audit panel yang menjadi sumbernya belum ada ketika kerangka
dibekukan. Setiap titik G1 dan G2 membawa nilai minimum dan maksimum ketiga repetisi, dan setiap
keterangan gambar memuat lingkungan 2 vCPU beserta batas klaimnya.

| ID | Isi | Bentuk | Asal |
|---|---|---|---|
| G1 | waktu penghitungan ulang terhadap besaran revisi | garis, sumbu y linear | kerangka beku |
| G2 | pertambahan byte terhadap besaran revisi | garis, sumbu y log | kerangka beku |
| G3 | sel yang dievaluasi terhadap besaran revisi | garis, sumbu y log | kerangka beku |
| G4 | recall per perlakuan, permintaan resmi dan sintetis | batang | kerangka beku |
| G5 | recall pada fixture dan pada panel | batang | ditambahkan setelah kerangka dibekukan |

## Perenderan gambar

Gambar dirender sebagai sumber PGFPlots yang dikompilasi menjadi PDF dengan pdflatex. Pilihan ini
diambil karena naskahnya memang dokumen LaTeX: hasilnya vektor, fontnya seragam dengan naskah, dan
datanya tetap terbaca di dalam berkas sumber gambar sehingga dapat diperiksa tanpa membuka pipeline.
Tidak ada pustaka penggambar yang ditambahkan ke stack pengukuran, dan perenderan berjalan di laptop
peneliti, bukan di node pengukuran.

Kompilasi dibuat deterministik dengan `SOURCE_DATE_EPOCH` tetap dan penekanan metadata opsional PDF,
sehingga dua kompilasi berturut-turut menghasilkan berkas yang identik byte. Checksum kesepuluh
berkas keluaran, yaitu lima sumber dan lima PDF, dicatat pada `data/manifests/h15-figures.json` dan
diperiksa oleh pengujian.

Satu catatan pembacaan gambar: pada G3, kurva B0 dan B3 berimpit karena keduanya mengevaluasi tepat
sel yang direvisi, demikian pula B1 dan B2 yang selalu menghitung ulang seluruh sel. Hal tersebut
dinyatakan pada keterangan gambar agar tidak terbaca sebagai kurva yang hilang.

## Cara angka masuk ke tabel

Seluruh sumber diverifikasi terhadap checksum yang dicatat manifest tahapnya sebelum satu nilai pun
dibaca, memakai mekanisme yang sama dengan paket naskah. Sembilan sumber dipakai untuk ketujuh tabel
dan keempat gambar. Kontraknya melarang nilai yang diketik manual, dan invarian tersebut diperiksa
pada setiap eksekusi.

## Draf bagian Hasil

Draf ditulis dalam bahasa Indonesia di
[`papers/vintage_reconciliation/draft/05-hasil.md`](../../papers/vintage_reconciliation/draft/05-hasil.md),
mengikuti aturan draf yang berlaku sejak H10 Jalur C: tidak ada angka yang diketik ulang, seluruhnya
dirujuk melalui `metric_id` pada `angka-kunci.csv`, dan setiap berkas draf ditutup tabel pemetaan dari
kalimat ke `metric_id`. Tiga puluh delapan `metric_id` dirujuk, dan seluruhnya diperiksa keberadaannya
oleh pengujian.

Susunannya mengikuti urutan pertanyaan penelitian, yaitu karakterisasi ketidaksesuaian, representasi
vintage, ongkos penghitungan ulang, kemampuan memanggil ulang angka terbit, kegagalan yang tidak
muncul pada tingkat keberhasilan, propagasi revisi, dan stabilitas pengukuran. Observasi dipisahkan
dari interpretasi pada setiap subbagian, dan seluruh klaim dibatasi pada lingkungan yang dibekukan.

Pembahasan dan Kesimpulan tidak ditulis di sini dan memang berada di luar jendela tiga minggu.

## Reproduksi

```bash
make h15-run
make h15-figures
make article-bundle
```

Penyusunan menolak berjalan bila kerangka beku dinyatakan berbeda dari yang dibekukan pada H11, bila
kontraknya mengizinkan nilai yang diketik manual, bila sebuah tabel tambahan tidak membawa alasan,
bila ada titik gambar berepetisi yang tidak membawa rentangnya, atau bila sebuah keterangan gambar
tidak menyebut lingkungan yang dibekukan.

Penyusunan diulang di VM dari commit yang sama dan menghasilkan checksum identik untuk kedua belas
berkas keluaran; 199 test lulus pada kedua mesin dengan satu test PDF dilewati, dan paket naskah
terverifikasi dengan 60 tabel serta 184 angka kunci.

## Artefak audit

- kontrak: `contracts/h15-result-tables-and-figures.json`;
- tabel naskah: `results/processed/h15-table-t7.csv` sampai `h15-table-t16.csv`;
- inventaris tabel dan gambar: `results/processed/h15-table-inventory.csv`,
  `results/processed/h15-figure-inventory.csv`;
- data gambar: `results/processed/h15-figure-data.csv`;
- validasi dan ringkasan: `results/processed/h15-validation.csv`, `results/processed/h15-summary.csv`;
- manifest: `data/manifests/h15-result-tables-and-figures.json`;
- sumber dan berkas gambar: `papers/vintage_reconciliation/manuscript/figures/`;
- manifest gambar: `data/manifests/h15-figures.json`;
- draf: `papers/vintage_reconciliation/draft/05-hasil.md`.
