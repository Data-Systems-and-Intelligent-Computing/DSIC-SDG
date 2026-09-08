# Audit awal data BPS untuk H1

Tanggal pemeriksaan: 2026-09-08.

## Keputusan

Tiga kanal dalam proposal sesuai sebagai titik awal: WebAPI BPS untuk data terstruktur, SIRuSa
untuk metadata, dan publikasi tahunan Indikator TPB Indonesia sebagai jalur penyajian resmi.
Namun, daftar pada Tabel 9 proposal masih merupakan daftar kandidat. Belum ada bukti di
repositori bahwa setiap kandidat tersedia pada dua kanal, pada granularitas nasional dan provinsi,
atau untuk satu dekade penuh.

H1 karena itu harus menghasilkan inventaris terverifikasi. H2 baru boleh menarik dan
membandingkan indikator yang memiliki locator sumber lengkap.

## Koreksi terhadap asumsi proposal dan README

1. Publikasi terbaru yang tersedia adalah *Indikator Tujuan Pembangunan Berkelanjutan Indonesia
   2025*, rilis 30 Desember 2025, nomor publikasi 07300.25034. Publikasi ini merupakan kolaborasi
   BPS, Sekretariat Nasional SDGs Bappenas, dan BIG.
2. `BPS` perlu dicatat sebagai kanal/penerbit dan sebagai produsen secara terpisah. Publikasi BPS
   juga mengompilasi indikator dari kementerian/lembaga. Contoh yang sudah terlihat adalah bauran
   energi 7.2.1 yang menggunakan data ESDM dan tutupan hutan 15.1.1(a) yang merujuk data KLHK.
3. Dokumentasi WebAPI mengharuskan API key serta ID domain, variabel, periode, dan kategori.
   Nama indikator saja belum cukup untuk menarik data secara reproducible.
4. SIRuSa memverifikasi definisi dan metadata. DNA (*Data Nucleus for Analytics*) menyediakan
   API JSON untuk metadata yang sama dan membutuhkan token login. Keberadaan metadata pada
   keduanya tidak membuktikan bahwa deret nilainya tersedia melalui WebAPI.
5. Klaim “sudah ditarik menurut proposal” belum didukung artefak di repositori. Tidak ada payload,
   manifest, checksum, ID API, atau tanggal penarikan sebelum scaffold H1 ini dibuat.
6. Proposal menyebut Silastik/PST berbayar pada jalur kritis, sedangkan README terbaru memilih
   jalur terbuka. Implementasi H1 mengikuti README terbaru; data berbayar tidak diasumsikan ada.

## Risiko indikator yang harus diperiksa pada H1

- SDG 4.1.1 berbasis AKM mempunyai deret relatif baru, sehingga tidak cocok dengan asumsi satu
  dekade tanpa bukti tambahan.
- SDG 6.1.1 dan 6.2.1 mencampur istilah `layak` dan `aman`; keduanya harus menjadi seri berbeda
  bila definisi atau denominator berbeda.
- SDG 7.1.1 mencampur rasio elektrifikasi dan persentase rumah tangga dengan akses listrik.
  Keduanya tidak boleh dibandingkan sebagai satu indikator tanpa pemetaan metodologi.
- SDG 7.2.1 dan 7.3.1 hanya diusulkan pada tingkat nasional, sehingga tidak mendukung uji
  provinsi.
- SDG 15.1.1 global dan indikator nasional 15.1.1(a) adalah kode/konsep berbeda; proposal perlu
  memilih yang dipakai.
- SDG 15.5.1 hanya nasional dan tidak dapat menjadi observasi untuk analisis spasial provinsi.
- Baris tanpa kode SDG, seperti APS, APM, APK, TPAK, serta luas kawasan, dapat dipakai sebagai
  variabel pendukung tetapi harus diberi label terpisah dari indikator TPB resmi.

## Artefak H1 dan pembagian kerja

- `config/sources/bps_sources.csv` adalah daftar kanal bersama.
- Lima berkas di `config/indicators/` dibagi satu per peneliti domain.
- `config/templates/normalized_observations.csv` adalah kontrak data untuk hasil ekstraksi H2.
- `make h1-validate` memeriksa struktur, referensi sumber, duplikasi, dan locator wajib.
- `make h1-summary` menunjukkan kemajuan verifikasi per domain.
- `make h1-example` menjalankan harness perbandingan pada dua snapshot contoh.

H1 selesai ketika setiap baris diputuskan menjadi `verified`, `partial`, `unavailable`, atau
`blocked`, dan setiap baris `verified` memiliki locator serta cakupan aktual. Status awal
`proposal_only` sengaja dipertahankan agar klaim ketersediaan tidak dibuat sebelum ada bukti.

## Sumber resmi yang diperiksa

- Dokumentasi WebAPI BPS: <https://webapi.bps.go.id/documentation/>
- SIRuSa Metadata Statistik: <https://sirusa.web.bps.go.id/metadata/indikator>
- Dokumentasi OpenAPI DNA: <https://dna.web.bps.go.id/docs/api-docs.json>
- Publikasi TPB 2025: <https://www.bps.go.id/id/publication/2025/12/30/8ffdc46aa817bf0c4c47e105/2025-indonesian-sustainable-development-goals-indicators.html>
- Publikasi TPB 2024: <https://www.bps.go.id/id/publication/2024/12/31/936a26d5d2b168b9971d3b02/indikatortujuan-pembangunan-berkelanjutan-indonesia-2024.html>
