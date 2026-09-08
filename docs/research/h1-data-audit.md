# Audit data gratis BPS - Minggu 1, H1

Tanggal pemeriksaan: 8 September 2026.

## Keputusan H1

H1 selesai untuk 35 kandidat indikator pada lima domain. Setiap kandidat sudah mempunyai keputusan
`verified`, `partial`, atau `unavailable`; tidak ada lagi baris `proposal_only`. Hasil ini menutup
inventarisasi Hari 1, tetapi belum meloloskan Gate G1. Gate G1 baru dapat dinilai setelah H2-H5
membandingkan nilai antarrilis dan menguji apakah jejak revisi benar-benar ada.

Seluruh bukti H1 berasal dari layanan tanpa biaya pembelian data:

- WebAPI BPS untuk katalog variabel dan payload tabel dinamis;
- katalog publikasi WebAPI BPS untuk mengunduh *Indikator Tujuan Pembangunan Berkelanjutan
  Indonesia 2024* dan edisi 2025;
- PDF publikasi BPS yang diunduh dari tautan resmi katalog tersebut.

SIRuSa dan DNA berstatus `hold` sesuai keputusan proyek. Silastik/PST, data mikro berbayar,
publikasi elektronik berbayar, dan peta digital berbayar tidak digunakan. Peta batas BPS/BIG juga
belum masuk pipeline sampai ditemukan rilis publik gratis yang tepat; geometri bukan syarat audit
indikator pada H1.

## Hasil aktual

| Artefak | Hasil |
|---|---:|
| Variabel pada katalog pusat WebAPI (`domain=0000`) | 1.753 |
| Kandidat hasil pencocokan awal | 175 |
| Variabel WebAPI terpilih dan diunduh | 29 |
| ID periode yang diunduh, mulai 2015 | 240 |
| Sel data pada respons WebAPI | 27.826 |
| Publikasi TPB gratis yang diunduh | 2 |
| Kandidat indikator yang diaudit | 35 |
| `verified` | 14 |
| `partial` | 17 |
| `unavailable` | 4 |

Status `verified` berarti sedikitnya satu sumber gratis yang tepat telah dikonfirmasi dengan
locator dan memenuhi geografi yang diusulkan. Status `partial` berarti sumber gratis ada, tetapi
cakupan geografis kurang, deret pendek/berjarak, memuat beberapa frekuensi, atau indikator masih
memerlukan transformasi kategori. Status `unavailable` berarti tidak ditemukan seri gratis yang
definisinya tepat pada dua jalur yang diperiksa.

Rincian per variabel terdapat di `results/processed/h1-webapi-coverage.csv`; keputusan per indikator
terdapat di `results/processed/h1-indicator-coverage.csv` dan sudah ditulis kembali ke lima berkas
`config/indicators/sdg*.csv`.

## Empat celah data gratis

1. `sdg04_dropout`: katalog hanya memberi kandidat angka anak tidak sekolah. Konsep itu tidak
   diganti menjadi angka putus sekolah karena denominator dan peristiwanya berbeda.
2. `sdg06_water_source`: tersedia persentase akses air minum layak, tetapi tidak ditemukan tabel
   pusat yang menguraikan jenis sumber air sesuai kandidat proposal.
3. `sdg15_protected_biodiversity`: publikasi 2024 memuat indikator nasional 15.1.2(a) berupa luas
   kawasan bernilai konservasi tinggi. Proksi tersebut tidak sama dengan proporsi kawasan penting
   keanekaragaman hayati darat yang dilindungi.
4. `sdg15_sustainable_forest`: publikasi 2024 memuat 15.2.1(a), jumlah KPH berkategori maju. Jumlah
   KPH tidak disamakan dengan indikator global pengelolaan hutan lestari.

Keempatnya dikeluarkan dari ekstraksi H2 sampai ada sumber gratis dengan definisi yang tepat.

## Temuan yang mengubah asumsi proposal

1. Publikasi terbaru adalah edisi 2025, rilis 30 Desember 2025 dengan nomor publikasi
   07300.25034. Untuk pemetaan H1, edisi 2024 lebih lengkap dan memberi locator bagi 8.10.1,
   15.3.1, dan 15.5.1 yang tidak ditemukan sebagai tabel dinamis pusat.
2. BPS harus dicatat terpisah sebagai kanal/penerbit dan sebagai produsen. Data bauran energi dan
   intensitas energi diproduksi ESDM; data tutupan lahan diproduksi KLHK; indikator 8.10.1 pada
   publikasi bersumber dari Bank Indonesia; layanan dasar sekolah bersumber dari
   Kemendikbud/Dapodik.
3. WebAPI membutuhkan API key dan locator `domain`, `var`, serta `th`. API membatasi parameter
   `th` maksimal tiga periode per permintaan, sehingga downloader membagi periode otomatis.
4. Istilah `layak` dan `aman` pada SDG 6 bukan sinonim. Variabel WebAPI 845 berisi akses sumber
   air minum layak, sedangkan publikasi 2024 menyajikan layanan air minum yang dikelola secara aman.
5. Rasio elektrifikasi ESDM (variabel 1155, nasional) dan persentase rumah tangga yang menggunakan
   listrik PLN/non-PLN (variabel 2832, nasional sampai kabupaten/kota) disimpan sebagai konsep
   terpisah.
6. SDG 15.1.1 membutuhkan denominator luas daratan dan pemetaan kelas tutupan lahan. Variabel
   1304 belum boleh disebut proporsi tutupan hutan sebelum transformasi itu dijalankan.

## Kandidat kuat untuk eksperimen versi rilis data

Beberapa metadata WebAPI sudah menunjukkan perubahan yang relevan untuk penelitian:

- variabel 1172, upah per jam, menyatakan nilai 2015-2019 direvisi karena perubahan penimbang;
- variabel 543, TPT, mencatat backcast dan perubahan metodologi pada periode historis;
- variabel 847, sanitasi layak, mencatat perubahan metode pada 2019;
- variabel 1161 memakai nilai PDB/PDRB sementara atau sangat sementara untuk tahun terbaru;
- variabel 1304 berasal dari rekalkulasi penutupan lahan 2014-2023.

Daftar ini menjadi prioritas H2 karena memberi peluang nyata menemukan perbedaan nilai antara
payload WebAPI terbaru dan angka yang dibekukan pada publikasi.

## Artefak dan reproduksi

- `config/sources/bps_sources.csv`: kebijakan biaya dan status aktif/hold setiap kanal.
- `config/sources/free_webapi_selection.csv`: keputusan pemetaan indikator ke `var_id`.
- `config/sources/free_publication_selection.csv`: locator halaman publikasi dan keputusan
  menerima atau menolak proksi.
- `data/manifests/h1-webapi-variable-catalog.json`: checksum katalog variabel.
- `data/manifests/h1-free-webapi-data.json`: checksum 29 payload variabel.
- `data/manifests/h1-free-publications.json`: checksum dua PDF publikasi.
- `results/processed/h1-webapi-coverage.csv`: profil periode, geografi, kategori, dan kepadatan sel.
- `results/processed/h1-indicator-coverage.csv`: status akhir 35 kandidat.

Payload mentah dan PDF berada di `data/raw/h1/` dan sengaja tidak disimpan di Git karena dapat
dibentuk ulang dari manifest dan API key lokal. API key hanya dibaca dari `.env`; manifest hanya
menyimpan fingerprint delapan karakter dari hash key.

Jalankan ulang H1 dengan urutan berikut:

```bash
make h1-discover-webapi
make h1-fetch-free-webapi
make h1-fetch-free-publications
make h1-apply-coverage
make h1-summary
make test
```

## Sumber resmi

- Dokumentasi WebAPI BPS: <https://webapi.bps.go.id/documentation/>
- Layanan BPS yang mencantumkan WebAPI sebagai layanan gratis:
  <https://ppid.bps.go.id/app/konten/1608/Layanan-BPS.html>
- Publikasi TPB 2025:
  <https://www.bps.go.id/id/publication/2025/12/30/8ffdc46aa817bf0c4c47e105/2025-indonesian-sustainable-development-goals-indicators.html>
- Publikasi TPB 2024:
  <https://www.bps.go.id/id/publication/2024/12/31/936a26d5d2b168b9971d3b02/indikatortujuan-pembangunan-berkelanjutan-indonesia-2024.html>
