# Ongkos Menerapkan Revisi Nyata (H12)

## Status

H12 mengukur apa yang sebenarnya dibayar setiap perlakuan ketika **rilis resmi yang benar-benar
terbit** datang satu per satu. Keempat rilis panel provinsi diterapkan berurutan pada keempat
perlakuan, masing-masing dengan mekanisme tulis dan pemeliharaan yang dibekukan pada H7 sampai H9,
lalu waktu per pernyataan serta keadaan dan ruang setelah setiap kedatangan dicatat.

Kontrak eksekusi ada di
[`contracts/h12-real-revision-cost.json`](../../contracts/h12-real-revision-cost.json). Jalankan
`make h12-measure` di host stack, lalu `make h12-run`.

## Mengapa ini diperlukan setelah H11

H11 menjawab pertanyaan yang terkontrol: berapa ongkos satu revisi berukuran `k` sel di atas panel
yang sudah jadi. Pertanyaan itu memerlukan revisi tersuntik, karena besaran revisi nyata tidak dapat
dikendalikan. Konsekuensinya, seluruh angka ongkos pada H11 berasal dari revisi buatan.

H12 menutup sisi lain pertanyaan yang sama. Panel provinsi dibangun oleh empat rilis resmi yang
benar-benar terbit, yaitu TPB 2024, TPB 2025, snapshot WebAPI H1, dan snapshot WebAPI H3, dan ketiga
kedatangan terakhir memang menimpa nilai yang sudah ada. Menerapkan keempat rilis itu satu per satu
merupakan beban revisi nyata, dengan besaran yang ditentukan BPS dan bukan oleh peneliti. Angka H12
karena itu dapat dibaca berdampingan dengan angka H11: mekanisme yang sama, node yang sama,
pemeliharaan yang sama, hanya sumber revisinya yang berbeda.

## Beban kerja

| Kedatangan | Sumber | Tanggal rilis | Baris masuk | Baris tertimpa | Nilai berubah | Timpa nilai sama |
|---:|---|---|---:|---:|---:|---:|
| 1 | `bps_tpb_2024` | 2024-12-31 | 1.560 | 0 | 0 | 0 |
| 2 | `bps_tpb_2025` | 2025-12-30 | 62 | 38 | 4 | 34 |
| 3 | `bps_webapi` (snapshot 14:04 UTC) | 2026-09-08 | 770 | 770 | 6 | 764 |
| 4 | `bps_webapi` (snapshot 23:38 UTC) | 2026-09-08 | 4.591 | 797 | 33 | 764 |

Kedatangan pertama membangun keadaan awal, dan ketiga kedatangan berikutnya membawa revisi nyata:
1.605 baris menimpa baris yang sudah ada, dan **43 di antaranya benar-benar mengubah nilai yang
diterbitkan**, sedangkan 1.562 sisanya menuliskan ulang nilai yang sama dari sumber yang berbeda.
Perbedaan tersebut penting untuk membaca hasilnya: sebagian besar pekerjaan tulis pada beban nyata
dihabiskan untuk nilai yang ternyata tidak berubah, dan tidak satu pun perlakuan mengetahui hal itu
sebelum menulis.

Beban ini identik dengan keadaan dasar H11, sehingga keadaan setelah kedatangan keempat wajib sama
dengan keadaan dasar sweep: B0 5.378 baris, B1 10.106 baris dalam empat snapshot, B2 5.378 baris,
store B3 6.983 baris, dan serving B3 5.378 baris.

## Yang diukur

Setiap repetisi membuang seluruh tabel beserta berkas fisiknya, membuatnya kembali, lalu menjalankan
satu sesi Spark SQL per perlakuan yang menerapkan kedatangan 1 sampai 4 berurutan. Di dalam sesi
tersebut setiap pernyataan dicatat waktunya, dan setelah setiap kedatangan dicatat jumlah baris, sel,
snapshot, serta byte data dan manifest yang masih dirujuk metadata. Setelah kedatangan terakhir,
seluruh objek tabel didaftar dari MinIO untuk memeriksa bahwa setiap objek yang dirujuk metadata
memang ada dengan ukuran yang sama, dan bahwa tidak ada objek tak terujuk yang ikut terhitung.

Pemeliharaan dijalankan **per kedatangan**, sama seperti pemeliharaan dijalankan per revisi pada
H10B dan H11, agar kedua pengukuran dapat dibandingkan. Keadaan yang harus dihasilkan setiap
kedatangan diturunkan dari katalog panel beku, bukan dari hasil pengukuran, sehingga selisih apa pun
menghentikan run.

## Hasil

Pengukuran dijalankan pada 12 September 2026 pukul 22:00:32 sampai 22:20:09 UTC, tiga repetisi
berurutan, dari commit bersih. Kesembilan invarian lolos, termasuk pemeriksaan bahwa keadaan setelah
kedatangan keempat sama persis dengan keadaan dasar H11 dan bahwa tidak ada objek tak terujuk yang
ikut dihitung. Marker:

```
H12_VERIFY|3|4|43|52.184|15.050|47.688|88.929|329276|837744|312945|839008|measured
```

### Ongkos seluruh rangkaian rilis

Waktu total median untuk menerapkan keempat rilis nyata, tulis ditambah pemeliharaan:

| Perlakuan | Total empat rilis | Tulis | Pemeliharaan |
|---|---:|---:|---:|
| B1 | 15,050 detik | 15,050 | 0 |
| B2 | 47,688 detik | 14,753 | 32,507 |
| B0 | 52,184 detik | 18,644 | 33,052 |
| B3 | 88,929 detik | 32,802 | 55,612 |

Kolom total adalah jumlah median tulis-plus-pemeliharaan tiap kedatangan, sedangkan kolom tulis dan
pemeliharaan adalah jumlah median masing-masing fase; keduanya dapat berselisih beberapa persepuluh
detik karena median tidak bersifat aditif. Pemeliharaan snapshot menghabiskan sekitar dua pertiga
waktu B0, B2, dan B3, dan nol pada B1 yang mekanismenya tidak menuntutnya.

Urutannya **sama persis** dengan urutan pada revisi tersuntik H11. Temuan H11 karena itu tidak
bergantung pada sifat revisi buatan: pada revisi yang benar-benar diterbitkan BPS pun B1 tercepat,
B3 termahal, dan pemeliharaan snapshot menghabiskan dua sampai tiga kali waktu penulisannya.

### Ongkos per rilis

| Kedatangan | Baris masuk | Nilai berubah | B0 | B1 | B2 | B3 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1.560 | 0 | 14,849 | 8,267 | 15,117 | 24,454 |
| 2 | 62 | 4 | 14,832 | 2,315 | 12,949 | 24,297 |
| 3 | 770 | 6 | 11,926 | 2,199 | 10,251 | 20,608 |
| 4 | 4.591 | 33 | 10,577 | 2,269 | 9,371 | 19,570 |

Satu angka pada tabel ini layak diperhatikan. Pada kedatangan kedua hanya 62 baris yang masuk dan 38
baris tertimpa, tetapi pernyataan `MERGE` B0 memerlukan 3,929 detik sedangkan `INSERT OVERWRITE` B1
yang menuliskan 3.144 baris hanya memerlukan 2,315 detik. Pada kedatangan keempat pola itu bertahan:
B0 menulis 3,197 detik untuk 4.591 baris masuk, B1 menulis 2,269 detik untuk 10.106 baris. **Pada
skala ini menulis ulang seluruh keadaan lebih murah daripada mencari dan menimpa sebagian kecilnya.**
Penyebabnya adalah `MERGE` dengan penulisan salin-saat-tulis, yang harus menggabungkan sumber dengan
berkas sasaran lalu menulis ulang berkas yang tersentuh, sedangkan `INSERT OVERWRITE` hanya menulis
berkas baru.

Kedatangan pertama lebih lambat untuk seluruh perlakuan karena sesi masih dingin; angka setelahnya
merupakan keadaan tunak.

### Ruang

Byte data dan manifest yang masih dirujuk metadata setelah tiap kedatangan:

| Kedatangan | B0 | B1 | B2 | B3 (store + serving) |
|---:|---:|---:|---:|---:|
| 1 | 121.407 | 124.697 | 133.286 | 256.218 |
| 2 | 134.128 | 275.268 | 146.070 | 328.109 |
| 3 | 156.186 | 448.003 | 146.660 | 429.175 |
| 4 | 329.276 | 837.744 | 312.945 | 839.008 |

Pertambahan per rilis memperlihatkan mekanismenya. B1 menambah 150.571, 172.735, lalu 389.741 byte,
karena setiap rilis menyimpan satu salinan penuh keadaan saat itu. B3 menambah 71.891, 101.066, lalu
409.833 byte, yaitu jauh lebih kecil pada rilis yang hanya menyentuh sedikit sel tetapi hampir sama
besar pada rilis terakhir yang membawa 4.591 baris baru.

Hasilnya, setelah keempat rilis nyata, total B3 dan B1 praktis sama besar, 839.008 berbanding 837.744
byte. Ini melengkapi temuan H11 dan sekaligus membatasinya: keunggulan ruang B3 pada H11 diukur
**per revisi** pada keadaan yang sudah penuh, sedangkan pada rangkaian rilis nyata yang sebagian
besarnya justru menambah sel baru, keunggulan itu menipis. Keunggulan B3 dalam ruang karena itu
bergantung pada seberapa besar bagian keadaan yang disentuh sebuah rilis, bukan pada jumlah rilisnya
saja.

Footprint lengkap dari listing MinIO, yaitu seluruh kelas objek termasuk daftar manifest dan berkas
metadata, adalah B0 383.025 byte, B1 889.873 byte, B2 372.108 byte, serta B3 952.270 byte yang
terbagi menjadi store 571.722 byte dan serving 380.548 byte. Angka ini lebih besar daripada kolom
byte per kedatangan karena kolom tersebut hanya menghitung data dan manifest, sedangkan footprint
menghitung kelima kelas objek.

Dibandingkan keadaan dasar H11 yang membangun keadaan yang sama, footprint di sini sedikit lebih
besar untuk B0 dan B2, yaitu 383.025 berbanding 373.370 byte dan 372.108 berbanding 316.590 byte.
Datanya identik; selisihnya berupa metadata, karena menerapkan empat rilis satu per satu meninggalkan
lebih banyak catatan metadata daripada membangun keadaan yang sama dalam satu jalan. Ini sekali lagi
menunjukkan bahwa pada beban sekecil ini metadata bukan komponen yang dapat diabaikan.

### Apa yang ditambahkan H12 terhadap H11

Tiga hal. Pertama, urutan biaya antarperlakuan terbukti sama pada revisi nyata dan revisi tersuntik,
sehingga hasil sweep tidak dapat ditolak sebagai artefak revisi buatan. Kedua, terlihat bahwa pada
skala ini `MERGE` lebih mahal daripada penulisan ulang penuh, yang menjelaskan mengapa B0 dan B3
tidak pernah menang dalam waktu. Ketiga, keunggulan ruang B3 ternyata bergantung pada proporsi
keadaan yang disentuh tiap rilis, dan pada rangkaian rilis nyata yang banyak menambah sel baru
keunggulan itu habis.

## Batas klaim

Sama seperti H10B dan H11: waktu hanya boleh dibaca sebagai perbandingan antarperlakuan pada VM 2
vCPU yang dibekukan, tidak pernah sebagai klaim performa atau skalabilitas. Selain itu, beban ini
memuat empat kedatangan dengan ukuran yang sangat timpang, mulai 62 sampai 4.591 baris, sehingga
perbandingan antarkedatangan mencampur dua hal sekaligus, yaitu besaran kedatangan dan keadaan yang
sudah ada sebelumnya. Sweep H11-lah yang memisahkan keduanya dengan besaran terkontrol.

## Artefak audit

- kontrak: `contracts/h12-real-revision-cost.json`;
- penggerak pengukuran: `scripts/h12_measure.sh`, memakai SQL bersama `scripts/h11_sql.sh`;
- keluaran mentah: `results/raw/h12/h12-20260913/`;
- hasil agregat: `results/processed/h12-*.csv` dan `data/manifests/h12-real-revision-cost.json`.
