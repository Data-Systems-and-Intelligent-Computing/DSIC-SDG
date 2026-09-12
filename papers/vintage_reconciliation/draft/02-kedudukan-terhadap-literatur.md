# 2. Kedudukan terhadap Literatur

*Draf H10 Jalur C, 12 September 2026. Status verifikasi setiap sumber ada di
`docs/research/related-work.md`; ringkasannya di akhir berkas.*

## 2.1 Perhitungan indikator SDG dari data terbuka yang heterogen

Upaya menghitung indikator SDG dari sumber terbuka yang tersebar sudah berjalan beberapa tahun
terakhir. SustainGraph membangun knowledge graph untuk melacak kemajuan dan keterkaitan antartarget
SDG (Fotopoulou dkk., 2022), sedangkan Jiang dan Johnson (2023) menyusun pendekatan berbasis aturan
untuk menemukan data yang relevan bagi indikator tertentu. Keduanya bekerja pada persoalan
penemuan dan penautan, yaitu bagaimana sebuah dataset dikenali sebagai calon masukan bagi sebuah
indikator.

Pekerjaan yang paling dekat dengan penelitian ini adalah SDG-KG (Benjira dkk., 2025). Kerangka
tersebut mempertemukan graf metadata yang diturunkan dari sumber data dengan graf indikator SDG
yang diturunkan dari repositori metadata indikator PBB, memakai bantuan LLM untuk penyelarasan
skema, lalu menghasilkan rencana eksekusi yang diterjemahkan menjadi kode Python. Ketika beberapa
sumber memberikan nilai yang berbeda, konflik diselesaikan dengan skor kepercayaan yang
menggabungkan kemiripan spasial, temporal, dan kontekstual dengan reliabilitas serta kelengkapan
sumber, kemudian satu sumber dipilih. Versi jurnalnya memperluas sisi pemetaan otomatis antara
indikator dan data terbuka (Benjira dkk., 2025b).

Dua batas melekat pada jalur ini, dan salah satunya dinyatakan penulisnya sendiri. SDG-KG bekerja
pada tingkat metadata dan tidak memproses aliran data, sehingga tidak memuat evaluasi performa,
studi skalabilitas, maupun pembahasan penyimpanan fisik. Batas kedua bersifat konseptual. Memilih
satu sumber ketika terjadi konflik berarti membuang nilai dari sumber yang tidak terpilih. Untuk
data terbuka yang kualitasnya memang beragam, keputusan tersebut masuk akal. Untuk statistik resmi,
yang dibuang justru informasi yang ingin dipelajari.

Konsekuensi pilihan tersebut dapat diukur, dan pada penelitian ini memang diukur. Perlakuan B2
mereplikasi pola pemilihan sumber tunggal memakai skor kepercayaan yang dibekukan. Hasilnya, 10 dari
14 sel menyajikan nilai yang bukan berasal dari vintage terbaru, dan pada beban revisi tersuntik
hanya 8 dari 28 revisi yang sampai ke keadaan serving, atau tingkat propagasi 0,2857. Angka tersebut
bukan indikasi kesalahan implementasi, melainkan sifat kelas kebijakan yang memilih satu sumber
sebelum perhitungan.

## 2.2 Truth discovery dan data fusion

Bidang truth discovery menyediakan dasar formal bagi keputusan semacam itu. Dong dkk. (2015)
merumuskan persoalan data fusion sebagai penyelesaian konflik dari banyak sumber, dan survei
berikutnya memetakan keluarga metode yang menaksir reliabilitas sumber sambil menyimpulkan nilai
yang benar (Li dkk., 2016; survei IEEE Transactions on Big Data, 2025). Asumsi dasarnya konsisten
di seluruh literatur ini, yaitu terdapat satu nilai benar yang tersembunyi dan sumber-sumbernya
tidak seluruhnya dapat dipercaya.

Asumsi tersebut tidak berlaku pada statistik resmi. Ketika WebAPI BPS dan kompilasi indikator TPB
memberikan angka berbeda untuk indikator, wilayah, dan tahun yang sama, tidak ada sumber yang salah.
Keduanya diterbitkan produsen yang sama melalui jalur yang sama-sama sah, dan perbedaannya berasal
dari vintage rilis, perubahan metodologi, atau granularitas yang berbeda. Bukti empiris pada
penelitian ini mendukung pembacaan tersebut: 96 dari 123 kejadian ketidaksesuaian dapat dipastikan
berasal dari salah satu dari ketiga sebab itu.

Karena itu bidang truth discovery diperlakukan sebagai pembanding, bukan sebagai fondasi. Kebaruan
tidak diklaim pada algoritmanya. Yang diambil hanyalah polanya, untuk dijalankan sebagai perlakuan
B2 sehingga konsekuensinya dapat diukur pada beban yang sama dengan perlakuan lain.

## 2.3 Vintage dan revisi pada statistik resmi

Pada sisi statistik resmi, persoalan revisi sudah lama dirumuskan. Pedoman OECD dan Eurostat tentang
kebijakan dan analisis revisi menetapkan bagaimana revisi diumumkan dan dianalisis, sedangkan
Statistics Canada menerbitkan real-time data tables yang memuat seluruh revisi satu titik data
sepanjang waktu. Literatur ekonometrik memakai vintage untuk menguji stabilitas peramalan (ECB
Working Paper 846, 2007) dan untuk menilai pengaruh revisi terhadap model (Statistical Methods &
Applications, 2014), dan perkakasnya terus dikembangkan, termasuk paket `reviser` untuk
menganalisis vintage deret waktu waktu nyata.

Dua istilah kunci dari literatur ini dipakai langsung pada penelitian ini. Vintage adalah keadaan
sebuah angka pada saat ia dirilis, sedangkan revision triangle adalah matriks yang menunjukkan
bagaimana taksiran satu periode berubah pada rilis berikutnya.

Batasnya terletak pada objek yang digarap. Literatur tersebut bekerja pada agregat yang sudah
terbit, umumnya deret waktu berukuran kecil, di lingkungan statistik dan ekonometrik. Pipeline yang
memproduksi angka tersebut tidak menjadi objek kajian, sehingga pertanyaan tentang berapa waktu dan
ruang yang dibutuhkan untuk mempertahankan riwayat angka tidak pernah muncul. Justru pertanyaan
itulah yang menjadi pokok penelitian ini.

## 2.4 Lakehouse, versioning, dan pemeliharaan inkremental

Mekanisme untuk menyimpan dan memelihara riwayat tersedia matang di lapisan lakehouse. Format tabel
terbuka menyediakan snapshot dan time travel, dan penelitian sistem sudah membandingkan
karakteristik penyimpanannya secara eksperimental (Jain dkk., 2023; survei dan studi eksperimental
lakehouse pada Information Systems, 2025). Pemeliharaan view secara inkremental juga sudah menjadi
kemampuan produk dan sistem sumber terbuka, dengan refresh yang dapat bersifat no-op, inkremental,
atau penuh.

Persoalannya bukan ketersediaan mekanisme, melainkan apa yang direkam mekanisme tersebut. Snapshot
tabel merekam kapan sebuah baris ditulis, sedangkan vintage indikator merekam kapan produsen
merilis angkanya. Selama data hanya bertambah, kedua sumbu waktu itu berjalan sejajar dan
perbedaannya tidak terasa. Ketika sumber direvisi secara surut, keduanya berpisah, dan snapshot
tabel tidak lagi dapat menjawab pertanyaan tentang nilai pada suatu rilis.

Perbedaan tersebut bukan argumen di atas kertas. Pada penelitian ini, katalog Iceberg yang semula
menyimpan registrasi tabel secara in-memory kehilangan seluruh registrasi setelah node dinyalakan
ulang, meskipun berkas datanya masih utuh di object storage. Kemampuan B1 memanggil angka lama
bergantung pada metadata snapshot di katalog, sehingga kemampuan itu hilang tanpa meninggalkan tanda
apa pun pada data. Perlakuan B3 tidak terpengaruh pada titik yang sama karena pemanggilan ulangnya
bersandar pada kunci `(cell_id, vintage_id)` yang tersimpan sebagai baris, bukan pada snapshot
tabel.

Seperti halnya truth discovery, incremental view maintenance dipakai sebagai mekanisme dan
pembanding. Kebaruan tidak diklaim di sini.

## 2.5 Provenance dan reproducibility pipeline

Kemampuan menghasilkan ulang angka yang pernah terbit bergantung pada provenance yang lengkap.
Penangkapan provenance secara transparan pada pipeline data science sudah dikerjakan sejak URSPRUNG
(Rupprecht dkk., 2020), dan pekerjaan berikutnya memperluasnya ke pipeline machine learning ujung ke
ujung serta ke pengelolaan provenance berbagai granularitas. Prinsip yang mendasarinya sudah lama
dirumuskan sebagai syarat penelitian komputasi yang dapat direproduksi (Peng, 2011).

Penelitian ini mengikuti garis tersebut dan menerapkannya pada rantai yang spesifik, yaitu dari
manifest sumber, vintage, versi transformasi, sel indikator, metrik, sampai tabel dan gambar.
Kelengkapan rantai tersebut diukur, bukan diasumsikan: 152 path lengkap terbentuk untuk keempat
perlakuan dengan kelengkapan 1,0000. Audit reproducibility juga dihitung ulang dari keadaan setiap
perlakuan alih-alih dipercaya dari label sebelumnya.

## 2.6 Posisi penelitian ini

Dua literatur yang sudah sama-sama matang belum pernah dipertemukan. Statistik resmi memiliki
konsep vintage yang mapan tetapi menerapkannya pada agregat yang sudah terbit, tanpa memperhitungkan
ongkos komputasi. Sistem data memiliki mesin lengkap untuk versioning dan pemeliharaan inkremental
tetapi memodelkan perbedaan antarsumber sebagai kesalahan yang harus diselesaikan, model yang keliru
untuk statistik resmi.

Penelitian ini menempati ruang di antara keduanya, dengan tiga pembeda terhadap pekerjaan terdekat.
Pertama, pekerjaannya berada pada lapisan fisik, sehingga yang diukur adalah waktu, ruang, dan
kemampuan menghasilkan ulang angka, bukan kemampuan memetakan skema. Kedua, perbedaan antarsumber
diperlakukan sebagai vintage yang harus dipertahankan, bukan sebagai konflik yang harus dipilih
salah satunya. Ketiga, pengujian dilakukan pada statistik resmi nasional Indonesia dengan revisi
yang benar-benar terjadi, bukan pada data terbuka Eropa.

Batas klaimnya dinyatakan di muka. Kebaruan tidak diklaim pada algoritma truth discovery maupun pada
incremental view maintenance. Klaim skalabilitas dan performa juga tidak dibuat, karena seluruh
pengukuran berjalan pada satu node kecil. Yang diklaim adalah perlakuan vintage indikator sebagai
objek kelas satu di dalam lakehouse beserta pengukuran ongkos mempertahankannya.

---

## Sumber yang disitasi pada bagian ini

Seluruh entri diambil dari `docs/research/related-work.md`. Kolom terakhir menyatakan sejauh mana
sumber sudah diperiksa: `penuh` berarti naskahnya dibaca langsung, `metadata` berarti judul, venue,
tahun, dan abstraknya terverifikasi dari sumber resmi tetapi naskahnya belum dibaca utuh.

| Sitasi pada draf | Sumber | Venue | Verifikasi |
|---|---|---|---|
| Benjira dkk., 2025 | *SDG-KG: A Framework to Compute SDG Indicators with Open Data* | PVLDB 18(12):5367–5370 | penuh |
| Benjira dkk., 2025b | *Automated mapping between SDG indicators and open data: An LLM-augmented knowledge graph approach* | Data & Knowledge Engineering 156, 102405 | metadata |
| Fotopoulou dkk., 2022 | *SustainGraph* | Frontiers in Environmental Science 10 | metadata |
| Jiang & Johnson, 2023 | *Data Discovery for the SDGs: A Systematic Rule-based Approach* | GoodIT'23, 384–390 | metadata |
| Dong dkk., 2015 | *Data Fusion: Resolving Conflicts from Multiple Sources* | Springer / arXiv:1503.00310 | metadata |
| Li dkk., 2016 | *A Survey on Truth Discovery* | ACM SIGKDD Explorations | metadata |
| Survei IEEE TBD, 2025 | *A Survey on Truth Discovery: Concepts, Methods, Applications, and Opportunities* | IEEE TBD 11(2):314–332 | metadata |
| Pedoman OECD/Eurostat | *Guidelines on Revisions Policy and Analysis* | Pedoman | metadata |
| Statistics Canada | *Real-time data tables* | Produk statistik | metadata |
| ECB Working Paper 846, 2007 | *Information combination and forecast (st)ability: Evidence from vintages of time-series data* | ECB Working Paper Series | metadata |
| Statistical Methods & Applications, 2014 | *Revisions in official data and forecasting* | Statistical Methods & Applications | metadata |
| `reviser` 0.2.0 | *Analyzing Revisions in Real-Time Time Series Vintages* | rOpenSci | metadata |
| Jain dkk., 2023 | *Analyzing and Comparing Lakehouse Storage Systems (LHBench)* | CIDR | metadata |
| Information Systems, 2025 | *Data Lakehouse: A survey and experimental study* | Information Systems 127:102460 | metadata |
| Microsoft Fabric | *Materialized Lake Views — optimal refresh* | Dokumentasi produk | metadata |
| Rupprecht dkk., 2020 | *URSPRUNG* | PVLDB | metadata |
| Peng, 2011 | *Reproducible Research in Computational Science* | Science 334(6060) | metadata |

## Yang harus diselesaikan sebelum submit

1. Empat sumber disitasi memakai venue karena `related-work.md` tidak mencatat nama penulisnya,
   yaitu ECB Working Paper 846 (2007), *Revisions in official data and forecasting* (2014), survei
   truth discovery IEEE TBD (2025), dan survei lakehouse Information Systems (2025). Nama penulis
   wajib diambil dari halaman penerbit sebelum sitasi diubah menjadi bentuk penulis-tahun.
   [Sumber belum mendukung penulisan nama penulis]
2. Tahun dan nomor halaman pedoman OECD/Eurostat belum tercatat pada `related-work.md` dan harus
   dilengkapi.
3. Sumber berstatus `metadata` yang klaimnya dipakai secara substantif, khususnya SDG-KG versi
   jurnal dan survei truth discovery 2025, sebaiknya dinaikkan ke `penuh` sebelum submit.

## Angka yang dipakai pada bagian ini

| Kalimat | Nilai | `metric_id` |
|---|---|---|
| Sel B2 yang menyajikan nilai bukan vintage terbaru | 10 dari 14 | `b2_selected_non_latest` |
| Tingkat propagasi revisi B2 | 0,2857 | `b2_propagation_b2` |
| Kejadian sebab inti terkonfirmasi | 96 dari 123 | `p1_confirmed_core_events`, `p1_classified_events` |
| Path lineage lengkap | 152 | `p4_lineage_paths` |
| Kelengkapan lineage | 1,0000 | `p4_lineage_completeness` |

Temuan katalog in-memory yang menghapus registrasi tabel berasal dari
`docs/research/h10-storage-recall.md`, bagian temuan infrastruktur.
