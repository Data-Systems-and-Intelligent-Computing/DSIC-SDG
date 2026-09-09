# H8 Jalur A — B1 Snapshot Penuh

## Status

H8 Jalur A mengimplementasikan perlakuan B1 pada workload revisi nyata yang sama dengan B0:
38 observasi, 14 sel stabil, dan tiga rilis berurutan. Implementasi logis serta uji unit telah
lulus. Integrasi Iceberg melalui `make h8-apply` pada VM eksperimen juga lulus dengan marker
`H8_VERIFY|3|42|14|38|0|3|0|0|0|0`. Pada VM, 58 test lulus dan satu test ekstraksi PDF dilewati
karena data mentahnya memang tidak disimpan di Git.

## Kontrak perlakuan

B1 mempertahankan satu keadaan tabel lengkap untuk setiap rilis. Urutan rilis ditentukan sebelum
state dibentuk, yaitu `vintage_date`, `retrieved_at`, lalu `vintage_id` secara menaik. Setiap rilis
diterapkan ke state berjalan, kemudian seluruh 14 sel ditulis ulang dengan `INSERT OVERWRITE`.
Snapshot Iceberg yang terbentuk tidak kedaluwarsa selama run B1.

Tabel target adalah `kkciv.experiments.b1_indicator_full_snapshots`. Kolom H6 dipertahankan utuh,
lalu ditambahkan `snapshot_order`, `state_snapshot_key`, dan `applied_vintage_id`. Kunci
`state_snapshot_key` bersifat deterministik untuk audit logis; pemanggilan fisik di Iceberg memakai
`snapshot_id` yang dibuat katalog ketika commit berlangsung.

Sebelum satu run lengkap, script menjatuhkan dan membuat ulang hanya tabel eksperimen B1. Langkah
ini membuat rerun idempoten dan mencegah snapshot dari run sebelumnya ikut dihitung sebagai rilis
baru. Tabel H6, B0, B2, dan artefak input tidak diubah.

## Keadaan yang dibentuk

| Snapshot | Rilis yang diterapkan | Baris masuk | Baris keadaan penuh | Dampak pada state |
|---:|---|---:|---:|---|
| 1 | TPB 2024 | 14 | 14 | 14 sel pertama dibuat |
| 2 | TPB 2025 | 14 | 14 | 4 nilai berubah dan 10 nilai sama memperoleh provenance baru |
| 3 | WebAPI 2026 | 10 | 14 | 10 sel berubah; 4 sel TPB 2025 dibawa maju |

Ketiga state penuh menghasilkan 42 kemunculan baris. Ada 38 identitas observasi unik; selisih empat
baris adalah observasi TPB 2025 yang disalin ke snapshot ketiga karena WebAPI tidak menyediakan
pengganti untuk sel tersebut.

State terakhir B1 dibandingkan pada seluruh kolom observasi H6 dengan state latest-vintage B0.
Keduanya sama persis: 10 sel berasal dari WebAPI 2026 dan empat sel tetap berasal dari TPB 2025.
Perbedaannya adalah B1 masih memiliki dua snapshot lama, sedangkan B0 hanya menyisakan state kini.

## Audit reproducibility

Setiap `observation_id` dari 38 masukan dicari pada seluruh keadaan snapshot logis. Hasilnya:

- 14 observasi dapat ditemukan pada snapshot current;
- 24 observasi lama dapat ditemukan pada snapshot historis;
- tidak ada permintaan yang gagal;
- tingkat keberhasilan adalah `38/38 = 1,0000`.

Script integrasi mengulang pemeriksaan tersebut terhadap tiga `snapshot_id` Iceberg aktual dengan
`VERSION AS OF`. Script juga memeriksa jumlah snapshot, 42 baris lintas time travel, 14 baris
current, duplikasi sel per snapshot, kesamaan state dengan CSV ber-checksum, serta pemetaan setiap
permintaan ke snapshot yang benar.

## Batas pengukuran H8

Angka 42 adalah jumlah kemunculan baris logis, bukan ukuran penyimpanan fisik. H8 belum mengklaim
jumlah byte, waktu tulis, waktu baca, atau keunggulan performa apa pun. Pengukuran ruang dan uji
pemanggilan ulang terukur dijadwalkan pada H10 setelah batas sumber daya dan harness eksperimen
dibekukan. Pemisahan ini mencegah hasil validasi fungsi VM 2-vCPU disalahartikan sebagai hasil
performa.

## Reproduksi

```bash
make h8-run
make test
make h8-apply
```

`make h8-run` memvalidasi semua input bermanifest, membangun artefak deterministik, membandingkan
state akhir dengan B0, dan menulis manifest H8. `make h8-apply` mengulang tahap logis, membuat tiga
snapshot Iceberg, lalu membaca masing-masing snapshot kembali.

Pada integrasi pertama, proses Spark di dalam loop shell ikut mengonsumsi stdin katalog sehingga
run berhenti setelah snapshot pertama. Guard jumlah snapshot menolak hasil `got 1`. Stdin proses
Docker kemudian dialihkan dari `/dev/null`; rerun yang bersih memproses ketiga rilis. Catatan ini
dipertahankan agar kegagalan integrasi tidak hilang dari audit.

Commit implementasi adalah `64eb50f`; perbaikan isolasi stdin adalah `d733799`.

## Artefak audit

- kontrak: `contracts/h8-b1-full-snapshot.json`;
- DDL: `infra/spark/h8-b1.sql`;
- pipeline: `src/kkciv_vintage/h8/`;
- integrasi Iceberg: `scripts/h8_apply.sh`;
- katalog snapshot logis: `results/processed/h8-b1-snapshot-catalog.csv`;
- 42 state rows: `results/processed/h8-b1-snapshot-states.csv`;
- state current: `results/processed/h8-b1-current-state.csv`;
- audit 38 permintaan: `results/processed/h8-b1-reproducibility.csv`;
- invariant: `results/processed/h8-b1-validation.csv`;
- ringkasan: `results/processed/h8-b1-summary.csv`;
- manifest: `data/manifests/h8-b1-full-snapshot.json`.

## Hal yang memerlukan audit manusia

1. Setujui bahwa “snapshot penuh” pada eksperimen ini berarti seluruh state 14 sel ditulis ulang
   sekali per rilis, bukan hanya commit metadata atas perubahan parsial.
2. Setujui bahwa empat sel yang tidak ada pada WebAPI 2026 memang dibawa maju dari TPB 2025.
3. Pastikan kebijakan drop-and-recreate khusus tabel B1 dapat diterima untuk rerun eksperimen.
4. Jangan menggunakan 42 kemunculan baris sebagai pengganti ukuran byte; ukuran fisik baru sah
   setelah protokol H10 dijalankan.
