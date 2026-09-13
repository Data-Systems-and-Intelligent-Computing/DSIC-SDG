# Query Plan, Log, dan Statistik Pembacaan (H14 Operator)

## Status

H14 sisi operator mengumpulkan tiga hal yang diwajibkan §12 README tetapi belum pernah tersimpan:
**query plan** setiap pernyataan tulis perlakuan, **log sesi** lengkap, dan **statistik pembacaan**.
Yang ketiga sekaligus menutup metrik pendukung s2, yang pada H11 dinyatakan tidak terukur.

Kontrak ada di
[`contracts/h14-plan-and-read-statistics.json`](../../contracts/h14-plan-and-read-statistics.json).
Jalankan `make h14-collect` di host stack, lalu `make h14-run`.

## Mengapa s2 sekarang dapat diukur

H11 menyatakan jumlah byte yang dibaca tidak dapat diukur karena antarmuka baris perintah Spark SQL
tidak melaporkannya per pernyataan. Pernyataan itu benar untuk keluaran CLI, tetapi tidak untuk event
log Spark. Iceberg menerbitkan ukuran hasil pemindaiannya sebagai akumulator sisi driver, yaitu
`total data file size (bytes)` beserta jumlah berkas yang dibaca dan yang dilewati, sedangkan view
CSV yang menjadi sumber staging melaporkan `Input Metrics` pada tingkat task. Keduanya dapat
dipulihkan dari event log dan dipetakan ke identitas eksekusi SQL masing-masing.

Karena itu H14 melaporkan **dua komponen terpisah**, bukan satu angka gabungan yang menyesatkan:

- `iceberg_bytes_read`, yaitu byte berkas data milik tabel perlakuan sendiri yang dibaca setelah
  pemangkasan;
- `file_bytes_read`, yaitu byte berkas staging yang dibaca pernyataan yang sama.

Keduanya adalah ukuran berkas, bukan byte terdekompresi dan bukan lalu lintas object store.

## Batas yang dinyatakan di muka

Menyalakan event log berarti Spark menulis satu baris per task dan per pembaruan SQL. Itu ongkos
yang tidak dimiliki run pengukuran waktu yang dibekukan. Karena itu **waktu dari run H14 tidak
dilaporkan sama sekali**, dan kontraknya menolak berjalan bila batas itu dilonggarkan. Yang diambil
dari run ini hanya rencana eksekusi, log, dan ukuran pembacaan.

## Yang dijalankan

Pernyataan yang diukur adalah pernyataan injeksi H11 yang sudah dibekukan, diambil dari pustaka SQL
bersama yang sama, tanpa satu pun perubahan. Untuk setiap titik sweep terkecil dan terbesar,
`sweep_001` dan `sweep_038`, keadaan dasar panel dibangun ulang lebih dahulu, lalu setiap perlakuan
dijalankan dalam satu sesi yang:

1. membuat view staging;
2. mencetak `EXPLAIN FORMATTED` dari pernyataan tulisnya, sebelum pernyataan itu dieksekusi;
3. mengeksekusi pernyataan tulis dan pemeliharaannya;
4. menyimpan seluruh keluaran sesi sebagai log.

Event log sesi dibaca untuk statistik pembacaan, lalu dikompresi dan disimpan sebagai bukti. Dua
repetisi dijalankan, karena pernyataan yang sama atas keadaan yang sama harus membaca berkas yang
sama; perbedaan antarrepetisi akan menghentikan agregasi.

## Hasil

Dua repetisi pada dua titik sweep menghasilkan 168 eksekusi SQL terinstrumentasi, 8 rencana
eksekusi, dan 48 artefak yang disimpan, yaitu 16 plan, 16 log sesi, dan 16 event log terkompresi
berjumlah sekitar 5,1 MB. Kelima invarian lolos. Marker:

```
H14_VERIFY|2|2|168|1111882|3469013|3489279|5628612|8|48|collected
```

### Byte yang dibaca satu revisi

Median dua repetisi, dipisah menurut asal bacaannya:

| Titik | Perlakuan | Dari tabelnya sendiri | Berkas data | Dari staging | Total |
|---|---|---:|---:|---:|---:|
| 1 sel | B0 | 594.148 | 10 | 517.727 | 1.111.875 |
| 1 sel | B1 | 0 | 0 | 3.469.013 | 3.469.013 |
| 1 sel | B2 | 0 | 0 | 3.489.276 | 3.489.276 |
| 1 sel | B3 | 3.073.190 | 90 | 2.545.159 | 5.618.349 |
| 38 sel | B0 | 594.148 | 10 | 517.734 | 1.111.882 |
| 38 sel | B1 | 0 | 0 | 3.469.013 | 3.469.013 |
| 38 sel | B2 | 0 | 0 | 3.489.279 | 3.489.279 |
| 38 sel | B3 | 3.078.364 | 90 | 2.550.248 | 5.628.612 |

Tiga hal terbaca langsung.

**B1 dan B2 tidak membaca tabelnya sendiri sama sekali.** Keduanya menimpa seluruh keadaan, sehingga
tidak perlu tahu isi tabel lama; seluruh bacaannya berasal dari sumber staging. Ongkos baca mereka
adalah ongkos menghitung ulang keadaan dari sumber, bukan ongkos membaca keadaan yang sudah ada.

**B0 membaca 594.148 byte dari tabelnya sendiri, berapa pun besaran revisinya.** Angka itu sama
persis pada revisi 1 sel dan 38 sel, karena `MERGE` salin-saat-tulis harus membaca seluruh berkas
data yang memuat baris yang cocok, dan ke-10 berkas itu memang memuatnya.

**B3 membaca paling banyak, yaitu 5,6 MB, dengan 90 berkas data dari store-nya sendiri.** Store
append-only menumpuk berkas kecil setiap kali sebuah rilis atau revisi masuk, dan penyelesaian sel
kotor membaca menyeberangi berkas-berkas itu. Inilah mekanisme di balik urutan waktu pada H11 dan
H12: perlakuan yang paling hemat menulis justru paling banyak membaca.

Seperti waktunya, jumlah byte yang dibaca hampir tidak berubah antara revisi 1 sel dan 38 sel.

### Rencana eksekusi

| Perlakuan | Operator puncak | Penulisan ulang salin-saat-tulis | Join | Baris rencana |
|---|---|---|---|---:|
| B0 | `ReplaceData` | ya | `BroadcastHashJoin`, `SortMergeJoin` | 219 |
| B1 | `OverwriteByExpression` | tidak | `BroadcastHashJoin`, `BroadcastNestedLoopJoin` | 163 |
| B2 | `OverwriteByExpression` | tidak | `BroadcastHashJoin` | 131 |
| B3 | `AppendData` | tidak | `BroadcastHashJoin` | 70 |

Rencana B0 menegaskan temuan H12 bahwa `MERGE` lebih mahal daripada penulisan ulang penuh pada skala
ini: ia satu-satunya yang memakai `ReplaceData`, yaitu penulisan ulang salin-saat-tulis, dan
satu-satunya yang memerlukan `SortMergeJoin` penuh antara sumber dan berkas sasaran. `INSERT
OVERWRITE` hanya menulis berkas baru dan tidak perlu menggabungkan apa pun dengan isi lama.

Rencana kedua repetisi identik setelah identitas objek JVM dinormalkan. Normalisasi itu hanya
menyentuh nama kelas lambda beserta alamat code-cache-nya, yang memang berganti pada setiap JVM;
digest berkas mentahnya tetap dicatat berdampingan.

### Determinisme

Jumlah berkas yang dibaca, jumlah berkas yang dilewati, jumlah baris keluaran, dan jumlah eksekusi
berulang persis sama pada kedua repetisi. Ukuran byte bergeser paling besar 0,031 persen, jauh di
dalam toleransi 0,1 persen yang dinyatakan kontrak. Penyebabnya dinyatakan apa adanya: berkas Parquet
yang ditulis siklus ini tidak identik byte dengan yang ditulis siklus sebelumnya, dan batas split
pada sumber staging dapat bergeser beberapa byte.

### Yang ditunjukkan hasil ini untuk perbaikan berikutnya

Store B3 dibaca dari 90 berkas data. Pemadatan berkas pada store merupakan arah perbaikan yang jelas,
tetapi H14 **tidak** mengukurnya, dan tidak ada klaim yang boleh dibuat tentang seberapa besar
pengaruhnya. Yang diukur di sini hanya apa yang dibaca oleh mekanisme yang sudah dibekukan.

## Artefak audit

- kontrak: `contracts/h14-plan-and-read-statistics.json`;
- pengumpul: `scripts/h14_collect.sh`, memakai pustaka SQL bersama `scripts/h11_sql.sh`;
- keluaran mentah, termasuk plan, log sesi, dan event log terkompresi:
  `results/raw/h14/h14-20260913/`;
- hasil: `results/processed/h14-*.csv` dan `data/manifests/h14-plan-and-read-statistics.json`.
