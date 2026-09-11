# H9 Jalur C — Audit B3, Impact Lineage, dan Penutupan Empat Perlakuan

## Status dan batas lingkup

H9C menambahkan B3 ke bukti yang sudah ditutup H8C. Pekerjaannya tiga:

1. mengaudit 38 permintaan B3 dengan prosedur sepuluh langkah H8C yang sama persis;
2. memeriksa ulang, secara independen dari Jalur A, bahwa sel kotor B3 memang berasal dari lineage;
3. memperluas graf H8C sehingga keempat perlakuan mencapai metrik, tabel bukti, dan data gambar yang
   sama.

Marker validasi `make h9c-run`:

```text
H9C_VERIFY|294|810|377|1088|152|104|48|1.0000|4|38|38|0|validated
```

Artinya: graf dasar 294 node dan 810 edge, graf tertutup 377 node dan 1.088 edge, 152 permintaan,
104 sukses, 48 tidak tersedia, completeness 1,0000, empat perlakuan, 38 permintaan B3 sukses, 38
baris impact diaudit, 0 selisih impact, dan status tervalidasi.

H9C merupakan pipeline Python murni yang deterministik. Verifikasi dua kali di VM belum dilakukan
karena alamat VM eksperimen tidak lagi mengarah ke mesin penelitian (lihat laporan H9A). Dua run
lokal pada unit test menghasilkan keluaran yang sama byte demi byte.

## Prosedur audit yang dibekukan

H9C tidak membuat prosedur baru. Berkas `config/h8c/reproducibility_audit_steps.csv` harus sama
byte demi byte dengan checksum yang dicatat pada manifest H8C. Bila berkas itu berubah, bahkan hanya
karena satu baris kosong tambahan, run berhenti. Dengan cara ini B3 tidak diaudit dengan standar
yang lebih longgar daripada B0–B2.

Baris audit B0, B1, dan B2 disalin dari keluaran H8C yang sudah diverifikasi checksum-nya, tanpa
dihitung ulang. Metrik ketiganya kemudian dihitung lagi dari baris salinan tersebut dan wajib sama
dengan metrik H8C. Hanya 38 baris B3 yang dihitung baru.

## Recomputasi independen B3

Untuk setiap `observation_id`:

- store B3 dicari dengan kunci `(cell_id, vintage_id)`;
- hasil yang dilaporkan H9A (`available_by_vintage_key`, `result`, dan `current_observation_id`)
  harus sama dengan hasil pencarian;
- pembacaan yang berhasil harus cocok pada ID observasi, nilai desimal, dan `value_lexeme`;
- permintaan harus menunjuk tepat satu `source_lineage_path_id` H6C.

Kelas akses baru, `vintage_key`, dipakai untuk pembacaan historis B3. Kelas ini dipisahkan dari
`historical_snapshot` milik B1 agar mekanisme keduanya tidak tercampur dalam tabel hasil.

## Hasil audit empat perlakuan

| Perlakuan | Permintaan | Serving | Snapshot historis | Kunci vintage | Gagal | Tingkat sukses |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 38 | 14 | 0 | 0 | 24 | 0,3684 |
| B1 | 38 | 14 | 24 | 0 | 0 | 1,0000 |
| B2 | 38 | 14 | 0 | 0 | 24 | 0,3684 |
| B3 | 38 | 14 | 0 | 24 | 0 | 1,0000 |

Totalnya 152 permintaan: 104 dapat dipanggil dan 48 tidak tersedia. Seluruh 48 kegagalan berasal
dari kebijakan B0 dan B2, dan tetap dihitung sebagai kegagalan reproducibility. B1 dan B3 sama-sama
mencapai 38/38, tetapi melalui mekanisme berbeda. Perbedaan ongkos keduanya baru dapat dinilai pada
H10.

## Audit impact lineage

Jalur A menentukan sel kotor dari graf H6C. Jalur C menurunkannya ulang dari graf tertutup H8C,
yang memuat edge H6C tanpa perubahan, lalu memeriksa empat hal:

1. setiap observasi di store mempunyai tepat satu baris impact dan satu edge
   `observation_materializes_cell`;
2. sel dan edge hasil penurunan ulang sama dengan yang dilaporkan H9A, serta sama dengan `cell_id`
   observasi H6;
3. jumlah sel kotor unik per kedatangan sama dengan `dirty_cells` dan `recomputed_cells` pada katalog
   kedatangan, yaitu 14, 14, dan 10;
4. setiap baris serving terakhir dihitung ulang pada kedatangan terakhir yang membuat selnya kotor:
   4 sel pada kedatangan 2 dan 10 sel pada kedatangan 3.

Pemeriksaan keempat membuktikan bahwa tidak ada sel yang dihitung ulang tanpa disentuh lineage, dan
tidak ada sel tersentuh yang terlewat pada kedatangan terakhirnya. Hasilnya 38 baris impact dengan 0
selisih.

## Penutupan graf

Graf H8C (294 node, 810 edge) disalin tanpa mengubah identitas maupun field dasarnya. H9C
menambahkan 83 node dan 278 edge:

| Tambahan | Jumlah | Fungsi |
|---|---:|---|
| `treatment_run` B3 | 1 | run B3 yang diikat ke checksum manifest H9 |
| `arrival_batch` | 3 | satu node per kedatangan rilis, dengan checksum state serving |
| `treatment_decision` dan `treatment_output` B3 | 38 + 38 | keputusan dan keluaran per permintaan |
| `reproducibility_metric` B3 | 1 | metrik B3; node metrik B0–B2 dipakai ulang dari H8C |
| `evidence_table` dan `figure_input` empat perlakuan | 1 + 1 | tabel dan data gambar B0–B3 |
| `treatment_run_applies_arrival`, `vintage_defines_arrival` | 3 + 3 | run → kedatangan ← vintage H6C |
| `observation_arrives_in_batch` | 38 | observasi → kedatangan tempat ia disimpan |
| `arrival_recomputes_cell` | 38 | kedatangan → sel kotor; evidence menyebut ID edge lineage H6C |
| edge keputusan, output, metrik, tabel, dan prosedur B3 | 196 | pola yang sama dengan B0–B2 |

Tabel dan data gambar H8C yang lama tetap ada di graf sebagai bukti sejarah. Seluruh 152 path
penutupan menunjuk ke tabel dan data gambar empat perlakuan yang baru. Path B3 juga mencatat node
kedatangan dan edge penghitungan ulang yang dilaluinya. Completeness mencapai `1,0000`.

## Batas klaim

- Data gambar delapan baris hanya berfungsi sebagai sumber grafik. Gambar manuskrip belum dirender.
- Tidak ada waktu, byte, maupun hasil workload tersuntik yang diukur atau diklaim.
- Completeness 1,0000 berlaku pada 152 permintaan workload H6, bukan pada seluruh 7.666 observasi H4.
- Gate G2 belum lolos: keempat perlakuan belum dijalankan pada beban revisi tersuntik yang identik,
  B3 belum diverifikasi di Iceberg VM, dan berkas freeze H10 belum ditulis.

## Reproduksi

```bash
make h9-run
make h9c-run
make test
```

`make h9c-run` membutuhkan manifest H9A yang valid. Bila H9A dijalankan ulang dan keluarannya
berubah, H9C juga harus dijalankan ulang.

## Artefak audit

- kontrak: `contracts/h9c-b3-lineage-audit.json`;
- prosedur beku (milik H8C): `config/h8c/reproducibility_audit_steps.csv`;
- pipeline: `src/kkciv_vintage/h9c/`;
- 152 baris audit: `results/processed/h9c-reproducibility-audit.csv`;
- 38 baris audit impact: `results/processed/h9c-impact-audit.csv`;
- metrik empat perlakuan: `results/processed/h9c-reproducibility-metrics.csv`;
- tabel bukti: `results/processed/h9c-reproducibility-table.csv`;
- data gambar: `results/processed/h9c-reproducibility-figure-data.csv`;
- 377 node: `results/processed/h9c-lineage-nodes.csv`;
- 1.088 edge: `results/processed/h9c-lineage-edges.csv`;
- 152 path tertutup: `results/processed/h9c-evidence-closure.csv`;
- invariant: `results/processed/h9c-validation.csv`;
- ringkasan: `results/processed/h9c-summary.csv`;
- manifest: `data/manifests/h9c-b3-lineage-audit.json`.

## Hal yang memerlukan audit manusia

1. Setujui pemisahan kelas akses `vintage_key` (B3) dari `historical_snapshot` (B1).
2. Setujui bahwa baris audit B0–B2 disalin dari H8C tanpa dihitung ulang, dengan metrik yang
   dicocokkan kembali.
3. Periksa bahwa `arrival_recomputes_cell` merupakan representasi yang tepat untuk "sel yang
   benar-benar terpengaruh" pada klaim B3.
4. Setelah H9A lulus di Iceberg VM, pastikan marker `H9_VERIFY` dicatat. Setelah itu H9C tidak perlu
   diubah selama keluaran H9A tetap sama.
