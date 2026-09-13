# Titik Impas dan Analisis Kegagalan (H14 Jalur A dan C)

## Status

H14 Jalur A dan C mengerjakan dua hal yang dijadwalkan rencana kerja: mencari titik impas
inkremental dan mengerjakan analisis kegagalan. Keduanya sudah mempunyai bahan terukur dari H11
sampai H14 sisi operator; yang dikerjakan di sini adalah **menjelaskan** hasilnya dan menyatukan sisi
ongkos dengan sisi reproducibility menjadi satu tabel yang dapat dibaca sekaligus.

Kontrak ada di
[`contracts/h14c-breakeven-and-failure-analysis.json`](../../contracts/h14c-breakeven-and-failure-analysis.json).
Jalankan `make h14c-run`. Marker: `H14C_VERIFY|8|6|1|0|3|125|B1,B3|validated`.

Jawaban terukur atas P3 tidak berubah sedikit pun dan dibawa apa adanya dari
[`results/processed/h11-breakeven.csv`](../../results/processed/h11-breakeven.csv): **tidak ada titik
impas di dalam rentang beku 1 sampai 38 sel pada kedua ukuran.** Yang ditambahkan di sini adalah
alasannya.

## Dekomposisi ongkos

Delapan garis dipasang atas enam titik sweep beku, satu per perlakuan per ukuran. Ini **deskripsi
enam titik terukur**, bukan model terfit dengan inferensi; tidak ada selang kepercayaan yang dihitung
dan tidak boleh ada yang dikutip.

| Perlakuan | Waktu tetap per revisi | Waktu per sel | Bagian pemeliharaan | Byte tetap per revisi | Byte per sel |
|---|---:|---:|---:|---:|---:|
| B0 | 25,23 s | −0,006 | 56,5% | 13.309 | 31,3 |
| B1 | 10,15 s | −0,001 | 0,0% | 468.349 | 36,1 |
| B2 | 23,91 s | −0,017 | 59,0% | 25.959 | 11,9 |
| B3 | 37,44 s | −0,046 | 57,7% | 50.145 | 78,8 |

Dua pola terbaca sekaligus.

**Waktu hampir seluruhnya ongkos tetap.** Kemiringannya bertanda negatif dan sangat kecil, yaitu
derau, bukan tren. Pemeliharaan snapshot memakan 56 sampai 59 persen waktu B0, B2, dan B3, dan nol
persen pada B1 yang mekanismenya memang tidak menuntutnya. Karena itu keunggulan waktu B1 sebagian
besar bukan keunggulan mekanisme tulisnya, melainkan akibat kebijakan pemeliharaan yang melekat pada
ketiga perlakuan lain.

**Byte tumbuh linear terhadap jumlah sel yang direvisi**, dengan ongkos tetap yang jauh berbeda
antarperlakuan: 13 KB pada B0, 26 KB pada B2, 50 KB pada B3, dan 468 KB pada B1.

## Kapan sebuah tren boleh disebut tren

Memasang garis pada enam titik selalu menghasilkan kemiringan. Kemiringan itu tidak berarti apa-apa
kecuali titik terkecil dan titik terbesar memang dapat dibedakan. Aturan yang dipakai di sini
menuntut dua hal sekaligus:

1. rentang terukur pada titik terkecil dan titik terbesar tidak bertumpang tindih; dan
2. median bergerak satu arah pada keenam titik.

Seluruh deret waktu gagal pada syarat kedua: mediannya naik turun. Seluruh deret byte lolos keduanya.
Karena itu tidak ada satu pun proyeksi waktu yang dilaporkan, meskipun garisnya punya kemiringan.

## Syarat agar titik impas mungkin ada

| Perbandingan | Ukuran | Arah terukur | Proyeksi | Status |
|---|---|---|---:|---|
| B3 terhadap B1 | waktu | B1 lebih murah di seluruh rentang | — | datar di dalam rentang terukur |
| B3 terhadap B1 | byte | B3 lebih murah di seluruh rentang | 9.785 sel | di luar rentang terukur |
| B3 terhadap B0 | waktu | B0 lebih murah di seluruh rentang | — | datar di dalam rentang terukur |
| B3 terhadap B0 | byte | B0 lebih murah di seluruh rentang | — | garisnya menjauh, tidak pernah bersilangan |
| B3 terhadap B2 | waktu | B2 lebih murah di seluruh rentang | — | datar di dalam rentang terukur |
| B3 terhadap B2 | byte | B2 lebih murah di seluruh rentang | — | garisnya menjauh, tidak pernah bersilangan |

Angka 9.785 sel adalah **proyeksi, bukan titik impas**, dan tidak boleh dikutip sebagai jawaban P3.
Artinya justru sebaliknya: agar B3 berhenti lebih murah daripada B1 dalam ruang, satu revisi harus
menyentuh sekitar 9.785 sel sekaligus, sementara seluruh panel hanya berisi 5.378 sel dan semesta
sweep beku 38 sel. Pada beban ini keunggulan ruang B3 terhadap B1 tidak pernah habis.

Untuk waktu, kesimpulannya lebih tegas: karena tidak ada tren yang dapat diselesaikan pada kedua
sisi, **tidak ada besaran revisi yang dapat menghasilkan titik silang**, di dalam maupun di luar
rentang ini. Yang dapat mengubahnya hanya ongkos tetap, yaitu kebijakan pemeliharaan atau ongkos
tetap per pernyataan. Keduanya tidak diuji.

## Harga mempertahankan seluruh angka terbit

| Perlakuan | Recall panel | Gagal | Material | Menyajikan nilai usang | Waktu per revisi | Byte per revisi | Byte dibaca | Putusan |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| B0 | 0,7702 | 1.605 | 43 | 0 | 25,23 s | 13.309 + 31,3/sel | 1,11 MB | kehilangan angka terbit sesuai desain |
| B1 | 1,0000 | 0 | 0 | 0 | 10,15 s | 468.349 + 36,1/sel | 3,47 MB | menyimpan seluruh angka terbit |
| B2 | 0,7702 | 1.605 | 43 | 39 | 23,91 s | 25.959 + 11,9/sel | 3,49 MB | kehilangan angka terbit sesuai desain |
| B3 | 1,0000 | 0 | 0 | 0 | 37,44 s | 50.145 + 78,8/sel | 5,63 MB | menyimpan seluruh angka terbit |

Inilah jawaban gabungan P3 dan P4 dalam satu baris kalimat: **mempertahankan seluruh angka terbit
menuntut 3,8 kali byte B0 bila memakai B3, atau 35 kali bila memakai B1; B3 membeli recall penuh yang
sama dengan B1 dengan sekitar sepersembilan byte per revisi, tetapi membayarnya dengan 3,7 kali waktu
B1, yang 58 persennya adalah pemeliharaan snapshot.**

## Analisis kegagalan

| Jenis kegagalan | Perlakuan terdampak | Angka terdampak | Material | Akibat | Bebas dari kegagalan ini |
|---|---|---:|---:|---|---|
| ditimpa vintage kemudian | B0 | 1.605 | 43 | angka terbit tidak dapat dihasilkan ulang dari state perlakuan | B1, B2, B3 |
| tidak terpilih skor kepercayaan | B2 | 1.605 | 43 | angka terbit tidak dapat dihasilkan ulang karena sumbernya tidak dipilih | B0, B1, B3 |
| menyajikan nilai yang sudah digantikan | B2 | 39 | 39 | permintaan terjawab, tetapi dengan nilai yang sudah diganti produsen | B0, B1, B3 |

Jenis ketiga perlu ditekankan karena ia tidak muncul pada tingkat keberhasilan sama sekali.
Permintaan atas 39 sel itu dijawab B2 dengan sukses; yang dijawab bukan angka mutakhir. Tingkat
keberhasilan saja karena itu tidak cukup untuk menilai sebuah perlakuan, dan itulah alasan tabel di
atas memuat kolom material dan kolom nilai usang secara terpisah.

Harga menghindari ketiganya sama untuk semuanya: B1 atau B3, dan B3 adalah yang termurah dari
keduanya dalam ruang, yaitu 50.145 byte per revisi ditambah 78,8 byte per sel yang direvisi.

## Batas klaim

Dekomposisi ini deskriptif. Ia merangkum enam titik terukur pada satu ukuran panel, satu node, dan
satu kebijakan pemeliharaan. Tidak ada klaim bahwa hubungannya linear di luar rentang itu, dan
proyeksi tunggal yang dilaporkan sengaja diberi status `outside_measured_range` agar tidak terbaca
sebagai pengukuran.

Bagian pemeliharaan yang mencapai 56 sampai 59 persen menunjukkan bahwa perbandingan waktu pada
artikel ini adalah perbandingan mekanisme **beserta** kebijakan pemeliharaannya. Memisahkan keduanya
memerlukan eksperimen versi baru, dan hal itu dinyatakan sebagai keterbatasan, bukan dikerjakan
diam-diam di sini.

## Reproduksi

```bash
make h14c-run
```

Analisis menolak berjalan bila kontraknya menyatakan dekomposisinya sebagai model terfit, bila
proyeksi boleh disebut titik impas, bila angka recall dihitung ulang alih-alih disalin dari audit
H13C, atau bila sebuah perlakuan dengan recall penuh ternyata membawa kegagalan material. Analisis
diulang di VM dari commit yang sama: keenam berkas keluaran berchecksum identik dengan hasil di
laptop, 189 test lulus pada kedua mesin dengan satu test PDF dilewati, dan paket naskah terverifikasi
dengan 50 tabel serta 184 angka kunci.

## Artefak audit

- kontrak: `contracts/h14c-breakeven-and-failure-analysis.json`;
- dekomposisi: `results/processed/h14c-cost-decomposition.csv`;
- syarat titik impas: `results/processed/h14c-breakeven-conditions.csv`;
- harga reproducibility: `results/processed/h14c-cost-of-reproducibility.csv`;
- sintesis kegagalan: `results/processed/h14c-failure-synthesis.csv`;
- validasi dan ringkasan: `results/processed/h14c-validation.csv`, `results/processed/h14c-summary.csv`;
- manifest: `data/manifests/h14c-breakeven-and-failure-analysis.json`.
