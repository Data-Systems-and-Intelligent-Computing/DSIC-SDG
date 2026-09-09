# H6 Jalur C - Lineage sel indikator ke rekaman sumber

H6 Jalur C membentuk graf lineage eksplisit untuk setiap observasi pada fixture H6. Tujuannya
adalah membuat setiap `cell_id` dapat ditelusuri kembali ke rekaman, artefak, dan manifest sumber
tanpa mengandalkan kemiripan label. Graf juga mempertahankan konteks vintage, batch ingestion, run
transformasi, dan versi transformasi sebagai cabang provenance yang dapat diaudit.

## Model graf

Graf diarahkan dari upstream ke downstream dan mempunyai sembilan tipe node:

`source_manifest -> source_artifact -> source_record -> observation -> indicator_cell`

Jalur lima node tersebut adalah core path dengan empat edge. Node `vintage` juga menuju observasi.
`ingestion_batch` menuju `transformation_run`, lalu run dan `transformation_version` masing-masing
menuju observasi. Seluruh edge dibentuk dari foreign key, ID, path, atau checksum yang sudah ada
pada H6; tidak ada fuzzy matching.

Identitas node dan edge berupa hash deterministik 20 karakter dengan prefiks tipe. Label manusia
tidak menjadi identitas, sehingga variasi seperti `Kepulauan Riau` dan `Kep. Riau` tidak membuat
atau memutus hubungan lineage.

## Hasil

| Artefak graf | Jumlah |
|---|---:|
| Node | 101 |
| Edge | 235 |
| Core path observasi-ke-sumber | 38 |
| `indicator_cell` | 14 |
| `source_record` ter-resolve | 38 |
| Source path per sel | 2–3 |
| Kelengkapan path | 38/38 = 1,0000 |

Graf mencakup dua manifest sumber, tiga artefak fisik, tiga vintage, 38 observasi, satu batch
ingestion, satu run transformasi, dan satu versi transformasi. Semua 14 sel dapat dijangkau dari
setiap rekaman sumber yang termanifestasi untuk sel tersebut.

## Temuan granularitas locator

`source_record_id` WebAPI sudah memuat koordinat variabel, wilayah, dan periode. Sebaliknya, empat
locator publikasi PDF hanya menunjuk halaman, kolom, serta tahun dan dipakai ulang oleh 20
observasi provinsi. Menganggap locator mentah tersebut sebagai primary key akan menggabungkan
beberapa provinsi menjadi satu rekaman semu.

H6C mempertahankan locator mentah dan jumlah pemakaiannya, lalu membentuk identitas node rekaman
dari:

`artifact checksum + source_record_id + indicator + series + period + geo level + geo code`

Seluruh unsur tambahan berasal dari kolom eksplisit H6. Ini menyelesaikan 38 node rekaman secara
deterministik tanpa menebak label atau posisi baris PDF. Resolusi tersebut adalah keputusan
lineage, bukan klaim bahwa locator publikasi mentah sudah record-exact.

## Invariant dan batas interpretasi

Tujuh invariant lulus: kontrak graf cocok, identitas node/edge unik, seluruh core path lengkap,
38 rekaman ter-resolve, collision locator diungkap, semua sel dapat dijangkau, dan tidak ada fuzzy
matching. Kelengkapan `1,0000` hanya berlaku pada 38 observasi fixture H6; ia tidak boleh
digeneralisasi ke seluruh 7.666 observasi H4 sebelum jalur yang sama dijalankan pada dataset penuh.

H6C juga belum memetakan node metrik atau tabel hasil eksperimen. Keduanya baru dapat ditambahkan
setelah perlakuan menghasilkan output, sehingga pekerjaan H7–H9 Jalur C harus memperluas graf ini,
bukan mengubah identitas sumber yang sudah dibekukan.

## Artefak dan reproduksi

- `contracts/h6c-cell-lineage.json`: tipe node, relationship, identitas, dan aturan resolusi;
- `results/processed/h6c-lineage-nodes.csv`: 101 node graf;
- `results/processed/h6c-lineage-edges.csv`: 235 edge terarah;
- `results/processed/h6c-cell-source-paths.csv`: 38 core path beserta audit locator;
- `results/processed/h6c-lineage-validation.csv`: hasil tujuh invariant;
- `data/manifests/h6c-cell-lineage.json`: checksum input-output;
- `tests/unit/test_h6c.py`: uji determinisme, reachability, collision, dan larangan fuzzy matching.

Jalankan:

```bash
make h6c-run
make test
```

Eksekusi diverifikasi pada 9 September 2026 di `sigerciv@34.128.67.92` setelah VM menarik commit
`3211bb6` dari `main`. Marker `H6C_VERIFY|101|235|38|14|4|20|1.0000|validated` membuktikan 101
node, 235 edge, 38 path untuk 14 sel, empat kelompok collision yang memengaruhi 20 observasi,
kelengkapan `1,0000`, dan status `validated`. Seluruh 48 tes yang dapat dijalankan di VM lulus;
satu tes ekstraksi PDF H3 dilewati karena payload mentah tidak disimpan di Git. Clone VM tetap
bersih setelah reproduksi.
