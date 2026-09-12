# Kerangka Tabel dan Gambar Hasil

Ditulis Jalur A dan Jalur C pada H11, 13 September 2026, bersamaan dengan sweep utama yang dipegang
operator Jalur B. Berkas ini menetapkan bentuk tabel dan gambar bagian Hasil sebelum angkanya
ditafsirkan, sehingga pemilihan tabel tidak dipengaruhi hasil yang sudah dilihat. Isi angkanya
dikerjakan pada H15 sesuai §6.5 README utama.

Aturan §1 draf tetap berlaku: tidak ada angka yang diketik ulang. Setiap sel tabel diambil dari
`papers/vintage_reconciliation/data/` melalui `metric_id` pada `angka-kunci.csv` atau langsung dari
tabel sumber yang tercantum di bawah. Paket dibentuk dengan `make article-bundle`, yang memverifikasi
checksum setiap sumber terhadap manifest tahapnya.

## Tabel

| ID | Pertanyaan | Judul kerja | Baris | Kolom | Sumber |
|---|---|---|---|---|---|
| T1 | P1 | Cakupan indikator dan kanal yang dipakai | 5 domain | kandidat, verified, partial, unavailable | `p1-karakterisasi/h1-indicator-coverage.csv` |
| T2 | P1 | Ketidaksesuaian antarsumber dan antarrilis | domain | sel dibandingkan, sel berbeda, pemeriksaan granularitas | `p1-karakterisasi/h3-*.csv` |
| T3 | P1 | Distribusi sebab ketidaksesuaian | sebab × tingkat bukti | kejadian, proporsi | `p1-karakterisasi/p1-distribusi-sebab.csv` |
| T4 | P2 | Fixture bukti dengan vintage eksplisit | 3 vintage | observasi, sel, rentang tahun | `p2-representasi/h6-*.csv` |
| T5 | P2 | Rekonstruksi state per rilis: B3 terhadap snapshot B1 | 3 rilis | baris state, selisih terhadap B1 | `p2-representasi/h9-b3-asof-states.csv` |
| T6 | P3 | Ongkos satu revisi pada fixture 14 sel | 4 perlakuan | pernyataan tulis, waktu tulis, pemeliharaan, byte | `p3-ongkos/h10b-apply-cost.csv` |
| T7 | P3 | Keadaan dasar sweep dan yang ditulis tiap perlakuan | 4 perlakuan | baris dasar, snapshot, sel dievaluasi, baris ditulis | `p3-ongkos/h11-sweep-scenarios.csv` |
| T8 | P3 | Waktu penghitungan ulang per titik sweep | 6 titik | B0, B1, B2, B3 (median, rentang) | `p3-ongkos/h11-apply-cost.csv` |
| T9 | P3 | Pertambahan byte per titik sweep | 6 titik | B0, B1, B2, B3 (data dan metadata) | `p3-ongkos/h11-apply-cost.csv` |
| T10 | P3 | Titik impas inkremental | 3 pembanding × 2 ukuran | arah, titik silang, nilai per titik | `p3-ongkos/h11-breakeven.csv` |
| T11 | P3 | Ruang penyimpanan total keempat perlakuan | 4 perlakuan | total, data, metadata | `p3-ongkos/h10-storage-by-treatment.csv` |
| T12 | P4 | Keberhasilan memanggil ulang angka terbit, fixture | 4 perlakuan | permintaan, berhasil, rasio, jalur akses | `p4-reproducibility/h9c-reproducibility-table.csv` |
| T13 | P4 | Recall pada panel setelah revisi | 6 titik × 4 perlakuan | permintaan resmi, sintetis, rasio | `p4-reproducibility/h11-recall.csv` |
| T14 | Pembahasan | Propagasi revisi menurut kebijakan sumber | skenario | B0, B1, B2, B3 | `pembahasan-b2/h11-propagation.csv`, `p3-ongkos/p3-propagasi-revisi.csv` |

T1 sampai T6, T11, T12, dan T14 bagian H9B sudah dapat diisi dari hasil yang ada. T7 sampai T10 dan
T13 menunggu agregasi sweep H11.

## Gambar

| ID | Judul kerja | Sumbu x | Sumbu y | Seri | Sumber |
|---|---|---|---|---|---|
| G1 | Waktu penghitungan ulang terhadap besaran revisi | sel direvisi (1-38, linear) | detik (median tiga repetisi) | B0, B1, B2, B3 | `h11-apply-cost.csv` |
| G2 | Pertambahan byte terhadap besaran revisi | sel direvisi (1-38, linear) | byte (skala log) | B0, B1, B2, B3 | `h11-apply-cost.csv` |
| G3 | Sel yang dievaluasi terhadap besaran revisi | sel direvisi | sel dievaluasi (skala log) | B0, B1, B2, B3 | `h11-apply-cost.csv` |
| G4 | Recall angka terbit per perlakuan | perlakuan | rasio | permintaan resmi, sintetis | `h11-recall.csv`, `h9c-reproducibility-table.csv` |

Setiap gambar wajib memuat rentang minimum-maksimum tiga repetisi, bukan hanya median, dan keterangan
gambar wajib menyebut lingkungan beku 2 vCPU beserta batas klaimnya. Gambar tanpa keterangan itu
tidak boleh masuk naskah.

## Yang tidak dibuat gambarnya

Jumlah byte yang dibaca per pernyataan (metrik pendukung s2) tidak diukur, karena Spark SQL CLI pada
stack beku tidak mengekspos statistik tersebut. Hal ini dinyatakan di bagian Keterbatasan, bukan
ditutup dengan proksi.

Waktu tidak boleh digambarkan sebagai kurva skalabilitas terhadap ukuran panel, karena hanya satu
ukuran panel yang diukur. Sumbu x pada G1 sampai G3 adalah besaran revisi, bukan ukuran data.

## Klaim yang menunggu bukti

- `[Sumber belum mendukung klaim titik impas P3]` sampai T10 terisi dari `h11-breakeven.csv`.
- `[Sumber belum mendukung klaim analisis kegagalan]` sampai H13 menghasilkan minimal satu kasus
  kegagalan pemanggilan ulang di luar B0 dan B2 yang memang gagal sesuai desain.
