# H6 Jalur A - Skema indikator dengan vintage eksplisit

H6 menetapkan kontrak fisik yang dipakai oleh B0, B1, dan B3 pada hari berikutnya. Skema tidak
menandai satu angka sebagai “benar”; setiap nilai tetap terikat pada rilis atau snapshot sumbernya.
Fixture validasi memakai 38 baris jejak nyata H5 agar keputusan skema diuji terhadap perubahan
nilai, sumber, metodologi, dan format angka yang sudah diamati.

## Keputusan skema

Skema terdiri dari dua tabel Iceberg.

| Tabel | Grain | Peran |
|---|---|---|
| `kkciv.research.release_vintages` | satu rilis atau snapshot sumber | dimensi vintage eksplisit |
| `kkciv.research.indicator_observations` | satu sel indikator pada satu vintage dan locator sumber | fakta nilai serta provenance |

`vintage_id` diturunkan deterministik dari `source_id`, `vintage_date`, dan checksum manifest
sumber. Dengan demikian dua penarikan dari sumber yang sama tidak saling menimpa bila manifestnya
berbeda. `vintage_basis` membedakan `published_release` dari `retrieval_snapshot`, sehingga tanggal
terbit publikasi tidak dicampur dengan waktu pengambilan API.

`cell_id` diturunkan dari indikator, seri, periode observasi, tingkat geografi, dan kode geografi.
Sumber, vintage, nilai, unit, serta versi metodologi sengaja tidak masuk identitas sel. Akibatnya
sel yang sama tetap dapat diikuti ketika sumber, nilai, unit, atau metode berubah. Identitas baris
fisik berada pada `observation_id`, yaitu hash dari `cell_id`, `vintage_id`, dan
`source_record_id`.

## Presisi dan reproduksi

Nilai disimpan dua kali dengan fungsi berbeda:

- `value_decimal DECIMAL(38,10)` untuk perbandingan numerik eksak tanpa galat floating point;
- `value_lexeme STRING` dan `published_decimal_places` untuk menghasilkan kembali bentuk yang
  diterbitkan, misalnya membedakan `9.00` dari `9.0`.

`unit` dan `methodology_version` berada pada fakta observasi, bukan pada dimensi indikator yang
dianggap tetap. Pilihan ini diperlukan oleh kasus tutupan hutan H5, yang membuktikan bahwa makna
angka dapat berubah antarrilis walaupun kunci indikatornya sama.

Provenance setiap fakta mencakup path dan checksum artefak sumber, locator rekaman sumber, batch
ingestion H4, run transformasi H5, serta versi transformasi H6. Rantai yang dapat dibentuk adalah:

`source manifest -> vintage_id -> observation_id/cell_id -> trace_id`

## Nilai terbaru bukan state yang ditimpa

Tidak ada kolom `is_current`. Nilai terbaru selalu diturunkan dari urutan
`vintage_date`, `retrieved_at`, `vintage_id`, lalu `observation_id`. Ini mencegah pembaruan satu
flag menghapus sejarah dan menjaga hasil query as-of tetap dapat dibentuk ulang. Aturan tersebut
hanya berarti *latest vintage* secara mekanis; aturan kepercayaan sumber B2 tetap keputusan
terpisah.

## Partisi

Tabel vintage tidak dipartisi dan tabel observasi hanya dipartisi menurut lima `domain`. Data
indikator ini kecil, sehingga partisi per tahun, sumber, atau provinsi justru berisiko menghasilkan
banyak file kecil. Urutan logis yang dibekukan dalam kontrak adalah indikator, periode, geografi,
dan vintage; optimasi fisiknya baru boleh diubah sebagai versi eksperimen baru.

## Validasi fixture H5

`make h6-run` memproyeksikan 38 baris H5 secara lossless menjadi:

- 3 baris dimensi vintage: TPB 2024, TPB 2025, dan snapshot WebAPI 2026;
- 38 fakta observasi;
- 14 `cell_id` stabil, satu untuk setiap jejak H5;
- 38 `observation_id` unik dan tanpa foreign key vintage yang hilang.

Enam invariant kontrak lulus, termasuk presisi lexeme, identitas sel lintas sumber, dan aturan
bahwa status current selalu diturunkan.

## Uji Iceberg

`make h6-apply` menjalankan DDL di `infra/spark/h6-vintage-schema.sql`, memuat fixture ke dua tabel
dengan `INSERT OVERWRITE`, lalu membaca data dan metadata Iceberg kembali. Uji memeriksa jumlah
vintage, observasi, sel, cardinality vintage per sel, data file, foreign key, serta kesetaraan
`value_lexeme` terhadap `value_decimal`.

Status eksekusi VM akan dicatat setelah implementasi H6 di-commit, di-push, dan ditarik oleh VM.

## Artefak dan reproduksi

- `contracts/h6-vintage-schema.json`: kontrak kolom, tipe, identitas, invariant, partisi, dan aturan
  current;
- `infra/spark/h6-vintage-schema.sql`: DDL Iceberg;
- `results/processed/h6-release-vintages.csv`: fixture dimensi vintage;
- `results/processed/h6-indicator-observations.csv`: fixture fakta observasi;
- `results/processed/h6-schema-validation.csv`: hasil enam invariant;
- `data/manifests/h6-vintage-schema.json`: checksum input-output;
- `scripts/h6_apply.sh`: uji integrasi Iceberg idempoten.

Jalankan:

```bash
make h6-run
make test
make h6-apply  # membutuhkan stack yang aktif
```

