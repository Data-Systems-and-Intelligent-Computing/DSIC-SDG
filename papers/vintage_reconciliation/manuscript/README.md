# Naskah LaTeX — Elsevier CAS (cas-dc)

Versi bahasa Inggris dari draf Jalur C, ditulis dengan kelas Elsevier CAS kolom ganda `cas-dc`,
mengikuti `papers/els-cas-templates/cas-dc-template.tex`.

## Isi

| Berkas | Keterangan |
|---|---|
| `main.tex` | naskah; bagian 1–5 |
| `refs.bib` | daftar pustaka, seluruhnya diambil dari `docs/research/related-work.md` |
| `cas-dc.cls`, `cas-common.sty`, `cas-model2-names.bst` | salinan kelas Elsevier, diperlukan karena `papers/els-cas-templates/` tidak masuk Git |
| `thumbnails/` | ikon email dan media sosial yang dipanggil kelas `cas-dc` |

## Cara compile

```bash
cd papers/vintage_reconciliation/manuscript
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

Keluarannya `main.pdf`. Versi 12 September 2026 menghasilkan 6 halaman, yaitu satu halaman
highlights dan lima halaman artikel, tanpa error dan tanpa sitasi yang tidak terdefinisi. Berkas
bantu LaTeX dan `main.pdf` tidak masuk Git.

## Cakupan naskah

Bagian 1 sampai 5 memuat pekerjaan yang sudah terukur sampai H10, yaitu Pendahuluan, Kedudukan
terhadap Literatur, Rancangan Studi, Hasil Sementara, serta Status dan Keterbatasan. Metode penuh
dan Hasil lengkap menyusul setelah sweep H11 dijalankan; bagian 5 menyatakan secara eksplisit bahwa
titik impas P3 belum dilaporkan.

Isi bagian 1 dan 2 merupakan versi bahasa Inggris dari
[`../draft/01-pendahuluan.md`](../draft/01-pendahuluan.md) dan
[`../draft/02-kedudukan-terhadap-literatur.md`](../draft/02-kedudukan-terhadap-literatur.md).
Keduanya tetap dipelihara sebagai versi kerja bahasa Indonesia, termasuk tabel pemetaan angka ke
`metric_id`.

## Aturan yang dipakai

1. Setiap angka berasal dari `../data/angka-kunci.csv` melalui `metric_id`. Jangan mengetik ulang
   angka; setelah `make article-bundle` dijalankan ulang, cocokkan kembali angka pada naskah.
2. Nama penulis pada `refs.bib` hanya memuat nama belakang, persis seperti yang tercatat pada
   `docs/research/related-work.md`. Nama depan tidak ditebak.
3. Tiga entri memakai penanda `{[Authors pending verification]}` karena penulisnya tidak tercatat.
   Penanda tersebut sengaja terlihat pada PDF agar tidak lolos ke submit.

## Yang wajib diselesaikan sebelum submit

1. Blok penulis masih memuat placeholder `[Co-author names pending]`. Lengkapi kelima rekan peneliti
   beserta afiliasi dan peran CRediT masing-masing.
2. Lengkapi nama penulis, tahun pedoman OECD/Eurostat, dan DOI pada `refs.bib`.
3. Isi bagian Data and code availability dengan URL repositori atau DOI arsip yang permanen.
4. Naikkan sumber berstatus `metadata` yang klaimnya dipakai secara substantif menjadi `penuh`.
