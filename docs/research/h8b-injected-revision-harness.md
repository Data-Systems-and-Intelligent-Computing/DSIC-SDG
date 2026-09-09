# H8 Jalur B — Harness Revisi Tersuntik

## Status

H8 Jalur B membangun generator revisi sintetis yang deterministik dan dapat memberikan payload
yang sama kepada B0, B1, B2, serta B3. Tahap ini memvalidasi pembentukan workload; belum ada
perlakuan yang dijalankan, belum ada waktu yang diukur, dan konfigurasi eksperimen utama belum
dibekukan. VM menarik commit `5c3969c`, menjalankan pipeline dua kali dengan checksum identik,
serta menghasilkan marker yang sama dengan lokal. Sebanyak 62 test VM lulus dan satu test PDF
dilewati karena data mentahnya tidak disimpan di Git; worktree tetap bersih.

## Mengapa fixture B0 dipakai sebagai titik awal

State akhir B0 adalah representasi latest-vintage satu baris per `cell_id`. B1 terbukti mempunyai
state akhir yang sama pada H8A. Karena itu state tersebut dipakai hanya sebagai nilai sebelum
injeksi dan daftar 14 sel stabil. Penggunaan state B0 di sini tidak berarti kebijakan overwrite
dianggap benar; ia menyediakan titik awal kanonik agar nilai sesudah revisi tidak bergantung pada
perlakuan yang akan diuji.

Setiap baris juga dipetakan kembali ke dimensi vintage H6 untuk mendapatkan `revised_source_id`.
Kolom ini memberi tahu adapter B2 skor sumber beku mana yang harus dipakai. Identitas record baru
tetap `synthetic_revision_harness` dengan kelas `synthetic_not_official`, sehingga hasil injeksi
tidak dapat disalahartikan sebagai rilis BPS yang benar-benar terbit.

## Profil validasi

Konfigurasi H8B berisi lima ukuran bertingkat:

| Skenario | Sel direvisi | Proporsi fixture | Status |
|---|---:|---:|---|
| `validation_001` | 1 | 7,1429% | `validation_only` |
| `validation_002` | 2 | 14,2857% | `validation_only` |
| `validation_004` | 4 | 28,5714% | `validation_only` |
| `validation_007` | 7 | 50,0000% | `validation_only` |
| `validation_014` | 14 | 100,0000% | `validation_only` |

Seed `20260909` ditulis eksplisit di konfigurasi. Semua sel diranking satu kali menggunakan
SHA-256 atas seed dan `cell_id`, lalu skenario ukuran `k` mengambil `k` peringkat pertama. Dengan
demikian skenario 1 merupakan subset skenario 2, skenario 2 merupakan subset skenario 4, dan
seterusnya. Tidak ada random state dari waktu eksekusi.

Profil ini hanya membuktikan mekanisme pada fixture kecil. Ia bukan daftar ukuran final untuk H11
dan belum mewakili satu tahun penuh seluruh provinsi. Konfigurasi final baru boleh dibekukan pada
akhir H10 setelah workload provinsi dan batas sumber daya diputuskan.

## Aturan perubahan nilai

Nilai setiap sel terpilih ditambah satu unit pada presisi yang diterbitkan. Contoh nilai dengan dua
angka desimal berubah dari `1.18` menjadi `1.19`, dengan delta eksak `0.01`. Jika nilai persentase
akan melewati 100, arahnya dibalik menjadi minus satu unit. Penyimpanan tetap memakai
`DECIMAL(38,10)` dan bentuk angka publikasi baru disimpan terpisah.

Dimensi pembentuk sel—indikator, seri, periode, geografi, dan unit—tidak diubah. Setiap baris
menyimpan nilai sebelum, delta, nilai sesudah, observasi dasar, vintage dasar, sumber yang
disimulasikan direvisi, serta ID sintetis deterministik. Ini membuat injeksi dapat diaudit dan
dibalik tanpa menebak nilai awal.

## Kesamaan input keempat perlakuan

Harness menghasilkan satu file kanonik dan 20 route: lima skenario dikalikan empat perlakuan.
Untuk satu skenario, B0, B1, B2, dan B3 menunjuk filter, jumlah baris, serta SHA-256 payload yang
sama. Tidak ada salinan yang dapat bermutasi berbeda per perlakuan.

Status seluruh route masih `prepared_not_run`. B3 belum diimplementasikan dan adapter eksekusi
masing-masing perlakuan belum dijalankan pada H8. Karena itu route B3 membuktikan kesiapan bentuk
input, bukan keberhasilan B3.

## Hasil validasi

- 14 sel dasar unik;
- lima skenario dengan ukuran `1-2-4-7-14`;
- 28 baris injeksi bila kelima skenario dihitung sebagai run independen;
- empat perlakuan dan 20 route;
- nol checksum payload yang berbeda antarperlakuan;
- seluruh sembilan invariant lulus;
- nol run waktu dan nol pengukuran penyimpanan.

Marker pipeline:

```text
H8B_VERIFY|14|5|1-2-4-7-14|28|4|20|0|0|validation_ready
```

Marker tersebut telah diperoleh dua kali berturut-turut di VM, bukan hanya dihitung sebagai
ekspektasi lokal.

## Reproduksi

```bash
make h8b-run
make test
```

Pipeline membaca input bermanifest, membangun ulang seluruh artefak, lalu memverifikasi checksum
dan jumlah baris. Pengujian menjalankan pipeline dua kali dan membandingkan byte semua keluarannya.

## Artefak audit

- kontrak: `contracts/h8b-injected-revision-harness.json`;
- konfigurasi skenario: `config/h8b/injection_scenarios.csv`;
- pipeline: `src/kkciv_vintage/h8b/`;
- rencana lima skenario: `results/processed/h8b-injection-plan.csv`;
- 28 perubahan sintetis: `results/processed/h8b-injected-revisions.csv`;
- 20 route perlakuan: `results/processed/h8b-treatment-routes.csv`;
- invariant: `results/processed/h8b-validation.csv`;
- ringkasan: `results/processed/h8b-summary.csv`;
- manifest: `data/manifests/h8b-injected-revision-harness.json`.

## Hal yang memerlukan audit manusia

1. Setujui penggunaan latest-vintage sebagai nilai awal kanonik injeksi.
2. Tinjau aturan satu unit pada presisi publikasi; aturan ini dibuat untuk mengubah dependensi sel,
   bukan meniru distribusi besar revisi BPS.
3. Tentukan apakah sweep utama harus merevisi tepat satu sumber per run. Profil validasi dapat
   memuat `revised_source_id` berbeda karena tujuannya menguji mekanisme umum.
4. Jangan menyebut ukuran `1-2-4-7-14` sebagai freeze eksperimen utama.
5. Adapter H9/H10 harus memakai `revised_source_id` untuk keputusan B2 dan tidak boleh memberi skor
   ke identitas sintetis.
