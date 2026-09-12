# Pengulangan Titik yang Meragukan (H13)

## Status

H13 sisi operator mengerjakan satu hal: mencari titik pengukuran yang repetisinya tidak cukup
sepakat untuk dipercaya, menjalankannya kembali dengan repetisi tambahan, lalu melaporkan apakah
median yang sudah diterbitkan bertahan.

Kontrak eksekusi ada di
[`contracts/h13-rerun-stability.json`](../../contracts/h13-rerun-stability.json). Jalankan
`make h13-rerun` di host stack, lalu `make h13-run`. Alasan setiap pengulangan tercatat di
[`docs/research/decision-log.md`](decision-log.md), sesuai §12 README utama.

## Aturan keraguan

Aturan ditetapkan lebih dahulu, lalu diterapkan secara mekanis pada **seluruh** titik pengukuran H11
dan H12, bukan pada sebagian yang dipilih.

> Sebuah titik dinyatakan meragukan bila sebaran fase tulisnya, yaitu selisih repetisi terlama dan
> tercepat dibagi mediannya, melebihi 0,20.

Yang dipakai adalah fase tulis, karena itulah ongkos perlakuan yang dilaporkan naskah. Sebaran fase
pemeliharaan tetap dicatat pada tabel yang sama, tetapi tidak memicu pengulangan; pemeliharaan
dilaporkan terpisah dan sifatnya memang lebih berayun pada node bersama.

Unit pengulangan adalah apa yang dieksekusi skrip pengukur sebagai satu siklus: satu skenario sweep
untuk H11, dan keempat kedatangan sekaligus untuk H12. Titik lain yang kebetulan berada di dalam
siklus yang sama ikut terukur ulang, dan hasilnya tetap dilaporkan.

## Aturan putusan

Median yang sudah diterbitkan **tidak pernah diganti**. Median gabungan dilaporkan berdampingan, dan
selisih relatifnya menentukan putusan:

- selisih dalam 5 persen: median terbitan dinyatakan bertahan;
- selisih di luar 5 persen: angka pada naskah wajib dikoreksi, dan koreksinya dicatat di decision log.

Repetisi tambahan berjumlah tiga per unit, sehingga titik yang diulang memiliki enam repetisi. Jumlah
ini memang tidak cukup untuk uji signifikansi, dan seluruh angka tetap dilaporkan sebagai median
beserta nilai minimum dan maksimum.

## Hasil

Aturan diterapkan pada seluruh 40 titik pengukuran, yaitu 24 titik sweep H11 dan 16 titik kedatangan
H12. Enam titik melewati ambang:

| Tahap | Titik | Perlakuan | Median tulis | Rentang repetisi | Sebaran |
|---|---|---|---:|---|---:|
| H11 | `sweep_001` | B2 | 9,998 s | 9,405 – 12,869 | 0,3465 |
| H11 | `sweep_001` | B3 | 15,971 s | 15,445 – 21,014 | 0,3487 |
| H12 | kedatangan 1 | B2 | 8,797 s | 8,047 – 17,465 | 1,0706 |
| H12 | kedatangan 2 | B2 | 2,064 s | 1,997 – 2,448 | 0,2185 |
| H12 | kedatangan 3 | B0 | 3,497 s | 3,064 – 3,806 | 0,2122 |
| H12 | kedatangan 3 | B2 | 2,062 s | 1,961 – 2,401 | 0,2134 |

Repetisi yang melar tidak berkumpul pada satu repetisi tertentu: pada H11 `sweep_001` nilai
tertinggi B2 muncul di repetisi pertama sedangkan B3 di repetisi ketiga, dan pada H12 kedatangan
pertama nilai tertinggi B2 muncul di repetisi ketiga. Ini derau biasa pada node bersama 2 vCPU,
bukan efek pemanasan yang dapat dibuang.

Kedua unit yang memuat titik meragukan dijalankan kembali dengan tiga repetisi tambahan, sehingga 20
titik memperoleh enam repetisi. Hasilnya:

- **18 titik stabil.** Median gabungan berada dalam pita 5 persen median terbitan.
- **2 titik bergeser.** Keduanya pada H12: kedatangan 2 perlakuan B2 bergerak dari 2,064 menjadi
  2,250 detik (+9,01 persen), dan kedatangan 3 perlakuan B0 bergerak dari 3,497 menjadi 3,319 detik
  (−5,09 persen).

Keempat titik yang paling meragukan justru bertahan. Median tulis B2 pada `sweep_001` bergerak dari
9,998 menjadi 9,956 detik (−0,42 persen) dan B3 dari 15,971 menjadi 15,964 detik (−0,04 persen),
meskipun sebarannya tetap tinggi karena repetisi yang melar tetap ikut dihitung. Median memang tahan
terhadap satu nilai ekstrem; sebarannya yang perlu dilaporkan, dan itulah yang dilakukan.

Kedua pergeseran berada pada pernyataan tulis berdurasi dua sampai empat detik, dengan selisih
absolut 0,186 dan 0,178 detik. Tidak satu pun kesimpulan berubah karenanya: pada kedatangan kedua
`MERGE` B0 tetap jauh lebih mahal daripada `INSERT OVERWRITE` B1 (4,085 berbanding 2,375 detik pada
median gabungan), dan urutan biaya keempat perlakuan pada H11 maupun H12 tidak bergeser sama sekali.
Sesuai aturan putusan, kedua angka itu tetap dikoreksi di
[`docs/research/h12-real-revision-cost.md`](h12-real-revision-cost.md) dan dicatat di
[`decision-log.md`](decision-log.md); median terbitan tidak dihapus, melainkan dilaporkan
berdampingan dengan median gabungan.

Marker: `H13_VERIFY|40|6|20|3|18|2|0.0901|verified`.

### Catatan tentang kebersihan working tree

Re-run H12 berjalan setelah re-run H11 di dalam satu batch, sehingga saat H12 mulai, keluaran mentah
H11 sudah ada di working tree sebagai satu entri yang belum di-commit. Audit H13 karena itu tidak
menuntut nol perubahan secara buta, melainkan menuntut bahwa satu-satunya yang belum di-commit
adalah keluaran mentah re-run sebelumnya di batch yang sama, dan bahwa seluruh re-run mengukur commit
yang sama, yaitu `62ff25a`. Kedua skrip pengukur kini juga mencatat **jalur** mana yang belum
di-commit, bukan hanya jumlahnya, sehingga run berikutnya dapat memeriksa hal ini tanpa penalaran
tambahan.

## Batas klaim

H13 tidak menambah pengukuran baru dan tidak mengubah satu pun parameter beku; ia hanya menambah
repetisi pada titik yang sudah diukur. Karena itu H13 tidak memerlukan versi eksperimen baru, tetapi
juga tidak dapat memperbaiki keterbatasan yang berasal dari rancangan, misalnya node tunggal atau
ukuran panel tunggal. Yang dijawab H13 hanya satu pertanyaan: apakah angka yang dilaporkan cukup
stabil untuk dipakai.

## Artefak audit

- kontrak: `contracts/h13-rerun-stability.json`;
- pengulangan H11: `results/raw/h11/h13-h11-sweep001/`;
- pengulangan H12: `results/raw/h12/h13-h12/`;
- hasil: `results/processed/h13-*.csv` dan `data/manifests/h13-rerun-stability.json`;
- catatan pengulangan: `docs/research/decision-log.md`.
