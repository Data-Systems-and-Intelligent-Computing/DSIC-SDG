# H8 Jalur C — Audit Reproducibility dan Penutupan Lineage Bukti

## Status dan batas lingkup

H8C mengaudit B0, B1, dan B2 karena hanya ketiga perlakuan tersebut yang sudah berjalan. B3
sengaja tidak diberi baris hasil, node perlakuan, atau metrik; prosedur yang sama wajib dijalankan
ulang setelah B3 diimplementasikan pada H9. Dengan batas ini, H8C menutup lineage bukti yang sudah
ada tanpa menutup Gate G2 terlalu dini.

## Prosedur audit

Prosedur berisi sepuluh langkah berurutan:

1. memverifikasi checksum manifest dan output;
2. mengunci 38 `observation_id` yang sama untuk setiap perlakuan;
3. membangun ulang state perlakuan secara terisolasi;
4. menjalankan perlakuan satu per satu;
5. merekam locator baca current, selected, atau snapshot;
6. membandingkan identitas observasi;
7. membandingkan nilai desimal dan bentuk angka terbit;
8. menghubungkan permintaan ke path sumber H6C;
9. memberi kelas eksplisit untuk setiap nilai yang tidak tersedia;
10. menghitung metrik hanya setelah audit baris lulus dan menyimpan seluruh bukti ber-checksum.

Tujuh langkah dimiliki pipeline audit. Tiga langkah yang menyentuh state fisik—reset, eksekusi
serial, dan perekaman locator—wajib dilaksanakan adapter perlakuan. Pembagian ini mencegah pipeline
analisis mengklaim telah menjalankan query fisik yang sebenarnya belum dilakukan.

## Recomputasi independen

H8C tidak sekadar menyalin kolom hasil reproducibility. Addressability dihitung ulang dari state:

- B0: `requested_observation_id` dibandingkan dengan observasi current untuk `cell_id` yang sama;
- B1: ID dicari pada ketiga state snapshot dan urutan kemunculannya dibandingkan dengan locator;
- B2: ID dibandingkan dengan observasi hasil pemilihan sumber untuk sel yang sama.

Permintaan yang dilaporkan sukses kemudian harus cocok pada tiga lapis: ID observasi, nilai
`DECIMAL(38,10)`, dan `value_lexeme`. Setiap permintaan juga harus mempunyai tepat satu
`source_lineage_path_id` H6C. Hasil yang tidak tersedia pada B0/B2 diberi kelas
`expected_unavailable_by_treatment_policy`; kegagalan tanpa kelas dilarang kontrak.

## Hasil audit

| Perlakuan | Permintaan | Sukses di state serving | Sukses lewat snapshot historis | Gagal | Tingkat sukses |
|---|---:|---:|---:|---:|---:|
| B0 | 38 | 14 | 0 | 24 | 0,3684 |
| B1 | 38 | 14 | 24 | 0 | 1,0000 |
| B2 | 38 | 14 | 0 | 24 | 0,3684 |

Total 114 permintaan menghasilkan 66 pembacaan sukses dan 48 nilai tidak tersedia sesuai desain.
Semua 66 pembacaan sukses cocok tepat pada identitas, nilai desimal, serta lexeme. Tidak ada
perbedaan antara hasil yang dilaporkan dan recomputasi independen.

## Penutupan graf

Graf H7C sebanyak 207 node dan 491 edge disalin tanpa mengubah identitas maupun field dasarnya.
H8C menambahkan:

- satu run B1, 38 keputusan B1, dan 38 output observasi B1;
- tiga node state snapshot dan 42 edge kemunculan observasi pada snapshot;
- satu prosedur audit dan satu node harness H8B;
- tiga node metrik reproducibility;
- satu node tabel bukti dan satu node data gambar.

Graf tertutup berisi 294 node dan 810 edge. Sebanyak 114 path menghubungkan rekaman sumber,
observasi, run, keputusan, output, metrik, tabel, data gambar, dan prosedur audit dengan completeness
`1,0000`.

Data gambar berisi enam baris addressable/unavailable untuk tiga perlakuan. Ini adalah input gambar,
bukan gambar manuskrip yang sudah dirender. Rendering dan analisis hasil tetap menunggu B3 serta
eksperimen utama.

## Keterhubungan dengan H8B

Manifest harness H8B menjadi node `workload_harness` dan dihubungkan ke prosedur audit. Hubungan
ini berarti setiap route revisi tersuntik kelak harus melewati sepuluh langkah yang sama. Ia tidak
berarti 20 route H8B sudah dieksekusi. Persetujuan manusia tentang tepat satu sumber per run utama
juga divalidasi sebelum node harness diterima.

## Reproduksi

```bash
make h8c-run
make test
```

Marker yang diperoleh dua kali, baik lokal maupun di VM:

```text
H8C_VERIFY|207|491|294|810|114|66|48|1.0000|3|10|7|3|validated
```

Implementasi pada commit `c123402` ditarik ke VM dengan `git pull --ff-only`. Sebelas checksum
keluaran identik pada dua run VM. Test penuh menjalankan 69 test: 68 lulus dan satu test ekstraksi
PDF dilewati karena PDF mentah tidak tersedia di checkout Git. Working tree VM tetap bersih.

## Artefak audit

- kontrak: `contracts/h8c-reproducibility-lineage.json`;
- prosedur sumber: `config/h8c/reproducibility_audit_steps.csv`;
- 114 audit baris: `results/processed/h8c-reproducibility-audit.csv`;
- tiga metrik: `results/processed/h8c-reproducibility-metrics.csv`;
- tabel bukti: `results/processed/h8c-reproducibility-table.csv`;
- data gambar: `results/processed/h8c-reproducibility-figure-data.csv`;
- 294 node: `results/processed/h8c-lineage-nodes.csv`;
- 810 edge: `results/processed/h8c-lineage-edges.csv`;
- 114 path tertutup: `results/processed/h8c-evidence-closure.csv`;
- salinan prosedur bermanifest: `results/processed/h8c-audit-procedure.csv`;
- validasi dan ringkasan: `results/processed/h8c-validation.csv` dan `h8c-summary.csv`;
- manifest: `data/manifests/h8c-reproducibility-lineage.json`.

## Hal yang memerlukan audit manusia

1. Setujui pembagian tujuh langkah pipeline dan tiga langkah adapter perlakuan.
2. Periksa bahwa “tidak tersedia sesuai kebijakan” tetap dihitung gagal reproducibility, walaupun
   audit pelaksanaannya lulus.
3. Setujui bahwa data gambar enam baris cukup sebagai endpoint lineage sementara; gambar final
   belum boleh diklaim.
4. Setelah B3 tersedia, tambahkan 38 permintaan B3 dan jangan memakai completeness `1,0000` H8C
   sebagai pengganti audit B3.
