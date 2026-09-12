# 3. Metode

*Draf H12 Jalur A dan C, 13 September 2026. Seluruh angka berasal dari `data/angka-kunci.csv`;
pemetaannya ada di akhir berkas. Konfigurasi yang dirujuk di sini dibekukan pada 12 September 2026,
sebelum eksperimen utama dijalankan, dan tercatat di `docs/research/experiment-freeze.md`.*

## 3.1 Ringkasan rancangan

Penelitian ini membandingkan empat cara menyimpan indikator resmi yang direvisi, pada beban revisi
yang sama, di atas satu tumpukan lakehouse yang sama. Ketiga pembanding mewakili praktik yang
sudah ada, dan yang keempat merupakan usulan.

| Kode | Perlakuan | Keadaan yang disimpan | Pernyataan tulis per revisi | Pemeliharaan |
|---|---|---|---|---|
| B0 | overwrite | tepat satu baris terkini per sel | `MERGE` | `expire_snapshots` sisa satu |
| B1 | snapshot penuh | satu salinan keadaan lengkap per rilis | `INSERT OVERWRITE` seluruh state | tidak ada |
| B2 | pemilihan sumber tunggal | satu baris per sel menurut skor kepercayaan | `INSERT OVERWRITE` seleksi yang dihitung ulang | `expire_snapshots` sisa satu |
| B3 | vintage-aware (usulan) | store append-only berkunci `(cell_id, vintage_id)` ditambah tabel serving | `INSERT` ke store lalu `MERGE` sel kotor | `expire_snapshots` sisa satu pada kedua tabel |

Rancangannya adalah pengukuran berulang pada beban identik: setiap titik pengukuran dijalankan tiga
kali dalam siklus purge-rebuild-suntik-ukur yang berurutan, dan seluruh repetisi dilaporkan sebelum
agregasi apa pun dilakukan. B2 mewakili keluarga truth discovery dan sekaligus menjadi pembanding
langsung terhadap pendekatan berbasis skor kepercayaan yang dipakai pekerjaan terkait; B1 mewakili
batas atas kemampuan memanggil ulang angka lama dengan ongkos ruang terbesar; B0 menjadi titik nol
karena mencerminkan praktik yang lazim.

## 3.2 Data

Seluruh sumber berada pada jalur gratis Badan Pusat Statistik dan ditarik satu kali, lalu dibekukan.
Snapshot WebAPI pertama ditarik pada 8 September 2026 pukul 14:04:19 UTC untuk inventarisasi, dan
snapshot kedua pada hari yang sama pukul 23:38:59 UTC untuk perbandingan provinsi. Dua kompilasi
indikator TPB, edisi 2024 dan 2025, diunduh dari katalog publikasi resmi. Setiap penarikan disimpan
sebagai vintage baru beserta manifest ber-checksum, dan tidak pernah menimpa penarikan sebelumnya;
aturan ini penting karena revisi justru merupakan objek penelitiannya.

Dua beban kerja dipakai, dan keduanya diperlukan untuk alasan yang berbeda.

**Fixture bukti** berisi 14 sel dengan 38 observasi pada tiga vintage. Keempat belas sel inilah yang
mempunyai jejak revisi nyata terkonfirmasi, sehingga hanya di sini kemampuan memanggil ulang angka
dapat diuji terhadap revisi yang benar-benar terjadi.

**Panel sweep** berisi 6.983 observasi pada 5.378 sel dengan empat vintage, mencakup 16 indikator,
lima domain, 38 provinsi ditambah agregat nasional, dan periode 2015 sampai 2025. Panel dipakai
sebagai keadaan dasar pengukuran ongkos, karena pada fixture 14 sel ongkos tetap satu pernyataan
lebih besar daripada pekerjaan datanya sehingga perbandingan ongkos tidak bermakna di sana.

Panel diturunkan dari satu batch ingestion dengan satu penyesuaian yang perlu dinyatakan. Dari 7.666
baris, 683 baris mengulang pasangan `(cell_id, source_id)` yang sama karena dua variabel WebAPI
membawa indikator yang sama untuk sel yang sama. Setiap kelompok duplikat diperiksa dan seluruhnya
memuat satu nilai yang identik, sehingga baris yang penarikannya lebih lama dibuang tanpa kehilangan
informasi. Penyesuaian ini diperlukan karena B3 mensyaratkan kunci `(cell_id, vintage_id)` yang unik.

## 3.3 Identitas sel, vintage, dan observasi

Perbandingan antarsumber hanya bermakna bila dua nilai memang berbicara tentang hal yang sama.
Karena itu identitas ditetapkan secara eksplisit dan dibekukan sebelum eksperimen.

`cell_id` adalah SHA-256 atas kunci indikator, kunci seri, periode yang diamati, tingkat geografi,
dan kode geografi, dipotong menjadi 20 heksadesimal. `vintage_id` adalah SHA-256 atas identitas
sumber, tanggal rilis, dan checksum manifest sumbernya, dengan pemotongan yang sama. `observation_id`
menggabungkan sel, vintage, dan locator rekaman sumbernya. Dua nilai dari sumber berbeda hanya
dianggap sel yang sama bila seluruh dimensi tersebut cocok.

Konsekuensi rancangan ini terlihat pada panel: dua penarikan WebAPI pada hari yang sama membentuk dua
vintage berbeda karena manifestnya berbeda, dan urutan kedatangannya ditentukan oleh tanggal rilis,
waktu penarikan, lalu identitas vintage. Nilai numerik eksak dan bentuk angka yang diterbitkan
disimpan terpisah, sehingga perbandingan aritmetik dan reproduksi bentuk terbit sama-sama terjaga.

## 3.4 Beban revisi

Revisi diuji dari dua arah. Revisi nyata diambil dari perbedaan antarsumber dan antarrilis yang
benar-benar terjadi, dan menjadi bukti bahwa persoalannya ada. Revisi tersuntik diperlukan karena
besaran revisi nyata tidak dapat dikendalikan, sedangkan pertanyaan tentang ongkos menuntut besaran
yang terkontrol.

Aturan penyuntikan dibekukan sebelum eksekusi. Nilai awal setiap injeksi adalah vintage terbaru pada
sel yang dipilih; nilainya digeser tepat satu unit pada presisi yang diterbitkan, dan arah
perubahannya dibalik bila nilai persentase akan melewati 100. Dimensi pembentuk sel tidak pernah
diubah, setiap baris sintetis ditandai sebagai bukan angka resmi, dan setiap baris menyimpan nilai
sebelum, delta, nilai sesudah, observasi dasar, serta sumber yang disimulasikan direvisi.

Perlu ditegaskan bahwa perubahan satu unit adalah mekanisme pemicu dependensi, bukan model besaran
revisi yang sebenarnya. Yang dikontrol pada eksperimen ini adalah **jumlah sel** yang direvisi, bukan
besar perubahan nilainya.

Sweep utama menyapu enam titik, yaitu 1, 2, 4, 8, 16, dan 38 sel yang direvisi. Semestanya adalah
satu irisan indikator-tahun pada seluruh 38 provinsi, sehingga titik terbesarnya secara harfiah
merupakan satu tahun penuh untuk seluruh provinsi. Sel dipilih dengan peringkat deterministik dari
SHA-256 atas seed eksplisit dan identitas sel, sehingga setiap skenario merupakan subset skenario
yang lebih besar dan tidak ada keadaan acak yang berasal dari waktu eksekusi. Seluruh sel semesta
dilayani satu sumber, sehingga aturan satu sumber yang direvisi per run terpenuhi di setiap titik.

## 3.5 Metrik

Empat metrik utama dan empat metrik pendukung ditetapkan sebelum eksperimen, dan definisi
operasionalnya disimpan dalam bentuk yang dapat dibaca mesin.

**Waktu penghitungan ulang** adalah waktu pernyataan yang dikeluarkan sebuah perlakuan untuk
menerapkan satu revisi, ditambah pernyataan pemeliharaan yang dituntut perlakuan tersebut. Waktu
diambil dari laporan waktu per pernyataan di dalam satu sesi, sehingga start-up mesin eksekusi dan
penyiapan view tidak masuk ke ongkos perlakuan. Pemisahan fase tulis dan fase pemeliharaan
dilaporkan terpisah, karena pada tumpukan ini keduanya berbeda sifat.

**Jumlah sel yang dievaluasi** memisahkan pekerjaan logis dari ongkos fisik. Untuk B3, jumlah ini
adalah himpunan sel kotor yang diturunkan dari edge lineage, bukan dari pembandingan nilai; untuk
perlakuan yang menulis ulang seluruh keadaan, jumlah ini adalah seluruh sel keadaan tersebut.

**Ruang penyimpanan** dihitung dari seluruh objek yang terjangkau dari metadata snapshot yang
dipertahankan, dengan ukuran diambil dari object store. Objek yang berada di lokasi tabel tetapi
tidak dirujuk metadata apa pun dilaporkan terpisah dan tidak pernah ikut dihitung. Ukuran yang
tercatat pada metadata wajib sama dengan ukuran objek yang sebenarnya, dan pemeriksaan ini merupakan
syarat sebelum angka ruang dipakai.

**Tingkat keberhasilan memanggil ulang** adalah proporsi permintaan atas angka yang pernah terbit
yang masih dapat dijawab persis, dicocokkan pada identitas observasi dan bentuk angka yang
diterbitkan, bukan hanya pada nilai numeriknya.

Metrik pendukungnya adalah kelengkapan lineage, jumlah byte yang dibaca, proporsi ketidaksesuaian
yang dapat dijelaskan otomatis, dan tingkat propagasi revisi. Tingkat propagasi revisi adalah jumlah
revisi yang terbaca di keadaan serving sebuah perlakuan setelah satu run, dibagi jumlah revisi yang
masuk pada run tersebut; metrik ini diusulkan setelah profil validasi dan statusnya dicatat sebagai
tambahan, bukan sebagai metrik yang ada sejak awal. Jumlah byte yang dibaca tidak diukur, karena
antarmuka baris perintah pada tumpukan yang dibekukan tidak mengekspos statistik tersebut per
pernyataan; hal ini dinyatakan sebagai keterbatasan, bukan diganti proksi.

## 3.6 Protokol eksekusi

Setiap titik pengukuran dijalankan sebagai siklus tertutup. Seluruh tabel perlakuan dihapus beserta
berkas fisiknya, keempat perlakuan dibangun ulang dari beban kerja yang sama rilis demi rilis dengan
mekanisme tulisnya masing-masing, keadaan dasar diukur, revisi disuntikkan melalui mekanisme tulis
tiap perlakuan, keadaan sesudahnya diukur, lalu seluruh permintaan pemanggilan ulang dijalankan.
Siklus diulang tiga kali per titik.

Dua hal menjaga agar angkanya tidak dapat dibaca sesuai harapan peneliti. Pertama, keluaran yang
harus dihasilkan setiap perlakuan pada setiap titik diprediksi lebih dahulu oleh simulator
perlakuan yang berjalan terpisah dari mesin eksekusi, sebelum satu pun pengukuran fisik dilakukan;
keadaan fisik setelah revisi dibandingkan terhadap prediksi itu, dan selisih bukan nol menghentikan
run. Kedua, sel yang tidak direvisi dibandingkan terhadap keadaan beban kerja yang dihitung secara
independen dari pernyataan yang sedang diukur, sehingga pemeriksaan tidak dapat lolos hanya karena
pernyataan tersebut konsisten dengan dirinya sendiri.

Eksekusi dipegang satu operator dan berjalan berurutan. Dua run yang berjalan serentak akan saling
memengaruhi CPU, memori, dan I/O pada node tunggal, sehingga angkanya tidak dapat dipakai.

## 3.7 Lingkungan

Seluruh pengukuran berjalan pada satu node dengan 2 vCPU, RAM 7,7 GiB, dan penyimpanan 19 GB, dengan
memori driver 2 GB. Spesifikasi ini menggantikan spesifikasi yang direncanakan semula dan dinyatakan
di muka sebagai revisi rancangan, bukan sebagai penyesuaian setelah melihat hasil. Versi setiap
komponen tumpukan dibekukan beserta digest image-nya, dan katalog tabel wajib persisten; syarat
terakhir ini bukan detail operasional, karena katalog yang tidak persisten pernah menghapus kemampuan
sebuah perlakuan memanggil angka lama tanpa meninggalkan tanda apa pun pada data.

Konsekuensinya dinyatakan tanpa ditutupi: waktu hanya boleh dibaca sebagai perbandingan
antarperlakuan pada perangkat keras yang sama, dan tidak pernah sebagai klaim performa, throughput,
maupun skalabilitas.

## 3.8 Reproducibility

Setiap tahap menuliskan manifest berisi checksum seluruh masukan dan keluarannya, dan tahap
berikutnya menolak berjalan bila satu saja checksum tidak cocok. Konfigurasi eksperimen dibekukan
dalam berkas terpisah yang memuat nilai beku, berkas buktinya, dan checksum berkas tersebut pada saat
pembekuan; tahap eksekusi memeriksa ulang seluruh checksum itu sebelum bekerja. Pengukuran mentah,
yaitu waktu per pernyataan, daftar objek, dan hasil pemanggilan ulang, disimpan sebelum agregasi,
dan tabel agregat dapat dibentuk ulang dari berkas mentah tersebut memakai perintah yang sama.

Rantai provenans dipelihara utuh dari manifest sumber sampai tabel naskah: manifest sumber, vintage,
versi transformasi, sel indikator, metrik, lalu tabel dan gambar. Setiap angka pada naskah ini
diambil dari satu berkas angka kunci yang menyebutkan sumber dan cara penurunan tiap nilai, sehingga
tidak ada angka yang diketik ulang secara manual.

## 3.9 Ancaman terhadap validitas

**Satu node dan satu ukuran panel.** Waktu diukur pada satu konfigurasi perangkat keras dan satu
ukuran keadaan dasar. Hasil waktu karena itu tidak dapat diekstrapolasi ke perangkat keras lain
maupun ke keadaan yang jauh lebih besar, dan tidak ada kurva skalabilitas yang dilaporkan.

**Kebijakan pemeliharaan ikut terukur.** Pada tumpukan ini, pernyataan pemeliharaan snapshot
menghabiskan waktu yang sebanding dengan pernyataan tulisnya. Perlakuan yang mekanismenya menuntut
pemeliharaan karena itu membawa ongkos tetap yang tidak berkaitan dengan besaran revisi. Perbandingan
waktu antarperlakuan pada laporan ini adalah perbandingan mekanisme **beserta** kebijakan
pemeliharaannya, dan keduanya tidak dipisahkan pada rancangan yang dibekukan.

**Semesta sweep bersumber tunggal.** Ke-38 sel semesta sweep hanya dilayani satu sumber. Pilihan ini
diperlukan agar aturan satu sumber yang direvisi per run terpenuhi di setiap titik, tetapi
konsekuensinya perlakuan pemilihan sumber tunggal tidak pernah menghadapi pilihan pada beban ini,
sehingga tingkat propagasi revisinya pada sweep bernilai satu menurut konstruksi. Perilaku menahan
revisi pada perlakuan tersebut dibuktikan pada beban validasi yang bersumber majemuk, bukan pada
sweep, dan kedua hasil tidak boleh dibaca sebagai satu rangkaian.

**Besaran perubahan nilai tidak divariasikan.** Yang divariasikan adalah jumlah sel yang direvisi.
Eksperimen ini karena itu tidak berbicara tentang pengaruh besar kecilnya perubahan nilai terhadap
ongkos.

**Volume kecil.** Domainnya memang tidak pernah besar, tetapi hal ini tetap membatasi klaim. Hasil
berlaku untuk indikator resmi pada granularitas nasional sampai provinsi, dan tidak digeneralisasi ke
beban analitik berukuran besar.

**Jumlah repetisi.** Tiga repetisi per titik cukup untuk melaporkan median beserta rentangnya,
tetapi tidak cukup untuk uji signifikansi. Seluruh angka waktu karena itu dilaporkan sebagai median
dengan nilai minimum dan maksimum, bukan sebagai rata-rata dengan interval kepercayaan.

---

## Angka yang dipakai pada bagian ini

| Kalimat | Nilai | `metric_id` |
|---|---|---|
| Vintage, observasi, sel pada fixture bukti | 3, 38, 14 | `p2_vintages`, `p2_observations`, `p2_stable_cells` |
| Observasi dan sel pada panel sweep | 6.983 dan 5.378 | `p3_sweep_panel_observations`, `p3_sweep_panel_cells` |
| Titik sweep yang dijalankan | 6 | `p3_sweep_points` |
| Skor kepercayaan tiap sumber | 0,9625; 0,9625; 0,907143 | `b2_trust_score_bps_tpb_2025` dst. |

Jumlah baris H4 sebelum penyesuaian (7.666) dan jumlah baris duplikat yang dibuang (683) berasal dari
`docs/research/experiment-freeze.md` butir 2 dan `docs/research/h11-main-sweep.md`. Spesifikasi node
berasal dari berkas freeze butir 7. Definisi kedelapan metrik berasal dari
`config/experiments/metric_definitions.csv`.

## Yang belum masuk draf ini

Angka hasil sweep sengaja tidak dibahas di bagian Metode; seluruhnya masuk bagian Hasil yang
kerangkanya ada di `03-kerangka-tabel-hasil.md`. Bagian Metode versi bahasa Inggris untuk naskah CAS
menyusul setelah draf ini diperiksa bersama.
