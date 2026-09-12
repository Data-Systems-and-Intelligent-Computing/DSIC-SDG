# Decision Log

Berkas ini mencatat keputusan operasional yang mengubah jalannya eksperimen: perbaikan yang memaksa
pengukuran diulang, run yang dibuang, dan pembersihan yang disetujui. Aturan §12 README utama
mewajibkan setiap pengulangan dicatat beserta alasannya; berkas inilah tempatnya.

Keputusan desain yang memerlukan persetujuan peninjau tidak dicatat di sini, melainkan di
`config/*/human_decisions.csv` dan dibekukan melalui `docs/research/experiment-freeze.md`.

## Catatan

| Tanggal | ID | Jenis | Kejadian | Alasan | Bukti |
|---|---|---|---|---|---|
| 2026-09-11 | `dl-01` | perbaikan infrastruktur | Katalog Iceberg REST dipindahkan dari SQLite in-memory ke berkas persisten, lalu seluruh tabel H5 sampai H9 dibangun ulang | Reboot VM menghapus seluruh registrasi tabel tanpa meninggalkan tanda pada data, sehingga B1 kehilangan kemampuan memanggil angka lama. Pengukuran ruang H10A tidak dapat dipercaya di atas katalog yang hilang saat restart | [`docs/research/h10-storage-recall.md`](h10-storage-recall.md) |
| 2026-09-12 | `dl-02` | pembersihan disetujui | 64 objek sisa run 9 September, 585.261 byte, dihapus dengan `remove_orphan_files` sebelum pengukuran H10B | Objek yatim dari run yang kehilangan registrasi tabel akan ikut terhitung pada listing ruang. Keputusan disetujui peninjau sebagai `h10b_orphan_cleanup` | [`config/h10/human_decisions.csv`](../../config/h10/human_decisions.csv), [`results/raw/h10b/cleanup-20260912/`](../../results/raw/h10b/cleanup-20260912/) |
| 2026-09-13 | `dl-03` | run dibuang | Dua run uji H11 satu skenario, `smoke-01` dan `smoke-02`, dibuang dan tidak masuk hasil | Pemeriksaan keadaan melaporkan 10.754 ketidaksesuaian palsu karena `EXCEPT` dan `UNION ALL` berbagi presedensi di Spark SQL. Setelah perbandingan diberi tanda kurung eksplisit, pemeriksaan kembali bernilai nol. Keduanya berstatus `limited_run=yes` sehingga tidak dapat diagregasi sebagai sweep utama | [`docs/research/h11-main-sweep.md`](h11-main-sweep.md) |
| 2026-09-13 | `dl-04` | run dibuang | Run uji H12 satu repetisi, `smoke-h12`, dibuang setelah gagal pada langkah footprint | Lokasi tabel diambil dari kolom yang salah pada baris keluaran footprint, sehingga listing MinIO tidak dapat dijalankan. Keempat perlakuan dan seluruh pemeriksaan keadaan pada run itu sudah benar, tetapi run tetap dibuang karena tidak lengkap | [`docs/research/h12-real-revision-cost.md`](h12-real-revision-cost.md) |
| 2026-09-13 | `dl-05` | pengulangan terukur | Titik pengukuran yang sebaran repetisinya melebihi ambang diukur ulang dengan tiga repetisi tambahan: skenario `sweep_001` pada H11 dan keempat kedatangan pada H12 | Aturan keraguan ditetapkan lebih dahulu, yaitu sebaran fase tulis melebihi 20 persen mediannya, lalu diterapkan secara mekanis pada seluruh titik. Median yang sudah dilaporkan tidak diganti; median gabungan dilaporkan berdampingan | [`docs/research/h13-rerun-stability.md`](h13-rerun-stability.md), [`contracts/h13-rerun-stability.json`](../../contracts/h13-rerun-stability.json) |
| 2026-09-13 | `dl-06` | koreksi angka | Dua median waktu tulis H12 dikoreksi menjadi median gabungan enam repetisi: kedatangan 2 perlakuan B2 dari 2,064 menjadi 2,250 detik, dan kedatangan 3 perlakuan B0 dari 3,497 menjadi 3,319 detik | Keduanya keluar dari pita stabilitas 5 persen pada H13. Selisih absolutnya 0,186 dan 0,178 detik dan tidak mengubah satu pun kesimpulan, tetapi aturan putusan H13 mewajibkan koreksi dicatat, bukan diserap diam-diam | [`docs/research/h13-rerun-stability.md`](h13-rerun-stability.md), [`results/processed/h13-stability.csv`](../../results/processed/h13-stability.csv) |

## Yang tidak dicatat di sini

Perbaikan kode yang tidak mengubah angka yang sudah diterbitkan, misalnya penataan ulang atau
penambahan pengujian, cukup terlihat pada riwayat Git. Yang masuk ke tabel di atas hanyalah kejadian
yang membuat sebuah pengukuran diulang, dibuang, atau dibersihkan.
