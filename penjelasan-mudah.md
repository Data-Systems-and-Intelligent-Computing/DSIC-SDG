Baik. Untuk penelitian **Vintage-Aware Reconciliation of Official SDG Indicators**, inti persoalannya sebenarnya bisa dibuat sangat sederhana:

> **Kalau angka indikator SDG yang sama pernah diterbitkan dengan nilai berbeda oleh sumber resmi BPS pada waktu yang berbeda, bagaimana kita menyimpan semua versinya agar angka lama tetap bisa dipanggil kembali—dan berapa biaya tambahan untuk melakukan itu?**

Ini bukan penelitian tentang “mencari angka BPS mana yang paling benar”. Justru dokumennya berangkat dari asumsi bahwa perbedaan antarversi resmi dapat bermakna: karena **vintage/rilis data, perubahan metodologi, atau granularitas**. 

## 1. Sebenarnya apa yang dimaksud “vintage”?

Bayangkan indikator:

> **Persentase bauran energi terbarukan, tahun 2020**

Pada publikasi tahun 2024 tertulis:

```text
2020 → 11,20%
```

Kemudian pada publikasi tahun 2025 angka tahun 2020 diperbarui:

```text
2020 → 11,31%
```

Lalu WebAPI BPS pada 2026 mungkin memberikan:

```text
2020 → 11,35%
```

Semua menunjuk indikator dan tahun yang sama, tetapi berasal dari **rilis yang berbeda**.

Maka kita punya:

```text
Vintage 2024 → 11,20
Vintage 2025 → 11,31
Vintage 2026 → 11,35
```

“Vintage” dalam penelitian ini dapat dibayangkan sebagai:

> **versi suatu angka sebagaimana pernah diketahui atau diterbitkan pada satu waktu tertentu.**

Masalah terjadi kalau sistem konvensional hanya menyimpan:

```text
2020 → 11,35
```

Angka 11,20 dan 11,31 hilang.

---

# 2. Kenapa angka lama perlu dipertahankan?

Bayangkan laporan pemerintah tahun 2024 mengatakan:

> “Bauran energi terbarukan tahun 2020 sebesar 11,20%.”

Dua tahun kemudian seseorang ingin mereproduksi laporan tersebut.

Kalau database sudah menimpa angka lama:

```text
2020 → 11,35
```

maka ketika query dijalankan ulang, keluarnya:

```text
11,35%
```

bukan:

```text
11,20%
```

Padahal laporan 2024 **tidak salah** saat diterbitkan. Ia memakai vintage yang tersedia pada 2024.

Jadi penelitian ini bertanya:

> **Bisakah sistem menjawab “berapa angka yang berlaku pada rilis tertentu?”, bukan hanya “berapa angka terbaru sekarang?”**

Dokumen memang menekankan bahwa overwrite terhadap nilai lama membuat angka yang pernah dipublikasikan tidak lagi dapat direproduksi. 

---

# 3. Apa masalah ilmiahnya?

Ada tiga sumber utama perbedaan yang ingin dibedakan.

| Jenis            | Bahasa mudah                                                             |
| ---------------- | ------------------------------------------------------------------------ |
| **Vintage**      | Angka lama direvisi pada rilis berikutnya                                |
| **Metodologi**   | Cara menghitung atau definisinya berubah                                 |
| **Granularitas** | Angka nasional tidak harus sama dengan hasil menjumlahkan semua provinsi |



Jadi kalau dua sumber resmi berbeda:

```text
BPS A → 72,4
BPS B → 73,1
```

penelitian **tidak langsung berkata**:

```text
salah satunya salah
```

Tetapi:

```text
Mengapa berbeda?
↓
vintage?
metodologi?
granularitas?
```

Ini perbedaan penting dengan *truth discovery*.

---

# 4. Ini bukan penelitian memilih “sumber paling benar”

Dalam *truth discovery*, biasanya:

```text
Source A → 72
Source B → 74
Source C → 74
```

lalu sistem mencoba menentukan:

> “Nilai benar sebenarnya adalah 74.”

Tetapi pada statistik resmi, situasinya bisa berbeda.

Misalnya:

```text
rilis 2024 → 72
rilis 2025 → 74
```

Kedua angka punya fungsi historis.

Yang dibutuhkan bukan:

```text
72 dibuang
74 disimpan
```

tetapi:

```text
2024 → 72
2025 → 74
```

Dokumen secara eksplisit membedakan penelitian ini dari truth discovery: perbedaan dipertahankan sebagai informasi, bukan direduksi menjadi satu “truth”. 

---

# 5. Jadi RQ utamanya apa?

Versi resminya cukup panjang. Versi paling mudahnya:

> **Berapa biaya untuk menyimpan indikator SDG dengan riwayat versinya sehingga angka lama tetap dapat direproduksi, dan kapan update inkremental masih lebih murah daripada menghitung ulang semuanya?**

Ada dua bagian besar di sini:

```text
CORRECTNESS
Apakah angka lama bisa direproduksi?

+

COST
Berapa waktu dan storage yang dibutuhkan?
```

RQ resminya memang menggabungkan **reproducibility** dengan pertanyaan **break-even incremental recomputation vs full recomputation**. 

---

# 6. Kenapa ada “ongkos”?

Karena cara paling mudah mempertahankan semua riwayat adalah:

```text
rilis 1 → simpan seluruh tabel
rilis 2 → simpan seluruh tabel lagi
rilis 3 → simpan seluruh tabel lagi
rilis 4 → simpan seluruh tabel lagi
```

Ini pasti membuat angka lama mudah dipanggil.

Tetapi storage-nya bertambah.

Alternatifnya:

```text
simpan hanya apa yang berubah
```

lebih hemat storage dan mungkin lebih cepat.

Namun sistem menjadi lebih kompleks.

Jadi ada trade-off:

```text
Reproducibility
      ↕
Storage
      ↕
Recomputation Cost
```

---

# 7. Ada empat pendekatan yang dibandingkan

Inilah bagian eksperimen terpenting.

| Treatment              | Cara kerja                                                    | Intuisi                             |
| ---------------------- | ------------------------------------------------------------- | ----------------------------------- |
| **B0 — Overwrite**     | nilai lama ditimpa                                            | murah, tapi sejarah hilang          |
| **B1 — Full Snapshot** | setiap rilis simpan keadaan lengkap                           | sejarah aman, storage mahal         |
| **B2 — Single Source** | pilih satu sumber berdasarkan trust score                     | hanya satu versi yang dipertahankan |
| **B3 — Vintage-Aware** | simpan vintage eksplisit dan hitung ulang hanya sel terdampak | usulan penelitian                   |

Empat perlakuan tersebut memang menjadi desain perbandingan utama. 

---

# 8. Apa itu B0 — Overwrite?

Ini cara paling sederhana.

Misalnya awalnya:

```text
2020 = 11,20
```

datang rilis baru:

```text
2020 = 11,31
```

database menjadi:

```text
2020 = 11,31
```

Nilai lama:

```text
11,20
```

hilang.

Keuntungannya:

> sederhana dan storage kecil.

Kelemahannya:

> laporan lama sulit direproduksi.

Dan ini bukan sekadar teori. Dalam implementasi yang sudah dilakukan di repository, B0 menyisakan hanya 14 dari 38 alamat observasi vintage yang dapat dipanggil ulang; 24 observasi historis memang hilang sesuai desain overwrite. 

---

# 9. Apa itu B1 — Full Snapshot?

Setiap ada rilis:

```text
Snapshot 2024
→ seluruh tabel

Snapshot 2025
→ seluruh tabel lagi

Snapshot 2026
→ seluruh tabel lagi
```

Kalau mau laporan tahun 2024:

```text
buka snapshot 2024
```

Jadi reproducibility bagus.

Dalam implementasi saat ini, tiga snapshot mempertahankan seluruh 38 identitas observasi dan audit logis berhasil 38/38. 

Masalahnya:

> **Apakah perlu menyimpan seluruh keadaan kalau sebenarnya hanya sedikit sel yang berubah?**

---

# 10. Apa itu B2 — Single Source?

Ini mewakili cara berpikir:

> “Kalau sumber berbeda, pilih sumber yang paling dipercaya.”

Misalnya:

```text
TPB 2025 score = 0,96
WebAPI score   = 0,91
```

maka:

```text
pilih TPB 2025
```

dan nilai lain tidak dipertahankan sebagai keluaran utama.

B2 penting sebagai pembanding karena mendekati pola *truth-discovery/source-selection*.

Dalam implementasi repository, B2 hanya dapat memanggil ulang 14 dari 38 observasi kandidat; 24 observasi yang tidak dipilih tidak lagi tersedia sebagai state akhir.  

---

# 11. Apa itu B3 — Vintage-Aware?

Ini proposal utama.

Daripada:

```text
indicator_id
year
value
```

buat:

```text
indicator_id
year
vintage_id
value
```

Misalnya:

```text
SDG7 | 2020 | TPB2024 | 11.20
SDG7 | 2020 | TPB2025 | 11.31
SDG7 | 2020 | API2026 | 11.35
```

Dengan begitu kita dapat bertanya:

```text
nilai terbaru?
```

atau:

```text
nilai sebagaimana diterbitkan 2024?
```

atau:

```text
bagaimana riwayat revisinya?
```

tanpa membuang versi lama.

Dokumen bahkan sudah menetapkan struktur dua tabel: `release_vintages` untuk rilis dan `indicator_observations` untuk sel indikator. 

---

# 12. Apa bedanya B1 dan B3?

Ini penting.

B1:

```text
setiap rilis
↓
simpan seluruh tabel lagi
```

B3:

```text
setiap rilis
↓
simpan vintage dan perubahan yang relevan
↓
pertahankan lineage
```

Bayangkan ada:

```text
10.000 sel
```

tetapi rilis baru hanya mengubah:

```text
20 sel
```

B1 secara konseptual memelihara snapshot penuh.

B3 mencoba bekerja lebih dekat ke:

```text
20 perubahan
```

dan hanya menghitung ulang hasil yang terdampak.

Pertanyaannya:

> Apakah penghematan itu benar-benar berarti setelah overhead lineage dan versioning dihitung?

Nah, itu harus dibuktikan eksperimen.

---

# 13. Apa itu incremental recomputation?

Misalnya indikator nasional dihitung dari banyak sel provinsi.

Ada 34 provinsi.

Hanya Lampung yang direvisi.

### Full recomputation

```text
baca semua provinsi
↓
hitung semuanya lagi
```

### Incremental recomputation

```text
deteksi Lampung berubah
↓
lihat indikator mana bergantung pada Lampung
↓
hitung ulang hanya bagian terdampak
```

Secara intuitif:

> **jangan hitung ulang seluruh dunia kalau hanya satu sel berubah.**

---

# 14. Tetapi incremental tidak selalu lebih murah

Ini justru salah satu pertanyaan penelitian paling menarik.

Misalnya revisi cuma:

```text
1 sel
```

incremental mungkin jauh lebih hemat.

Tetapi bagaimana kalau:

```text
50% tabel berubah?
```

atau:

```text
seluruh provinsi × seluruh tahun berubah?
```

Menelusuri dependency satu per satu mungkin malah mahal.

Akhirnya ada titik:

```text
ukuran revisi kecil
→ incremental menang

ukuran revisi besar
→ full recompute mungkin menang
```

Titik peralihan itulah **break-even point**.

---

# 15. Contoh break-even

Misalkan hasil kelak seperti ini:

| Jumlah sel direvisi | Incremental |  Full |
| ------------------: | ----------: | ----: |
|                   1 |       0,2 s | 2,0 s |
|                  10 |       0,4 s | 2,0 s |
|                 100 |       1,1 s | 2,0 s |
|                 500 |       2,2 s | 2,0 s |
|               1.000 |       3,6 s | 2,0 s |

Angka di atas **hanya ilustrasi**.

Dari ilustrasi:

```text
sekitar 100–500 sel
```

ada crossover.

Artinya:

> di bawah wilayah tersebut incremental menguntungkan; setelah itu full recomputation mungkin lebih murah.

---

# 16. Mengapa ada revisi nyata dan revisi sintetis?

Karena dua-duanya menjawab pertanyaan berbeda.

### Revisi nyata

Digunakan untuk membuktikan:

> **masalah ini benar-benar terjadi di BPS.**

Misalnya nilai 2022 yang berubah antara publikasi 2024, publikasi 2025, dan WebAPI 2026.

### Revisi sintetis

Digunakan untuk mengontrol:

> **berapa besar revisinya.**

Misalnya sengaja ubah:

```text
1 sel
2 sel
4 sel
7 sel
14 sel
```

Supaya kita dapat membuat kurva biaya secara sistematis.

Dokumen secara eksplisit memakai keduanya: revisi nyata untuk validitas empiris dan injeksi terkontrol untuk mencari break-even. 

---

# 17. Apakah revisi sintetis berarti datanya palsu?

Untuk analisis ketidaksesuaian BPS: tidak.

Bukti utama tetap:

```text
real BPS revisions
```

Synthetic injection hanya dipakai sebagai **experimental treatment**.

Analoginya seperti:

> kita tahu kecelakaan jaringan nyata terjadi, tetapi untuk menguji recovery kita sengaja memutus koneksi pada tingkat tertentu.

Di sini:

> kita tahu revisi resmi nyata terjadi, tetapi besarnya tidak dapat kita atur, sehingga kita membuat workload revisi terkontrol.

---

# 18. Datasetnya sebenarnya besar?

Tidak.

Dan repository secara eksplisit mengatakan **itu bukan masalah**.

H1 menemukan 29 variabel WebAPI, 240 ID periode sejak 2015, dan 27.826 sel data. 

Jadi ini bukan penelitian:

> “big data karena datanya sangat besar.”

Ini penelitian:

> **data systems untuk correctness, lineage, temporal versioning, reproducibility, dan maintenance cost.**

---

# 19. Lalu kenapa pakai lakehouse?

Karena kebutuhan penelitian cocok dengan beberapa karakteristiknya:

```text
snapshot
versioning
open table format
time travel
object storage
reproducible processing
```

Stack minimal:

```text
MinIO
↓
Apache Iceberg
↓
Spark / PySpark
```

Docker Compose untuk deployment dan Git untuk versioning. 

Trino, OpenMetadata, Airflow, GeoPandas saat ini **tidak dibutuhkan** untuk artikel utama.

---

# 20. Apa fungsi Iceberg di sini?

Iceberg relevan karena bisa mempertahankan:

```text
snapshot
table version
metadata
time travel
```

Tetapi novelty bukan:

> “menggunakan Apache Iceberg.”

Iceberg hanya mekanisme.

Novelty yang diklaim adalah:

> **menjadikan vintage indikator sebagai first-class object dalam penyimpanan dan mengukur biaya mempertahankannya.** 

---

# 21. Apa itu lineage?

Lineage menjawab:

> **Angka ini berasal dari mana dan melalui proses apa?**

Misalnya output:

```text
SDG7 2022 = 13,4%
```

harus dapat dilacak:

```text
Tabel hasil
↓
metric
↓
indicator cell
↓
transformation version
↓
vintage
↓
source record
↓
source manifest
```

Dokumen menetapkan rantai provenance:

`source manifest -> vintage -> transformation version -> indicator cell -> metric -> tabel/gambar`. 

---

# 22. Kenapa lineage penting?

Karena kalau suatu angka berubah, sistem perlu tahu:

> **apa yang harus dihitung ulang?**

Misalnya:

```text
Source cell A
↓
Indicator X
↓
Metric Y
↓
Table 3
```

Kalau A berubah:

```text
hitung ulang X
↓
hitung ulang Y
```

tetapi tidak perlu menghitung:

```text
Indicator Z
```

yang tidak bergantung pada A.

Jadi lineage punya dua fungsi sekaligus:

```text
provenance
+
dependency tracking
```

---

# 23. Apakah mereka sudah menemukan masalah nyata?

Ya, ini berbeda dengan beberapa README sebelumnya karena repository ini **sudah mengandung hasil tahap awal**.

Pada pilot H2, ada 19 sel yang dapat dibandingkan secara langsung antara WebAPI dan publikasi TPB 2024:

```text
16 sama
3 berbeda
```

Ketiga perbedaan berasal dari bauran energi terbarukan 2018–2020. 

Pada H3, audit yang lebih besar membandingkan:

```text
1.435 sel
```

dengan:

```text
1.402 sama
33 berbeda
```

dan tambahan publikasi TPB 2025 menemukan delapan perbedaan nilai pada tiga domain: energi, ekonomi, dan ekologi. 

Jadi objek penelitiannya **bukan hipotesis kosong**. Ketidaksesuaian sudah ditemukan.

---

# 24. Bahkan Gate G1 sudah lolos

Pada H4 awalnya terdapat:

```text
123 kejadian
85 confirmed
= 69,11%
```

yang dapat dijelaskan sebagai vintage, metodologi, atau granularitas.

Ini sedikit di bawah threshold 70%.

Kemudian H5 mengonfirmasi kandidat tambahan sehingga menjadi:

```text
96 / 123
= 78,05%
```

dan Gate G1 dinyatakan lolos. 

Artinya penelitian sudah menjawab satu pertanyaan awal:

> **Ya, objek konflik/revisi yang ingin diteliti memang ada secara empiris.**

---

# 25. Ada hasil penting lain: 14 revision traces

Setelah H5:

```text
14 jejak revisi
38 baris vintage
```

dibekukan.

Jadi satu `cell_id` bisa mempunyai beberapa vintage.

Contoh sederhananya:

```text
cell X
├── vintage 2024
├── vintage 2025
└── vintage 2026
```

Ini yang menjadi testbed awal untuk membangun representasi vintage-aware. 

---

# 26. Apa itu `cell_id`?

Bayangkan satu angka indikator diidentifikasi oleh kombinasi seperti:

```text
indikator
wilayah
tahun
kategori tertentu
```

Itulah sel logis.

Misalnya:

```text
indicator = SDG7 Renewable Share
province  = Lampung
year      = 2022
```

`cell_id` tetap.

Tetapi nilai pada vintage berbeda bisa berubah:

```text
cell_id = ABC
vintage 2024 → 12.8
vintage 2025 → 13.1
vintage 2026 → 13.3
```

Jadi:

```text
cell identity = tetap
release vintage = berubah
value = bisa berubah
```

Ini desain yang sangat penting.

---

# 27. Apa metrik utama penelitian?

Metrik utamanya bukan Accuracy atau F1.

Yang diukur adalah:

| Metrik                   | Pertanyaan                                      |
| ------------------------ | ----------------------------------------------- |
| **Recomputation time**   | berapa lama update setelah revisi?              |
| **Changed cells**        | berapa banyak sel benar-benar terdampak?        |
| **Storage space**        | berapa biaya menyimpan sejarah?                 |
| **Reproducibility rate** | berapa banyak angka lama dapat dipanggil ulang? |

Pendukungnya mencakup lineage completeness dan bytes read saat recomputation. 

---

# 28. Apa metrik yang paling penting?

Secara ilmiah, ada guardrail:

> **Reproducibility harus benar terlebih dahulu.**

Misalnya:

```text
B0 runtime = 0,1 detik
B3 runtime = 0,5 detik
```

B0 memang lebih cepat.

Tetapi kalau:

```text
B0 historical reproducibility = 36%
B3 historical reproducibility = 100%
```

maka tidak fair mengatakan:

> “B0 lebih baik karena lebih cepat.”

B0 dan B3 menyelesaikan level correctness yang berbeda.

Dokumen menegaskan bahwa solusi lebih murah yang gagal mereproduksi angka lama **tidak dihitung sebagai keuntungan**. 

---

# 29. Ini mirip penelitian DSIC-2606 tentang recovery

Ada kemiripan cara berpikir.

Pada penelitian recovery:

```text
job hidup kembali
≠
data pasti benar
```

Pada penelitian SDG ini:

```text
query cepat
≠
sistem versi datanya benar
```

Correctness tetap menjadi prasyarat sebelum membandingkan efisiensi.

---

# 30. Apa pertanyaan P1–P4 dalam bahasa sangat sederhana?

| Pertanyaan | Bahasa sederhana                                                                  |
| ---------- | --------------------------------------------------------------------------------- |
| **P1**     | Memang ada perbedaan apa saja di data BPS, dan penyebabnya apa?                   |
| **P2**     | Bisakah semua versi angka itu disimpan dengan rapi tanpa full copy terus-menerus? |
| **P3**     | Kapan incremental recomputation lebih murah daripada full recomputation?          |
| **P4**     | Bisakah angka lama benar-benar dibuat kembali setelah sumber berubah?             |

Empat subpertanyaan ini merupakan struktur artikel. 

---

# 31. P1 sudah mulai terjawab

Dari pekerjaan H1–H5:

```text
perbedaan nyata ditemukan
↓
diklasifikasikan
↓
revision traces dibentuk
```

Jadi P1 bukan lagi sepenuhnya rancangan.

Ada evidence empiris awal.

---

# 32. P2 sedang diwujudkan lewat schema vintage

Dua tabel utama:

```text
release_vintages
```

dan:

```text
indicator_observations
```

Dengan:

```text
cell_id = identitas sel
vintage_id = identitas rilis
```

H6 telah memproyeksikan 38 observasi menjadi tiga vintage dan 14 cell tanpa kehilangan provenance. 

Ini sudah merupakan bukti feasibility awal.

---

# 33. P3 belum final

Pertanyaan break-even:

```text
incremental
vs
full recompute
```

masih menunggu benchmark utama.

H8 baru menyiapkan workload injeksi:

```text
1
2
4
7
14
```

sel untuk validation profile. 

Jadi jangan membaca README seolah-olah break-even point sudah ditemukan.

**Belum.**

Itu masih hasil eksperimen yang akan dicari.

---

# 34. P4 sudah punya sinyal awal

B0:

```text
14 / 38 bisa dipanggil ulang
```

B1:

```text
38 / 38 bisa dipanggil ulang
```

B2:

```text
14 / 38 bisa dipanggil ulang
```

Ini sudah menunjukkan bahwa representasi state sangat memengaruhi historical reproducibility. 

Tetapi B3 dan evaluasi penuh masih diperlukan sebelum kesimpulan artikel final.

---

# 35. Jadi eksperimen utamanya nanti seperti apa?

Bayangkan workload:

```text
revisi 1 sel
revisi 2 sel
revisi 4 sel
...
revisi besar
```

Pada setiap workload jalankan:

```text
B0
B1
B2
B3
```

dan ukur:

```text
runtime
bytes read
storage
changed cells
reproducibility
```

Lalu buat kurva.

---

# 36. Grafik paling penting yang saya bayangkan

Misalnya:

```text
Recomputation Time
↑
│                 Incremental
│               /
│             /
│           X
│---------/---------- Full recompute
│       /
│     /
└────────────────────────→ Revision Size
```

`X` adalah:

> **break-even revision size**

Sebelum X:

```text
incremental lebih murah
```

Sesudah X:

```text
full recompute lebih murah
```

Kalau garis tidak pernah berpotongan, hasil:

> **no break-even within tested revision range**

juga sah.

---

# 37. Grafik penting kedua: storage vs reproducibility

Secara konseptual:

```text
Reproducibility
↑
│      ● B1
│   ● B3
│
│
│ ● B0/B2
└────────────────→ Storage Cost
```

Tujuannya melihat:

> apakah B3 bisa mendekati reproducibility B1 dengan biaya storage lebih kecil?

Sekali lagi ini ilustrasi konsep, bukan hasil.

---

# 38. Apa novelty-nya?

Bukan:

```text
Apache Iceberg
MinIO
Spark
time travel
incremental view maintenance
truth discovery
```

Novelty yang aman adalah:

> **memperlakukan vintage indikator sebagai objek kelas satu di dalam lakehouse dan secara empiris mengukur biaya mempertahankan reproducibility tersebut.** 

Versi lebih mudah:

> **Bukan sekadar menyimpan versi data, tetapi mengukur berapa harga yang harus dibayar agar angka resmi yang pernah diterbitkan tidak hilang dari sejarah komputasi.**

---

# 39. Mengapa penelitian ini menarik?

Karena ada konflik antara dua kebutuhan.

Sistem data biasanya ingin:

```text
latest data
simple state
fast update
```

Statistik resmi juga membutuhkan:

```text
historical reproducibility
revision trace
provenance
```

Kalau hanya mengejar “latest”:

```text
sejarah hilang
```

Kalau menyimpan seluruh snapshot terus:

```text
biaya maintenance meningkat
```

B3 mencoba mencari kompromi yang lebih baik.

---

# 40. Apa yang sebenarnya dilakukan enam peneliti?

Ini bukan enam paper.

Dokumen menegaskan seluruh tim bermuara ke **satu artikel**. 

Pembagiannya:

| Jalur             | Fokus                                            |
| ----------------- | ------------------------------------------------ |
| **A — Fondasi**   | stack, ingestion, vintage schema, B0/B1          |
| **B — Treatment** | B2, injection harness, benchmark                 |
| **C — Evidence**  | lineage, reproducibility, literature, manuscript |

B3 dikerjakan lintas A dan C karena membutuhkan schema sekaligus lineage. 

---

# 41. Kenapa benchmark tidak boleh dilakukan paralel oleh enam orang?

Karena satu node dipakai untuk pengukuran.

Kalau:

```text
Run A + Run B
```

dijalankan bersamaan:

```text
CPU contention
memory contention
disk I/O contention
```

maka runtime tidak comparable.

Jadi meskipun ada enam peneliti:

> **measurement run harus serial.**

Dokumen secara eksplisit menekankan ini. 

---

# 42. Apa tiga gate penelitian?

Cara paling mudah memahaminya:

### G1 — Apakah masalahnya benar-benar ada?

Jawabannya sekarang:

> **Ya, lolos.**

Ada disagreement dan revision trace nyata. 

### G2 — Apakah empat treatment benar-benar bisa dibandingkan?

Harus:

```text
B0
B1
B2
B3
```

menerima workload yang sama.

### G3 — Apakah RQ sudah benar-benar terjawab?

Harus menghasilkan:

```text
characterization
representation
cost/break-even
reproducibility
```

termasuk bila hasil break-even negatif. 

---

# 43. Kenapa hasil “incremental ternyata tidak lebih murah” tetap bagus?

Karena RQ-nya bukan:

> “Buktikan incremental lebih baik.”

RQ-nya:

> **Pada besaran revisi seperti apa incremental masih menguntungkan?**

Kalau hasil ternyata:

```text
bahkan revisi kecil
→ incremental overhead terlalu besar
```

maka kesimpulannya:

> pada skala data resmi yang diuji, incremental maintenance tidak memberikan keuntungan biaya.

Itu tetap sebuah hasil sistem yang berguna.

---

# 44. Apa batas klaimnya?

Paper hanya boleh mengklaim empat area:

> karakterisasi disagreement BPS, representasi vintage, recomputation cost/break-even, dan reproducibility.

Tidak boleh meloncat menjadi:

```text
platform SDG nasional
```

atau:

```text
scalable big-data architecture
```

atau:

```text
berlaku untuk seluruh 17 SDG
```

atau:

```text
berlaku di semua negara
```

Dokumen memang membatasi klaim dengan ketat. 

---

# 45. Jadi ini sebenarnya penelitian Big Data atau Data Systems?

Saya akan menyebutnya:

> **Data Systems / Versioned Data Management / Provenance / Incremental Maintenance / Reproducibility**

Bukan penelitian Big Data dalam arti:

```text
volume besar
distributed scale
petabyte
throughput tinggi
```

Bahkan README secara sadar mengatakan volumenya kecil dan **tidak boleh digunakan untuk klaim scalability**. 

---

# 46. Variabel penelitiannya apa?

Bisa diringkas menjadi:

| Komponen                | Isi                                  |
| ----------------------- | ------------------------------------ |
| **Treatment**           | B0, B1, B2, B3                       |
| **Revision size**       | dari sedikit sel sampai revisi besar |
| **Revision type**       | real dan injected                    |
| **Outcome cost**        | runtime, bytes read, storage         |
| **Outcome correctness** | historical reproducibility           |
| **Supporting outcome**  | lineage completeness                 |

Jadi model mentalnya:

$$
Storage\ Strategy
\times
Revision\ Size
\rightarrow
Recomputation\ Cost
+
Reproducibility
$$

---

# 47. Satu contoh eksperimen lengkap

Misalnya ada 14 `cell_id`.

Baseline sudah mempunyai vintage terbaru.

Kemudian injeksi revisi:

```text
revision size = 2 cells
```

Untuk setiap treatment:

```text
B0
B1
B2
B3
```

jalankan revisi yang **persis sama**.

Lalu ukur:

```text
elapsed time
bytes read
bytes written
storage after update
historical addresses recoverable
```

Setelah selesai, ganti:

```text
revision size = 4
```

lalu:

```text
7
```

lalu:

```text
14
```

Dengan begitu terbentuk kurva.

---

# 48. Mengapa semua treatment harus menerima revisi yang sama?

Kalau:

```text
B1 diuji dengan 2 sel
B3 diuji dengan 14 sel
```

perbandingan tidak valid.

Jadi workload revision harus:

```text
same changed cells
same original state
same values
same resource limit
```

Yang berbeda hanya strategi penyimpanannya.

Ini alasan harness H8 membuat route ke B0–B3 dengan filter dan checksum payload yang sama. 

---

# 49. Apa tools yang sebenarnya dibutuhkan?

Untuk paper ini cukup:

```text
Python / PySpark
MinIO
Apache Iceberg
Spark SQL
Docker Compose
Git
```

Yang **tidak diperlukan sekarang**:

```text
Trino
OpenMetadata
Airflow
Sedona
PostGIS
text-to-SQL
dashboard
MLOps
```

kecuali RQ memang diperluas. 

Ini keputusan yang tepat karena setiap tool tambahan bisa mengaburkan kontribusi utama.

---

# 50. Apa hasil yang sudah benar-benar ada dan mana yang belum?

Ini penting agar tidak mencampurkan **temuan** dan **rencana**.

| Sudah ada evidence                       | Belum final                     |
| ---------------------------------------- | ------------------------------- |
| disagreement antar-sumber memang ada     | break-even incremental vs full  |
| G1 sudah lolos                           | benchmark lengkap B0–B3         |
| 14 revision traces / 38 vintage rows     | storage cost final              |
| explicit vintage schema berhasil         | recomputation performance final |
| B0/B1/B2 sudah punya audit awal          | final statistical comparison    |
| lineage completeness 1.0000 pada fixture | kesimpulan artikel akhir        |

Jadi paper ini sudah lebih maju dibanding beberapa penelitian sebelumnya, tetapi **pertanyaan performa utamanya belum selesai**.

---

# 51. Apa cerita artikel yang paling kuat?

Bukan:

> “Kami membuat platform SDG dengan MinIO dan Iceberg.”

Jauh lebih kuat:

> **Kami menemukan ketidaksesuaian nyata antar-rilis dan jalur resmi BPS. Alih-alih memilih satu sebagai truth dan membuang yang lain, kami mempertahankan setiap angka sebagai vintage yang dapat dilacak. Kemudian kami mengukur biaya penyimpanan dan recomputation yang diperlukan untuk mempertahankan historical reproducibility, termasuk mencari kapan incremental recomputation tidak lagi lebih murah daripada full recomputation.**

Itu jauh lebih tajam.

---

# 52. Apa hubungan penelitian ini dengan penelitian sebelumnya?

Kalau kita sejajarkan dengan seluruh topik yang telah dibahas:

| Penelitian      | Masalah inti         | Treatment              | Outcome                |
| --------------- | -------------------- | ---------------------- | ---------------------- |
| Bioakustik      | noise/domain shift   | representation         | retrieval robustness   |
| Parquet         | query berbeda        | file size              | query latency          |
| Recovery        | pipeline failure     | checkpoint/idempotence | correctness            |
| Conflict Query  | evidence conflict    | Direct/Verify/Abstain  | risk/coverage          |
| Async FL        | heterogeneous client | participation/budget   | bytes + model quality  |
| MoE             | routing association  | expert ablation        | causal impact          |
| **SDG Vintage** | official revisions   | B0/B1/B2/B3            | reproducibility + cost |

Pola ilmiahnya tetap sama:

```text
masalah nyata
↓
treatment terkontrol
↓
ukur outcome
↓
jangan hanya mencari "pemenang"
↓
jelaskan trade-off dan mekanismenya
```

---

# 53. Kalimat yang paling mudah diingat

Kalau semua penjelasan tadi dilupakan, cukup ingat ini:

> **Angka indikator resmi dapat berubah ketika rilis baru terbit. Penelitian ini tidak ingin membuang angka lama, tetapi menyimpannya sebagai vintage sehingga laporan lama tetap bisa direproduksi. Setelah itu penelitian mengukur berapa biaya storage dan recomputation yang harus dibayar, serta kapan menghitung hanya bagian yang berubah masih lebih murah daripada menghitung ulang semuanya.**

Versi paling singkat:

> **“Berapa harga yang harus dibayar agar angka resmi yang pernah terbit tidak hilang ketika datanya direvisi?”**

Dan itu tepat dengan pertanyaan penggerak di README: **bagaimana menyimpan dan menghitung indikator SDG sehingga setiap angka yang pernah terbit tetap dapat dipanggil ulang, dan berapa ongkosnya.** 