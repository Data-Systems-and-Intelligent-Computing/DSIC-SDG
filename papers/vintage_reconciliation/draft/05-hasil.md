# 4. Hasil

*Draf H15 Jalur A dan C, 13 September 2026. Seluruh angka berasal dari
`data/angka-kunci.csv` melalui `metric_id`; pemetaannya ada di akhir berkas. Penomoran tabel dan
gambar mengikuti kerangka yang dibekukan pada H11 di `03-kerangka-tabel-hasil.md`, dan penomoran
akhir ditetapkan saat penulisan LaTeX.*

Bagian ini melaporkan bukti untuk keempat sub-pertanyaan. Urutannya mengikuti urutan pertanyaan,
yaitu karakterisasi ketidaksesuaian, representasi vintage, ongkos pemeliharaan, dan kemampuan
memanggil ulang angka terbit. Seluruh angka waktu berasal dari satu node dengan 2 vCPU yang
dibekukan sebagai batas sumber daya, sehingga angka tersebut hanya dapat dibaca sebagai perbandingan
antarperlakuan pada perangkat keras yang sama.

## 4.1 Ketidaksesuaian antarsumber benar-benar ada dan sebagian besar dapat dijelaskan

Perbandingan sel per sel antara ketiga sumber resmi menghasilkan 123 kejadian ketidaksesuaian yang
diklasifikasikan memakai delapan aturan yang ditetapkan sebelum data dilihat. Dari jumlah tersebut,
96 kejadian atau 78,05 persen dapat dipastikan berasal dari salah satu dari tiga sebab yang
dibedakan pada rancangan, yaitu revisi vintage, perubahan metodologi, dan perbedaan granularitas
(Tabel T2 dan T3).

Empat belas sel di antaranya mempunyai jejak revisi antarwaktu yang terkonfirmasi melalui tiga rilis
berurutan. Keempat belas sel itulah yang dipakai sebagai fixture bukti pada seluruh pengujian
perlakuan, karena hanya pada sel tersebut kemampuan memanggil ulang angka lama dapat diuji terhadap
revisi yang benar-benar terjadi.

Hasil ini menegaskan bahwa persoalan yang diteliti bukan persoalan hipotetis. Perbedaan antarsumber
resmi muncul pada lima domain, dan sebagian besarnya dapat dijelaskan secara sistematis, bukan
sebagai kesalahan salah satu sumber.

## 4.2 Vintage dapat direpresentasikan tanpa menyimpan salinan penuh setiap rilis

Fixture bukti berisi 3 vintage, 38 observasi, dan 14 sel indikator yang identitasnya stabil lintas
sumber. Seluruh 38 observasi tersimpan pada skema dengan vintage sebagai dimensi eksplisit tanpa
kehilangan provenance, dan setiap observasi dapat dipanggil kembali melalui kunci
`(cell_id, vintage_id)`.

Kemampuan tersebut diuji dengan rekonstruksi keadaan pada setiap rilis. Perlakuan vintage-aware
menghasilkan 42 baris state as-of, dan seluruhnya sama persis dengan snapshot penuh yang disimpan
perlakuan B1 (Tabel T5). Artinya keadaan pada setiap titik rilis dapat dibentuk ulang dari store
append-only tanpa menyimpan salinan tabel utuh untuk setiap rilis.

Hasil ini menjawab P2 pada tingkat representasi. Ongkos mempertahankannya dilaporkan pada bagian
berikutnya.

## 4.3 Ongkos penghitungan ulang

### 4.3.1 Revisi tersuntik dengan besaran terkontrol

Sweep utama dijalankan pada panel provinsi berisi 6.983 observasi pada 5.378 sel, dengan enam titik
besaran revisi dari satu sel sampai satu tahun penuh untuk 38 provinsi. Setiap titik dijalankan tiga
kali, dan seluruh repetisi dilaporkan sebelum agregasi.

Hasil pengukuran waktu menunjukkan pola yang tidak diperkirakan rancangan awal: **waktu keempat
perlakuan praktis tidak berubah ketika besaran revisi bertambah 38 kali lipat** (Tabel T8, Gambar
G1). Perlakuan B1 memerlukan 10,056 detik pada revisi satu sel dan 10,068 detik pada revisi 38 sel.
Pada rentang yang sama, B2 bergerak dari 24,616 menjadi 23,052 detik, B0 dari 24,652 menjadi 24,861
detik, dan B3 dari 38,007 menjadi 35,626 detik. Arah perubahannya tidak konsisten dan besarnya
berada dalam sebaran antarrepetisi.

Dekomposisi ongkos memperlihatkan penyebabnya. Ongkos waktu yang tidak bergantung pada besaran
revisi berjumlah 10,15 detik pada B1, 23,91 detik pada B2, 25,23 detik pada B0, dan 37,44 detik pada
B3, sedangkan pemeliharaan snapshot menghabiskan 56 sampai 59 persen waktu B0, B2, dan B3 serta nol
persen pada B1 (Tabel T8). Dengan kata lain, pada keadaan dasar sebesar 5.378 sel, waktu ditentukan
oleh jumlah pernyataan dan kebijakan pemeliharaan, bukan oleh jumlah baris yang disentuh.

Ruang penyimpanan berperilaku berbeda. Pertambahan byte tumbuh mengikuti besaran revisi, dengan
kemiringan 11,9 byte per sel pada B2, 31,3 pada B0, 36,1 pada B1, dan 78,8 pada B3, di atas ongkos
tetap yang jauh berbeda antarperlakuan (Tabel T9, Gambar G2). Perlakuan B1 menambah 468.313 byte
pada revisi satu sel dan 469.682 byte pada revisi 38 sel, karena setiap revisi menuliskan salinan
penuh keadaan 5.378 sel. Perlakuan B3 menambah 49.262 dan 52.873 byte pada kedua titik yang sama,
yaitu sekitar sepersembilan pertambahan B1, sedangkan B0 paling hemat dengan 13.279 dan 14.459 byte.

Perbedaan pekerjaan logis antarperlakuan jauh lebih besar daripada perbedaan waktunya. Pada revisi
satu sel, B0 dan B3 mengevaluasi tepat satu sel, sedangkan B1 dan B2 menghitung ulang seluruh 5.378
sel (Gambar G3). Penghematan sebesar 5.378 kali dalam pekerjaan logis tersebut tidak muncul pada
waktu, dan hanya sebagian muncul pada ruang.

### 4.3.2 Rilis nyata memberi urutan biaya yang sama

Karena besaran revisi tersuntik ditentukan peneliti, keempat perlakuan juga diuji pada revisi yang
benar-benar diterbitkan produsen. Keempat rilis yang membangun panel diterapkan satu per satu dalam
tiga repetisi. Ketiga kedatangan terakhir menimpa 1.605 baris, dan 43 di antaranya benar-benar
mengubah nilai yang diterbitkan; sisanya menuliskan ulang nilai yang sama dari sumber berbeda.

Total waktu untuk menerapkan keempat rilis adalah 15,050 detik pada B1, 47,688 detik pada B2, 52,184
detik pada B0, dan 88,929 detik pada B3 (Tabel T15). Urutan antarperlakuan sama persis dengan urutan
pada revisi tersuntik. Kesesuaian tersebut menunjukkan bahwa hasil sweep tidak bergantung pada sifat
buatan revisi yang disuntikkan.

Pada beban ini muncul satu pola yang tidak terlihat pada sweep. Kedatangan kedua hanya membawa 62
baris, tetapi pernyataan `MERGE` milik B0 memerlukan waktu lebih lama daripada `INSERT OVERWRITE`
milik B1 yang menuliskan 3.144 baris. Penulisan ulang seluruh keadaan pada skala ini lebih murah
daripada mencari dan menimpa sebagian kecilnya.

Ruang terujuk setelah keempat rilis berjumlah 312.945 byte pada B2, 329.276 byte pada B0, 837.744
byte pada B1, dan 839.008 byte pada B3. Keunggulan ruang B3 terhadap B1 yang terlihat jelas per
revisi karena itu menipis ketika rangkaian rilis sebagian besarnya menambah sel baru, bukan merevisi
sel lama.

### 4.3.3 Apa yang dibaca setiap pernyataan

Instrumentasi event log menutup metrik jumlah byte yang dibaca, yang pada tahap sweep belum dapat
diukur. Pengukuran dilakukan pada dua titik sweep dengan dua repetisi, dan angkanya dipisah menurut
asal bacaan, yaitu tabel milik perlakuan sendiri dan berkas staging (Tabel T16).

Perlakuan B1 dan B2 tidak membaca tabelnya sendiri sama sekali; seluruh 3.469.013 dan 3.489.279 byte
bacaannya berasal dari sumber staging. Perlakuan B0 membaca 594.148 byte dari tabelnya sendiri atas
10 berkas data, dan angka tersebut sama pada revisi satu sel maupun 38 sel. Perlakuan B3 membaca
paling banyak, yaitu 5.628.612 byte, dengan 90 berkas data berasal dari store append-only-nya.

Rencana eksekusi menjelaskan pola tersebut. Hanya B0 yang direncanakan sebagai `ReplaceData`, yaitu
penulisan ulang salin-saat-tulis yang menuntut penggabungan antara sumber dan berkas sasaran,
sedangkan B1 dan B2 direncanakan sebagai `OverwriteByExpression` dan B3 sebagai `AppendData`.
Perlakuan yang paling hemat menulis justru paling banyak membaca, dan bacaan tersebut tersebar pada
banyak berkas kecil.

### 4.3.4 Tidak ada titik impas di dalam rentang yang disapu

Aturan pencarian titik impas ditetapkan sebelum hasil dilihat, yaitu melaporkan besaran revisi
terkecil ketika pendekatan inkremental berhenti lebih murah daripada pembanding, dan menyatakan
secara eksplisit bila tidak ada titik silang. Hasilnya, **tidak ada satu pun titik silang pada
keenam perbandingan**, baik pada ukuran waktu maupun ukuran byte (Tabel T10).

Urutan antarperlakuan stabil pada keenam titik. Pada ukuran waktu, B1 lebih murah daripada B3 di
seluruh rentang; pada ukuran byte, B3 lebih murah daripada B1 di seluruh rentang. Terhadap B0 dan
B2, B3 lebih mahal pada kedua ukuran di seluruh rentang.

Sebuah tren hanya dinyatakan ada apabila rentang terukur pada titik terkecil dan titik terbesar
tidak bertumpang tindih dan mediannya bergerak satu arah pada keenam titik. Seluruh deret waktu
gagal memenuhi syarat kedua, sehingga tidak ada proyeksi waktu yang dilaporkan. Konsekuensinya lebih
tegas daripada sekadar tidak ditemukannya titik impas: karena waktu tidak bergantung pada besaran
revisi, tidak ada besaran revisi yang dapat menghasilkan titik silang, dan yang dapat mengubahnya
hanya ongkos tetap, yaitu kebijakan pemeliharaan atau ongkos tetap per pernyataan.

Pada ukuran byte, satu proyeksi dilaporkan dengan status di luar rentang terukur: B3 baru berhenti
lebih murah daripada B1 apabila satu revisi menyentuh sekitar 9.785 sel, sementara seluruh panel
hanya berisi 5.378 sel. Angka tersebut bukan titik impas terukur dan tidak dipakai sebagai jawaban
P3; fungsinya menunjukkan seberapa jauh titik silang itu berada dari beban yang benar-benar ada.

## 4.4 Kemampuan memanggil ulang angka terbit

Prosedur audit sepuluh langkah yang dibekukan pada tahap sebelumnya dijalankan pada dua skala beban.
Pada fixture bukti berisi 38 permintaan, B1 dan B3 memanggil ulang seluruhnya sedangkan B0 dan B2
memanggil ulang 0,3684 bagian. Pada panel provinsi berisi 6.983 permintaan, B1 dan B3 tetap
memanggil ulang seluruhnya, sedangkan B0 dan B2 memanggil ulang 0,7702 bagian (Tabel T13, Gambar G4
dan G5).

Perbedaan antara kedua skala tersebut perlu dibaca dengan hati-hati. Fixture memang dipilih karena
setiap selnya direvisi, sehingga proporsi kehilangannya jauh lebih besar. Pada panel yang sebagian
besar selnya hanya terbit sekali, proporsi kehilangan turun menjadi sekitar seperempat. Kedua angka
merupakan sifat beban kerja, bukan sifat umum arsip statistik resmi.

Jumlah kegagalan B0 dan B2 pada panel sama, yaitu 1.605 permintaan, tetapi himpunan yang hilang
berbeda arah. Perlakuan B0 kehilangan angka lama karena ditimpa vintage yang datang kemudian,
sedangkan B2 kehilangan angka baru karena sumbernya memperoleh skor kepercayaan lebih rendah.
Keduanya kehilangan seperempat arsip angka terbit, tetapi seperempat yang berlawanan.

Tingkat keberhasilan saja tidak cukup untuk menilai kerugiannya. Dari 1.605 kegagalan tersebut,
hanya 43 yang membawa nilai berbeda dari nilai yang kini disajikan perlakuan itu; 1.562 sisanya
merupakan baris dengan nilai identik dari sumber lain. Empat puluh tiga angka itulah kerugian
reproducibility yang sebenarnya, dan seluruhnya tercatat baris per baris beserta nilai penggantinya
serta locator rekaman sumbernya.

## 4.5 Kegagalan yang tidak muncul pada tingkat keberhasilan

Satu bentuk kegagalan tidak terlihat pada metrik keberhasilan sama sekali, karena permintaannya
memang terjawab. Perlakuan B2 memilih sumber menurut skor kepercayaan dan bukan menurut kebaruan,
sehingga pada 39 sel ia menyajikan nilai yang sudah digantikan produsen dengan nilai berbeda.
Permintaan atas angka tersebut berhasil, tetapi angka yang dikembalikan bukan angka mutakhir.

Perlakuan B0, B1, dan B3 tidak mengalami hal ini karena ketiganya menyajikan vintage terbaru.
Temuan tersebut memperluas hasil pada fixture, yang menemukan pola serupa pada 10 dari 14 sel, ke
skala panel.

Seluruh kasus kegagalan terdokumentasi sebagai 125 baris bukti yang memuat nilai yang hilang, nilai
penggantinya, selisihnya, serta artefak dan locator sumbernya, sehingga setiap kasus dapat diperiksa
tanpa membuka pipeline.

## 4.6 Propagasi revisi pada semesta bersumber tunggal

Tingkat propagasi revisi bernilai 1,0000 untuk keempat perlakuan pada seluruh titik sweep. Nilai
tersebut merupakan konsekuensi semesta sweep, bukan temuan tentang kebijakan pemilihan sumber:
ke-38 sel semestanya hanya dilayani satu sumber, sehingga B2 tidak pernah menghadapi pilihan dan
tidak pernah menahan revisi.

Perilaku menahan revisi pada B2 terbukti pada beban validasi yang bersumber majemuk, yaitu 8 dari 28
revisi yang tersaji. Kedua hasil tersebut tidak boleh dibaca sebagai satu rangkaian, dan
perbandingan langsung di antara keduanya tidak dilakukan.

## 4.7 Stabilitas pengukuran

Seluruh 40 titik pengukuran diperiksa dengan aturan yang ditetapkan lebih dahulu, yaitu sebaran fase
tulis melebihi 20 persen mediannya. Enam titik melewati ambang tersebut dan diukur ulang dengan tiga
repetisi tambahan, sehingga 20 titik memperoleh enam repetisi.

Delapan belas titik tetap berada dalam pita lima persen dan dua bergeser di luarnya, dengan
pergeseran terbesar 0,0901. Keduanya berada pada pernyataan tulis berdurasi dua sampai empat detik,
dan tidak satu pun mengubah urutan biaya antarperlakuan maupun kesimpulan pada bagian sebelumnya.
Median yang telah dilaporkan tidak diganti; median gabungan dilaporkan berdampingan dan koreksinya
dicatat pada decision log.

---

## Angka yang dipakai pada bagian ini

| Kalimat | Nilai | `metric_id` |
|---|---|---|
| Kejadian ketidaksesuaian yang diklasifikasikan | 123 | `p1_classified_events` |
| Kejadian dengan sebab inti terkonfirmasi | 96 (0,7805) | `p1_confirmed_core_events`, `p1_confirmed_core_share` |
| Jejak revisi yang dibekukan | 14 | `p1_revision_traces` |
| Vintage, observasi, sel pada fixture | 3, 38, 14 | `p2_vintages`, `p2_observations`, `p2_stable_cells` |
| Baris state as-of B3 yang sama dengan snapshot B1 | 42 | `p2_b3_asof_rows` |
| Observasi dan sel panel sweep | 6.983 dan 5.378 | `p3_sweep_panel_observations`, `p3_sweep_panel_cells` |
| Titik sweep | 6 | `p3_sweep_points` |
| Waktu total pada revisi 1 sel | 24,652; 10,056; 24,616; 38,007 | `p3_b0_sweep_1_total_seconds` dst. |
| Waktu total pada revisi 38 sel | 24,861; 10,068; 23,052; 35,626 | `p3_b0_sweep_38_total_seconds` dst. |
| Ongkos waktu tetap per revisi | 25,23; 10,15; 23,91; 37,44 | `p3_b0_fixed_seconds` dst. |
| Byte per sel direvisi | 31,3; 36,1; 11,9; 78,8 | `p3_b0_bytes_per_cell` dst. |
| Pertambahan byte pada revisi 1 sel | 13.279; 468.313; 25.883; 49.262 | `p3_b0_sweep_1_delta_bytes` dst. |
| Pertambahan byte pada revisi 38 sel | 14.459; 469.682; 26.363; 52.873 | `p3_b0_sweep_38_delta_bytes` dst. |
| Sel yang dievaluasi pada revisi 1 sel | 1; 5.378; 5.378; 1 | `p3_b0_sweep_1_cells_evaluated` dst. |
| Nilai terbit yang benar-benar berubah pada rilis nyata | 43 | `p3_real_value_revisions` |
| Waktu keempat rilis nyata | 52,184; 15,050; 47,688; 88,929 | `p3_b0_real_releases_total_seconds` dst. |
| Byte terujuk setelah rilis terakhir | 329.276; 837.744; 312.945; 839.008 | `p3_b0_real_releases_referenced_bytes` dst. |
| Byte yang dibaca pada revisi 38 sel | 1.111.882; 3.469.013; 3.489.279; 5.628.612 | `s2_b0_sweep_038_bytes_read` dst. |
| Operator puncak rencana eksekusi | ReplaceData; OverwriteByExpression; OverwriteByExpression; AppendData | `p3_plan_b0` dst. |
| Titik impas pada keenam perbandingan | none | `p3_breakeven_b3_b1_waktu` dst. |
| Proyeksi titik silang byte B3 terhadap B1 | 9.785 | `p3_projected_crossing_b3_byte` |
| Recall panel | 0,7702; 1,0000; 0,7702; 1,0000 | `p4_b0_panel_recall` dst. |
| Kegagalan panel | 1.605; 0; 1.605; 0 | `p4_b0_panel_failures` dst. |
| Kegagalan material | 43 pada B0 dan 43 pada B2 | `p4_b0_material_failures`, `p4_b2_material_failures` |
| Sel yang disajikan B2 dengan nilai usang | 39 | `p4_b2_superseded_serving_cells` |
| Kasus kegagalan yang didokumentasikan | 125 | `p4_failure_cases` |
| Propagasi revisi pada sweep | 1,0000 keempatnya | `b2_sweep_propagation_b0` dst. |
| Propagasi B2 pada beban validasi | 0,2857 | `b2_propagation_b2` |
| Titik diperiksa, meragukan, diulang, stabil, bergeser | 40; 6; 20; 18; 2 | `p3_points_checked` dst. |
| Pergeseran median terbesar | 0,0901 | `p3_largest_median_shift` |

Angka recall fixture 0,3684 berasal dari `p4_b0_success_rate` dan `p4_b2_success_rate`. Proporsi
pemeliharaan sebesar 56 sampai 59 persen berasal dari kolom `maintenance_share` pada
`p3-ongkos/h14c-cost-decomposition.csv`. Jumlah 1.605 baris tertimpa dan 1.562 duplikat nilai berasal
dari `p3-ongkos/h12-arrival-cost.csv` dan `p4-reproducibility/h13c-failure-profile.csv`. Angka 10
dari 14 sel pada fixture berasal dari `b2_selected_non_latest`. Rincian 594.148 byte atas 10 berkas
data pada B0 dan 90 berkas data pada B3 berasal dari `p3-ongkos/h14-read-summary.csv`, sedangkan
jumlah 3.144 baris pada kedatangan kedua B1 berasal dari `p3-ongkos/h12-arrival-cost.csv`.

## Tabel dan gambar yang dirujuk

| ID | Isi | Berkas |
|---|---|---|
| T2, T3 | ketidaksesuaian antarsumber dan distribusi sebabnya | `p1-karakterisasi/` |
| T5 | rekonstruksi state per rilis B3 terhadap snapshot B1 | `p2-representasi/h9-b3-asof-states.csv` |
| T8 | waktu penghitungan ulang per titik sweep | `results/processed/h15-table-t8.csv` |
| T9 | pertambahan byte per titik sweep | `results/processed/h15-table-t9.csv` |
| T10 | titik impas dan syaratnya | `results/processed/h15-table-t10.csv` |
| T13 | recall pada kedua skala | `results/processed/h15-table-t13.csv` |
| T15 | ongkos keempat rilis nyata | `results/processed/h15-table-t15.csv` |
| T16 | byte yang dibaca dan rencana eksekusi | `results/processed/h15-table-t16.csv` |
| G1–G5 | data gambar dan berkas gambar terender | `results/processed/h15-figure-data.csv`, `manuscript/figures/` |

## Yang belum masuk draf ini

Pembahasan dan Kesimpulan belum ditulis dan berada di luar jendela tiga minggu ini. Bagian Hasil di
atas sengaja dibatasi pada pelaporan bukti; penjelasan mekanistik yang lebih jauh, perbandingan
dengan literatur, serta implikasinya dikerjakan pada bagian Pembahasan.
