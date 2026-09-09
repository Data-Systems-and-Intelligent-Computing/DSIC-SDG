# H7 Jalur B - Implementasi B2 pemilihan sumber tunggal

H7 Jalur B mengimplementasikan B2 dengan materialisasi satu observasi terpilih untuk setiap
`cell_id`. Implementasi mengonsumsi ranking dan preview H6 Jalur B yang sudah dibekukan; sumber
tidak dihitung ulang setelah nilai konflik terlihat. Dengan demikian hasil H7B menguji konsekuensi
aturan kepercayaan yang ditetapkan sebelumnya, bukan menyesuaikan aturan agar cocok dengan angka
terbaru.

## State B2

Tabel fisik `kkciv.experiments.b2_indicator_selected` memakai seluruh kolom fakta H6 dan menambah
skor, rank sumber, jumlah kandidat, jumlah kandidat yang dibuang, penanda apakah pilihan merupakan
vintage terbaru, versi kontrak, dan ID run deterministik. Grain tabel adalah satu baris per
`cell_id` dan partisinya tetap `domain`.

State hanya menyimpan observasi pemenang. Daftar kandidat yang dibuang berada pada artefak audit
eksperimen, bukan pada tabel serving B2. Setelah materialisasi, seluruh snapshot Iceberg kecuali
snapshot terbaru dihapus. Kebijakan ini mencegah time travel membuat kandidat yang secara logis
dibuang tetap dapat dipanggil dari tabel B2.

## Hasil materialisasi

Seluruh 38 kandidat H6 terbagi tanpa tumpang tindih menjadi 14 baris terpilih dan 24 baris dibuang.

| Hasil keputusan | Jumlah |
|---|---:|
| Terpilih | 14 |
| Dibuang karena skor lebih rendah | 10 |
| Dibuang oleh tie-break vintage yang lebih lama | 14 |
| **Total kandidat** | **38** |

TPB 2025 terpilih pada seluruh 14 sel. Empat pilihan sama dengan vintage terbaru. Sepuluh pilihan
lain mendahulukan skor TPB 2025 (`0,962500`) terhadap snapshot WebAPI 2026 (`0,907143`); pada
kesepuluh sel itu nilai B2 berbeda dari nilai latest-vintage.

Hasil tersebut tidak menunjukkan TPB 2025 benar dan WebAPI salah. Keduanya merupakan rilis resmi.
Ia menunjukkan perilaku pembanding single-source: aturan kepercayaan dapat memberi jawaban yang
konsisten, tetapi perubahan vintage yang bermakna hilang dari state serving.

## Reproducibility

Audit meminta kembali seluruh 38 `observation_id`. Empat belas observasi terpilih tersedia dan 24
kandidat yang dibuang tidak tersedia, sehingga tingkat baca ulang adalah `14 / 38 = 0,3684`.
Kegagalan ini sesuai desain B2 dan tetap menjadi hasil kontrol negatif untuk P4.

B2 dan B0 sama-sama menyisakan 14 dari 38 alamat observasi, tetapi isi state tidak sama. B0
menyimpan latest-vintage dan B2 menyimpan sumber dengan skor tertinggi; akibatnya sepuluh nilai B2
berbeda dari B0. Perbedaan inilah yang membuat keduanya tetap menjadi perlakuan terpisah.

## Invariant dan uji Iceberg

Enam invariant logis lulus: materialisasi sama dengan preview beku, satu baris per sel, selected
dan discarded membagi input secara lengkap, setiap discard mempunyai alasan, tidak ada rescoring,
dan audit reproducibility seimbang.

`make h7b-apply` memvalidasi checksum manifest, membuat tabel, menjalankan `INSERT OVERWRITE`,
menghapus snapshot lama, lalu membaca state dan metadata Iceberg kembali. Uji fisik memeriksa
jumlah baris/sel, satu sumber terpilih, sepuluh pilihan non-latest, hasil audit 14/24, tepat satu
snapshot, keberadaan data file, serta nol duplikasi dan mismatch.

Status verifikasi VM akan dicatat setelah commit implementasi ditarik dan dijalankan pada
`sigerciv@34.128.67.92`.

## Artefak dan reproduksi

- `contracts/h7b-b2-single-source.json`: kontrak state, reproducibility, dan larangan rescoring;
- `infra/spark/h7b-b2.sql`: DDL tabel Iceberg B2;
- `results/processed/h7b-b2-selected-state.csv`: 14 observasi terpilih;
- `results/processed/h7b-b2-discarded-candidates.csv`: 24 kandidat beserta alasan discard;
- `results/processed/h7b-b2-reproducibility.csv`: audit 38 alamat observasi;
- `results/processed/h7b-b2-summary.csv`: ringkasan metrik;
- `results/processed/h7b-b2-validation.csv`: hasil enam invariant;
- `data/manifests/h7b-b2-single-source.json`: checksum seluruh input-output;
- `scripts/h7b_apply.sh`: uji integrasi Iceberg idempoten.

Jalankan:

```bash
make h7b-run
make test
make h7b-apply  # membutuhkan stack yang aktif
```
