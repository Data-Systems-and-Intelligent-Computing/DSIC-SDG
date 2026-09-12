# 1. Pendahuluan

*Draf H10 Jalur C, 12 September 2026. Seluruh angka berasal dari `data/angka-kunci.csv`; pemetaannya
ada di akhir berkas.*

## 1.1 Latar belakang

Indikator Tujuan Pembangunan Berkelanjutan di Indonesia diterbitkan Badan Pusat Statistik melalui
beberapa jalur resmi yang berjalan berdampingan. WebAPI menyediakan nilai tabel dinamis yang
diperbarui mengikuti pemutakhiran basis data, sedangkan kompilasi indikator TPB terbit sebagai
publikasi tahunan yang isinya beku pada tanggal rilis. Keduanya sah, keduanya diproduksi produsen
yang sama, dan keduanya dirujuk pengguna yang sama.

Pada penelitian ini kedua jalur tersebut ditarik dan dibandingkan sel per sel. Dari 1.435 sel yang
beririsan antara snapshot WebAPI dan lampiran publikasi 2024, terdapat 33 sel yang nilainya berbeda.
Perbandingan antarrilis publikasi membentuk 4.608 kunci sel dan menemukan delapan perbedaan nilai
yang tersebar pada tiga domain, yaitu energi, ekonomi, dan ekologi. Perbedaan semacam ini tidak
dapat diselesaikan dengan menyatakan salah satu sumber keliru, karena keduanya merupakan statistik
resmi yang diterbitkan produsen yang berwenang.

Penyebabnya dapat dipisahkan. Pada 123 kejadian ketidaksesuaian yang diklasifikasikan memakai
delapan aturan yang ditetapkan di muka, 96 kejadian atau 78,05 persen dapat dipastikan berasal dari
salah satu dari tiga sebab, yaitu revisi vintage, perubahan metodologi, dan perbedaan granularitas.
Rinciannya adalah 82 kejadian granularitas, 13 kejadian vintage, dan satu kejadian metodologi yang
terkonfirmasi, sedangkan 19 kejadian lain merupakan selisih pembulatan yang sengaja dikeluarkan dari
hitungan. Sisanya berhenti sebagai kandidat karena snapshot historis yang diperlukan untuk
memastikannya tidak tersedia.

Kondisi terakhir itulah yang menjadi persoalan. Nilai lama pada WebAPI ditimpa oleh nilai terbaru,
sehingga angka yang pernah dipublikasikan tidak lagi dapat dihasilkan ulang dari sumbernya.
Pedoman revisi statistik resmi justru menuntut kemampuan sebaliknya, yaitu kemampuan menunjukkan
bagaimana sebuah taksiran berubah dari satu rilis ke rilis berikutnya. Selama riwayat itu hanya
hidup di dalam publikasi PDF yang terbit setahun sekali, kemampuan tersebut bergantung pada arsip
dokumen, bukan pada sistem yang memproduksi angkanya.

## 1.2 Pendekatan yang sudah tersedia dan keterbatasannya

Dua bidang sudah menggarap sebagian persoalan ini, tetapi dari arah yang berbeda dan tanpa pernah
bertemu.

Dari sisi sistem data, perhitungan indikator SDG dari sumber terbuka yang heterogen sudah
didemonstrasikan, terbaru oleh SDG-KG yang mempertemukan graf metadata sumber dengan graf indikator
SDG dan menyelesaikan konflik antarsumber memakai skor kepercayaan. Pendekatan tersebut bekerja pada
tingkat metadata dan, sebagaimana dinyatakan penulisnya sendiri, tidak memproses aliran data serta
tidak memuat evaluasi performa maupun pembahasan penyimpanan fisik. Keputusan memilih satu sumber
juga membuang perbedaan yang justru ingin dipelajari pada kasus statistik resmi.

Dari sisi statistik resmi, konsep vintage dan revision triangle sudah mapan dan dituangkan dalam
pedoman maupun produk data waktu nyata. Literatur tersebut bekerja pada agregat yang sudah terbit,
biasanya berupa deret waktu berukuran kecil, dan tidak menyentuh pipeline yang memproduksinya.
Ongkos komputasi untuk mempertahankan riwayat angka karena itu tidak pernah masuk hitungan.

Mekanisme teknis untuk menyimpan riwayat sebenarnya tersedia di lapisan lakehouse. Format tabel
terbuka seperti Apache Iceberg menyediakan snapshot dan time travel, sedangkan pemeliharaan view
secara inkremental sudah lama matang. Persoalannya, snapshot tabel merekam kapan sebuah baris
ditulis, bukan kapan produsen merilis angkanya. Ketika sumber direvisi secara surut, kedua sumbu
waktu tersebut berpisah, dan snapshot tabel tidak lagi dapat menjawab pertanyaan tentang nilai pada
suatu rilis.

## 1.3 Pertanyaan penelitian

Berdasarkan kondisi tersebut, penelitian ini menanyakan berapa ongkos mempertahankan indikator SDG
yang tetap dapat direproduksi dan ditelusuri ketika beberapa sumber resmi memberikan nilai berbeda,
serta pada besaran revisi seperti apa penghitungan ulang inkremental berhenti lebih murah daripada
penghitungan ulang penuh. Pertanyaan tersebut diuraikan menjadi empat sub-pertanyaan.

**P1.** Bentuk ketidaksesuaian apa yang benar-benar muncul antarsumber resmi BPS pada lima domain,
dan berapa proporsi yang berasal dari revisi vintage dibanding perbedaan metodologi dan perbedaan
granularitas.

**P2.** Dapatkah ketidaksesuaian tersebut direpresentasikan sebagai vintage indikator di atas format
tabel terbuka, sehingga nilai yang pernah dipublikasikan tetap dapat dipanggil ulang tanpa menyimpan
salinan penuh setiap rilis.

**P3.** Berapa waktu dan ruang yang dibutuhkan untuk menghitung ulang indikator ketika satu sumber
direvisi, dan pada besaran revisi seperti apa pendekatan inkremental berhenti terbayar.

**P4.** Apakah angka yang pernah dilaporkan dapat dihasilkan ulang persis setelah sumbernya direvisi,
dan pada kondisi apa ia gagal.

P4 diperlakukan sebagai syarat kelayakan. Hasil yang lebih murah tetapi gagal menghasilkan ulang
angka lama tidak dihitung sebagai keuntungan.

## 1.4 Rancangan pengujian

Empat perlakuan penyimpanan dibandingkan pada beban revisi yang sama. B0 menyimpan hanya nilai
terkini dan mewakili praktik yang lazim. B1 menyimpan setiap rilis sebagai snapshot keadaan penuh
dan menjadi batas atas ongkos ruang. B2 memilih satu sumber berdasarkan skor kepercayaan dan
mewakili pendekatan pemilihan sumber tunggal. B3, yang diusulkan penelitian ini, menyimpan vintage
indikator sebagai dimensi eksplisit dan menghitung ulang secara inkremental berdasarkan lineage sel
yang benar-benar terpengaruh.

Beban revisi berasal dari dua sumber. Revisi nyata diambil dari perbedaan antarrilis yang
benar-benar terjadi, dan 14 jejak revisi dengan 38 baris vintage dibekukan sebagai basis bukti.
Revisi tersuntik dengan besaran terkendali dipakai untuk mencari titik impas, karena besaran revisi
nyata tidak dapat diatur. Seluruh konfigurasi eksperimen dibekukan sebelum eksperimen utama
dijalankan.

## 1.5 Kontribusi

Penelitian ini memberikan empat kontribusi.

Pertama, karakterisasi empiris ketidaksesuaian antarsumber resmi BPS pada lima domain, lengkap
dengan aturan klasifikasi yang ditetapkan di muka dan proporsi sebab yang terukur.

Kedua, rancangan penyimpanan yang memperlakukan vintage indikator sebagai dimensi eksplisit di atas
format tabel terbuka. Pada workload nyata, 38 observasi dari tiga rilis diproyeksikan menjadi 14 sel
tanpa kehilangan provenance, dan ketiga keadaan per rilis dapat direkonstruksi dari kunci vintage.

Ketiga, pengukuran ongkos fisik keempat perlakuan pada perangkat keras yang sama. Ruang total
terukur berturut-turut 95.898 byte untuk B0, 190.261 byte untuk B1, 64.077 byte untuk B2, dan
240.884 byte untuk B3. Pengukuran waktu pada revisi satu sel memperlihatkan bahwa pada ukuran ini
ongkos satu revisi praktis merupakan ongkos satu commit Iceberg, bukan ongkos datanya: revisi satu
nilai pada B0 hanya mengubah 161 byte data tetapi menambah 23.915 byte metadata.

Keempat, audit reproducibility yang dihitung ulang dari keadaan setiap perlakuan, bukan dipercaya
dari label. B1 dan B3 memanggil ulang seluruh 38 angka terbit, sedangkan B0 dan B2 hanya 14 dari 38.
Hasil yang sama bertahan setelah katalog Iceberg di-restart dan setelah revisi tersuntik diterapkan
secara fisik.

Titik impas yang diminta P3 belum dapat dilaporkan pada draf ini. Sweep utama dijadwalkan setelah
konfigurasi eksperimen dibekukan, dan hasilnya menyusul. [Sumber belum mendukung klaim titik impas]

## 1.6 Batas klaim

Volume data pada penelitian ini kecil, dan hal tersebut merupakan konsekuensi domainnya. Indikator
SDG pada granularitas nasional sampai provinsi memang tidak pernah besar. Pertanyaan yang diajukan
menyangkut kebenaran, keterlacakan, dan ongkos pemeliharaan, bukan throughput, sehingga rancangannya
sengaja disusun agar tidak bergantung pada volume besar.

Seluruh pengukuran berjalan pada satu node dengan 2 vCPU dan RAM 7,7 GiB. Angka waktu karena itu
hanya boleh dibaca sebagai perbandingan antarperlakuan pada perangkat keras yang sama, dan tidak
pernah sebagai klaim performa maupun skalabilitas. Kebaruan juga tidak diklaim pada algoritma truth
discovery maupun pada incremental view maintenance, karena keduanya dipakai sebagai mekanisme dan
pembanding. Yang diklaim adalah perlakuan vintage indikator sebagai objek kelas satu di dalam
lakehouse beserta pengukuran ongkos mempertahankannya.

---

## Angka yang dipakai pada bagian ini

| Kalimat | Nilai | `metric_id` |
|---|---|---|
| Sel WebAPI vs TPB 2024 yang dibandingkan | 1.435 | `p1_main_compared_cells` |
| Sel yang nilainya berbeda | 33 | `p1_main_discrepant_cells` |
| Kunci sel perbandingan antarrilis | 4.608 | `p1_release_cell_keys` |
| Perbedaan nilai antarrilis | 8 | `p1_release_discrepancies` |
| Domain yang terdampak | 3 | `p1_release_discrepancy_domains` |
| Kejadian yang diklasifikasikan | 123 | `p1_classified_events` |
| Kejadian sebab inti terkonfirmasi | 96 | `p1_confirmed_core_events` |
| Proporsi sebab inti terkonfirmasi | 0,7805 | `p1_confirmed_core_share` |
| Kejadian granularitas, vintage, metodologi | 82, 13, 1 | `p1_granularity_observed`, `p1_vintage_observed`, `p1_methodology_observed` |
| Kejadian pembulatan yang dikeluarkan | 19 | `p1_rounding_or_presentation_observed` |
| Jejak revisi yang dibekukan | 14 | `p1_revision_traces` |
| Baris vintage pada jejak revisi | 38 | `p1_trace_vintage_rows` |
| Vintage, observasi, sel pada workload nyata | 3, 38, 14 | `p2_vintages`, `p2_observations`, `p2_stable_cells` |
| Ruang fisik B0, B1, B2, B3 | 95.898; 190.261; 64.077; 240.884 byte | `p3_b0_bytes_median`, `p3_b1_bytes_median`, `p3_b2_bytes_median`, `p3_b3_bytes_median` |
| Tingkat keberhasilan recall B0, B1, B2, B3 | 0,3684; 1,0000; 0,3684; 1,0000 | `p4_b0_success_rate`, `p4_b1_success_rate`, `p4_b2_success_rate`, `p4_b3_success_rate` |
| Recall setelah restart katalog | 14, 38, 14, 38 dari 38 | `p4_b0_recalled_after_restart` dst. |

Angka 161 byte data dan 23.915 byte metadata pada revisi satu nilai B0 berasal dari
`docs/research/h10b-injected-revision-physical.md`, bagian temuan. Spesifikasi node berasal dari
`docs/research/experiment-freeze.md` butir 7.
