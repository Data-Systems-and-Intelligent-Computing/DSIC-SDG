# Audit Reproducibility dan Analisis Kegagalan (H13 Jalur C)

## Status

H13 Jalur C menjawab P4 pada skala panel dan menutup butir §13 yang menuntut minimal satu analisis
kegagalan. Prosedur audit sepuluh langkah yang dibekukan pada H8C dijalankan atas **seluruh 6.983
angka terbit** panel provinsi untuk keempat perlakuan, lalu setiap kegagalan diklasifikasikan dan
ditelusuri sampai ke rekaman sumbernya.

Kontrak ada di
[`contracts/h13c-reproducibility-audit.json`](../../contracts/h13c-reproducibility-audit.json).
Jalankan `make h13c-run`. Marker:

```
H13C_VERIFY|6983|0.7702|1.0000|0.7702|1.0000|1605|0|1605|0|43|0|43|0|39|1.0000|125|validated
```

## Mengapa audit ini diperlukan

H9C sudah mengaudit keempat perlakuan, tetapi atas 38 permintaan pada fixture 14 sel. Angka
`0,3684` untuk B0 dan B2 di sana benar, namun berasal dari fixture yang memang dipilih karena setiap
selnya direvisi. Panel provinsi berperilaku berbeda: sebagian besar selnya hanya muncul sekali, dan
tingkat keberhasilan yang terukur pun jauh lebih tinggi. Keduanya perlu dilaporkan berdampingan agar
pembaca tidak menyimpulkan bahwa B0 kehilangan dua pertiga angka terbit pada beban apa pun.

Yang lebih penting, tingkat keberhasilan saja tidak membedakan **angka revisi yang hilang** dari
**duplikat yang hilang**. Audit ini memisahkan keduanya.

## Hasil pada kedua skala

| Skala | Permintaan | B0 | B1 | B2 | B3 |
|---|---:|---:|---:|---:|---:|
| Fixture bukti (H9C) | 38 | 0,3684 | 1,0000 | 0,3684 | 1,0000 |
| Panel provinsi (H13C) | 6.983 | 0,7702 | 1,0000 | 0,7702 | 1,0000 |

B1 dan B3 memanggil ulang seluruh angka terbit pada kedua skala, B1 melalui state yang dipertahankan
dan B3 melalui kunci `(cell_id, vintage_id)`. B0 dan B2 sama-sama gagal pada 1.605 dari 6.983
permintaan, dan angka yang sama itu menyembunyikan perbedaan yang penting.

## Yang hilang tidak sama

Meskipun jumlah kegagalannya identik, **himpunan yang hilang berbeda**, karena kebijakan keduanya
berbeda.

| Perlakuan | Sebab kegagalan | Sumber yang hilang |
|---|---|---|
| B0 | ditimpa vintage yang datang kemudian | 1.556 baris TPB 2024 dan 49 baris TPB 2025 |
| B2 | tidak terpilih oleh skor kepercayaan | 1.567 baris WebAPI dan 38 baris TPB 2024 |

B0 kehilangan yang lama karena yang baru menimpanya. B2 kehilangan yang baru karena skor
kepercayaannya lebih rendah. Keduanya kehilangan seperempat arsip angka terbit, tetapi seperempat
yang berlawanan arah.

## Berapa yang benar-benar hilang

Dari 1.605 kegagalan, hanya sebagian kecil membawa nilai yang berbeda dari yang kini disajikan
perlakuan tersebut. Sisanya adalah baris dengan nilai yang sama persis dari sumber lain, sehingga
tidak ada angka terbit yang benar-benar lenyap.

| Perlakuan | Kegagalan | Material | Duplikat nilai |
|---|---:|---:|---:|
| B0 | 1.605 | **43** | 1.562 |
| B2 | 1.605 | **43** | 1.562 |

Inilah angka yang seharusnya dibaca sebagai kerugian reproducibility: **43 angka yang pernah
diterbitkan BPS tidak lagi dapat dihasilkan ulang** pada masing-masing perlakuan, dan sekali lagi
himpunannya berbeda. Pada B0 sebarannya 29 kejadian ekonomi, 13 energi, dan 1 ekologi; pada B2
sebarannya 31 ekonomi, 11 energi, dan 1 ekologi.

Setiap kasus dicatat baris per baris di
[`results/processed/h13c-failure-cases.csv`](../../results/processed/h13c-failure-cases.csv), lengkap
dengan nilai yang hilang, nilai penggantinya, selisihnya, serta artefak dan locator rekaman sumbernya.
Contoh kasus pertama: `sdg07_clean_cooking` 2021 untuk provinsi 1200, TPB 2024 menerbitkan 88,12
sedangkan keadaan B0 kini menyajikan 88,11 dari WebAPI; angka 88,12 yang pernah terbit tidak dapat
lagi dihasilkan dari state B0.

## Kegagalan jenis ketiga: menyajikan angka yang sudah digantikan

Satu bentuk kegagalan tidak muncul pada tingkat keberhasilan sama sekali, karena permintaannya
memang terjawab. B2 memilih sumber menurut skor kepercayaan dan bukan menurut kebaruan, sehingga
pada **39 sel** ia menyajikan nilai yang sudah digantikan produsen dengan nilai berbeda. Permintaan
atas angka itu berhasil, tetapi angka yang disajikan bukan angka mutakhir.

B0, B1, dan B3 tidak pernah mengalami hal ini, karena ketiganya menyajikan vintage terbaru. Temuan
ini memperluas hasil H7B, yang menemukan pola serupa pada 10 dari 14 sel fixture, ke skala panel.

## Pemeriksaan silang terhadap pengukuran fisik

Audit ini diturunkan dari panel beku, bukan dari eksekusi baru, sehingga ia wajib cocok dengan apa
yang benar-benar dikembalikan mesin. Recall fisik yang diukur pada sweep H11 dibandingkan titik per
titik: untuk setiap skenario berukuran `k`, recall resmi B0 dan B2 harus sama dengan hitungan audit
dikurangi `k`, sedangkan B1 dan B3 harus sama persis. Kedua puluh empat pasangan
skenario-perlakuan cocok tanpa kecuali.

Seluruh 6.983 permintaan juga terselesaikan ke satu rekaman sumber melalui lineage panel, dengan
kelengkapan `1,0000` atas 19.379 node dan 41.928 edge.

## Reproduksi

```bash
make h13c-run
```

Audit menolak berjalan bila prosedur sepuluh langkah H8C berubah, bila satu saja keluaran payload
panel tidak cocok dengan checksum manifestnya, bila ada kegagalan yang tidak terklasifikasi, atau
bila recall turunan tidak cocok dengan recall yang diukur sweep. Audit diulang di VM dari commit yang
sama dan menghasilkan checksum identik untuk kelima berkas keluaran; 164 test lulus pada kedua mesin
dengan satu test PDF dilewati.

## Batas klaim

Audit ini menyangkut kemampuan memanggil ulang angka yang pernah terbit, bukan kebenaran angkanya.
Tidak ada satu pun sumber BPS yang dinyatakan keliru di sini: yang dinyatakan adalah bahwa sebuah
perlakuan tidak lagi dapat menghasilkan angka tertentu yang pernah dipublikasikan, atau menyajikan
angka yang sudah digantikan.

Proporsi kegagalan bergantung sepenuhnya pada beban kerja. Pada fixture yang setiap selnya direvisi,
B0 kehilangan 63 persen; pada panel yang sebagian besar selnya hanya terbit sekali, ia kehilangan 23
persen. Angka mana pun tidak boleh digeneralisasi sebagai tingkat kehilangan pada arsip statistik
resmi mana pun.

## Artefak audit

- kontrak: `contracts/h13c-reproducibility-audit.json`;
- prosedur sepuluh langkah yang dibekukan H8C: `config/h8c/reproducibility_audit_steps.csv`;
- tabel dua skala: `results/processed/h13c-reproducibility-table.csv`;
- profil kegagalan: `results/processed/h13c-failure-profile.csv`;
- kasus kegagalan: `results/processed/h13c-failure-cases.csv`;
- validasi dan ringkasan: `results/processed/h13c-validation.csv`, `results/processed/h13c-summary.csv`;
- manifest: `data/manifests/h13c-reproducibility-audit.json`.
