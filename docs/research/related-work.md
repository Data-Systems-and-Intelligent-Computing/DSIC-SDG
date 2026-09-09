# Related Work — SDG Data Systems (2020–2026)

Status: metadata seluruh sumber yang sebelumnya bertanda `daftar` diverifikasi pada 2026-09-09 melalui H7 Jalur C. Kolom **Verifikasi** menyatakan seberapa jauh sumber sudah diperiksa.

- `penuh` — PDF dibaca langsung, isi dan daftar pustakanya diperiksa.
- `metadata` — judul, venue, tahun, dan abstrak/ringkasan terverifikasi dari sumber resmi.
- `daftar` — baru muncul pada hasil pencarian; belum diverifikasi, jangan disitasi sebelum diperiksa.

H7C memeriksa 18 kemunculan `daftar` yang mewakili 15 sumber unik. Semuanya mempunyai halaman
primer dari penerbit, prosiding resmi, repositori preprint, lembaga penerbit, dokumentasi produk,
atau repositori proyek resmi sehingga dinaikkan menjadi `metadata`. Pemeriksaan ini tidak sama
dengan membaca penuh semua naskah. Tahun bibliografis juga diluruskan jika tahun terbit daring
berbeda dari tahun volume/prosiding. Inventaris bukti terstruktur berada di
[`config/h7c/related_work_verification.csv`](../../config/h7c/related_work_verification.csv).

---

## A. Perhitungan indikator SDG dari data terbuka heterogen

Ini pesaing terdekat. Kelompok Prancis (De Vinci Research Center, CEDRIC-CNAM, LASTIG-IGN) menguasai jalur ini.

| Sumber | Venue | Tahun | Verifikasi |
|---|---|---|---|
| Benjira, Travers, Atigui, Bucher, Grim-Yefsah. *SDG-KG: A Framework to Compute SDG Indicators with Open Data* | PVLDB 18(12): 5367–5370 | 2025 | penuh |
| Benjira, Atigui, Bucher, Grim-Yefsah, Travers. *Automated mapping between SDG indicators and open data: An LLM-augmented knowledge graph approach* | Data & Knowledge Engineering 156, 102405 | 2025 | metadata |
| Benjira, Atigui, Bucher, Grim-Yefsah, Travers. *Web Open Data to SDG Indicators: Towards an LLM-Augmented Knowledge Graph Solution* | WISE'24 | 2024 | metadata |
| Fotopoulou et al. *SustainGraph: A knowledge graph for tracking the progress and interlinking among the SDG targets* | Frontiers in Environmental Science 10 | 2022 | metadata |
| Jiang & Johnson. *Data Discovery for the SDGs: A Systematic Rule-based Approach* | GoodIT'23, 384–390 | 2023 | metadata |
| van Loenhout, Ranasinghe, Degbelo, Bouali. *Physicalizing Sustainable Development Goals Data: An Example with SDG 7* | CHI EA'22 | 2022 | metadata |
| [*Assessing the availability and interoperability of open government data (OGD) supporting SDGs and value creation in the GCC*](https://link.springer.com/article/10.1007/s11135-024-02025-2) | Quality & Quantity 59:1573–1593 | 2025 | metadata |

### Catatan penting tentang SDG-KG

SDG-KG adalah **demonstration paper empat halaman**, bukan artikel research track. Ini menetapkan tinggi mistar: VLDB menerima topik indikator SDG, tetapi pada jalur demo.

Isinya: Metadata Graph (dari sumber data) dipertemukan dengan SDG Graph (dari UN SDG Indicator Metadata Repository); pemetaan skema dibantu LLM (GPT-3.5); konflik antarsumber diselesaikan dengan *Trust Score Metric* yang menggabungkan kemiripan spasial/temporal/kontekstual, reliabilitas sumber, dan kelengkapan; hasilnya rencana eksekusi yang diterjemahkan ke kode Python/Pandas/GeoPandas. Disimpan di Neo4j.

Data: UN SDG Indicator Metadata Repository, INSEE, WorldPop, OpenDataParis, OpenStreetMap. Indikator yang didemokan: **11.2.1** (proporsi penduduk dengan akses mudah ke transportasi publik) — indikator spasial yang memerlukan spatial join dan perhitungan service area.

**Batasan yang mereka nyatakan sendiri:** SDG-KG bekerja pada tingkat metadata dan tidak memproses aliran data. Tidak ada evaluasi performa, tidak ada studi skalabilitas, tidak ada pembahasan penyimpanan fisik.

Celah yang tersisa dari sini jelas: seluruh lapisan fisik — bagaimana data itu benar-benar disimpan, dipartisi, dimaterialisasi, dan dihitung ulang ketika sumbernya berubah — belum digarap oleh jalur ini.

---

## B. Lakehouse sebagai objek penelitian sistem

| Sumber | Venue | Tahun | Verifikasi |
|---|---|---|---|
| [*Data Lakehouse: A survey and experimental study*](https://www.sciencedirect.com/science/article/pii/S0306437924001182) | Information Systems 127:102460 | 2025 | metadata |
| Jain et al. *Analyzing and Comparing Lakehouse Storage Systems (LHBench)* | CIDR | 2023 | metadata |
| *AutoComp: Automated Data Compaction for Log-Structured Tables in Data Lakes* | arXiv:2504.04186 | 2025 | metadata |
| *LakeVilla: A Modular and Non-Invasive Toolbox for Lakehouse Transactions* | arXiv:2504.20768 | 2025 | metadata |
| van Renen & Leis. *Cloud Analytics Benchmark* | PVLDB 16(6), 1413–1425 | 2023 | metadata |
| Alotaibi et al. *ESTOCADA: Towards Scalable Polystore Systems* | PVLDB 13(12) | 2020 | metadata |
| Barret, Manolescu, Upadhyay. *Computing Generic Abstractions from Application Datasets* | EDBT'24 | 2024 | metadata |

Empat sumber pertama juga terdaftar pada bacaan inti Katalog DSIC-RG (Terbaru 6, 7, 8, 12), sehingga selaras dengan arah kelompok riset.

---

## C. Lakehouse spasial — lapisan yang baru terbuka

Ini bagian paling menarik secara waktu. Dukungan geometri native baru masuk ke Iceberg pada 2025–2026, dan strategi partisi spasialnya secara eksplisit masih terbuka.

| Sumber | Bentuk | Tahun | Verifikasi |
|---|---|---|---|
| Apache Iceberg v3 — tipe `geometry` dan `geography` native, metadata bounding box, partisi spasial | Spesifikasi format | 2025–2026 | metadata |
| Apache Sedona **SpatialBench** v0.1.0 — benchmark SQL analitik geospasial lintas mesin | Benchmark + hasil single-node | Sep 2025 | metadata |
| **SedonaDB** — mesin analitik single-node dengan geospasial sebagai warga kelas satu | Rilis + blog | Sep 2025 | metadata |
| *Managing spatial tables in Data Lakehouses with Iceberg* | Blog Apache Sedona | Okt 2025 | metadata |

Hasil SpatialBench single-node yang dipublikasikan membandingkan **SedonaDB, DuckDB, dan GeoPandas** pada SF 1 dan SF 10. Temuannya: SedonaDB dan DuckDB setara dan jauh di atas GeoPandas pada skala lebih besar.

Dokumentasi Sedona menyatakan bahwa lapisan berikutnya — strategi partisi spasial, indeks spasial di luar bounding box, dan integrasi predikat spasial dengan perencanaan query — masih dalam pengembangan aktif, dan pengguna diminta memeriksa dukungan tiap mesin. **Ini pernyataan celah dari pihak pengembang sendiri, bukan dugaan.**

---

## D. Provenance dan reproducibility pipeline

| Sumber | Venue | Tahun | Verifikasi |
|---|---|---|---|
| Rupprecht et al. *Improving Reproducibility of Data Science Pipelines through Transparent Provenance Capture (URSPRUNG)* | PVLDB | 2020 | metadata |
| [*Capturing end-to-end provenance for machine learning pipelines*](https://www.sciencedirect.com/science/article/pii/S0306437924001534) | Information Systems 132:102495 | 2025 | metadata |
| [*Learning Lineage Constraints for Data Science Operations*](https://arxiv.org/abs/2506.18252) | arXiv:2506.18252, vision paper | 2025 | metadata |
| [*An LLM-guided platform for multi-granular collection and management of data provenance*](https://link.springer.com/article/10.1186/s40537-025-01209-3) | Journal of Big Data 12:187 | 2025 | metadata |
| [*Building a Correct-by-Design Lakehouse. Data Contracts, Versioning, and Transactional Pipelines for Humans and Agents*](https://arxiv.org/abs/2602.02335) | arXiv:2602.02335 | 2026 | metadata |
| Peng. *Reproducible Research in Computational Science* | Science 334(6060) | 2011 | metadata |

---

## E. Statistik resmi, standar, dan rekonsiliasi sumber

| Sumber | Bentuk | Tahun | Verifikasi |
|---|---|---|---|
| SDMX 3.0 dan 3.1 — sub-cube tetap pada Data Structure Definition, semantic versioning | Spesifikasi | 2024, 2025 | metadata |
| Laporan SDMX ke UN Statistical Commission (E/CN.3/2025/33) | Dokumen PBB | 2025 | metadata |
| [*A Unified Statistical And Computational Framework For Ex-Post Harmonisation Of Aggregate Statistics*](https://arxiv.org/abs/2406.14163) | arXiv:2406.14163 | 2024 | metadata |
| [*Evaluating Quality of Disparate Data Sources: A Discord-Driven Approach*](https://link.springer.com/chapter/10.1007/978-3-032-05281-0_10) | ADBIS 2025, LNCS 16043:147–163 | 2026 | metadata |
| World Bank *Statistical Performance Indicators* update | Laporan | 2025 | metadata |
| [*Satu Data Indonesia in Sectoral Statistics: Concept of Satu Data Metadata Framework (SDMF)*](https://proceedings.stis.ac.id/icdsos/article/view/243) | Proceedings ICDSOS 2021(1):315–325 | 2022 | metadata |

Penelusuran tidak menemukan penelitian yang mempertemukan SDMX dengan format tabel terbuka semacam Iceberg secara empiris. Celah ini nyata, tetapi berisiko: pekerjaan standar sulit dievaluasi dengan angka.

---

## F. Truth discovery dan data fusion — bidang yang mengapit dari sisi basis data

Bidang ini sudah matang. Kebaruan tidak boleh diklaim di sini; ia dipakai sebagai pembanding dan sebagai kontras konseptual.

| Sumber | Venue | Tahun | Verifikasi |
|---|---|---|---|
| Dong, Berti-Équille, Srivastava. *Data Fusion: Resolving Conflicts from Multiple Sources* | Springer / arXiv:1503.00310 | 2013, 2015 | metadata |
| Li et al. *A Survey on Truth Discovery* | ACM SIGKDD Explorations | 2016 | metadata |
| *Enhancing domain-aware multi-truth data fusion using copy-based source authority and value similarity* | The VLDB Journal | 2023 | metadata |
| [*A Survey on Truth Discovery: Concepts, Methods, Applications, and Opportunities*](https://ieeexplore.ieee.org/document/10587116/) | IEEE Transactions on Big Data 11(2):314–332 | 2025 | metadata |
| [*Evaluating Quality of Disparate Data Sources: A Discord-Driven Approach*](https://link.springer.com/chapter/10.1007/978-3-032-05281-0_10) | ADBIS 2025, LNCS 16043:147–163 | 2026 | metadata |

**Asumsi bidang ini:** ada satu nilai benar yang tersembunyi, sumber-sumbernya tidak seluruhnya dapat dipercaya, dan tugasnya menyimpulkan mana yang benar sambil menaksir reliabilitas sumber.

Asumsi itu **tidak berlaku** untuk statistik resmi. Ketika BPS WebAPI dan kompilasi indikator SDGs memberi angka berbeda, tidak ada sumber yang salah. Keduanya resmi. Perbedaannya berasal dari vintage rilis, perubahan metodologi, atau granularitas yang berbeda. Menerapkan truth discovery di sini berarti membuang informasi yang justru bermakna.

Inilah pembeda konseptual utama penelitian ini, dan sekaligus alasan mengapa pendekatan *Trust Your Friend* pada SDG-KG — yang memilih satu sumber berdasarkan skor kepercayaan sebelum perhitungan — tidak memadai untuk kasus statistik resmi.

## G. Revisi dan vintage pada statistik resmi

Konsep ini mapan di dunia statistik resmi, tetapi hidup terpisah dari dunia sistem data.

| Sumber | Bentuk | Tahun | Verifikasi |
|---|---|---|---|
| OECD/Eurostat *Guidelines on Revisions Policy and Analysis* | Pedoman | — | metadata |
| OECD Statistics Working Paper 2006/02, *Undertaking Revisions and Real-Time Data Analysis* | Working paper | 2006 | metadata |
| Statistics Canada *Real-time data tables* — seluruh revisi satu titik data sepanjang waktu | Produk statistik | berjalan | metadata |
| [ECB Working Paper 846, *Information combination and forecast (st)ability: Evidence from vintages of time-series data*](https://www.ecb.europa.eu/pub/pdf/scpwps/ecbwp846.pdf) | ECB Working Paper Series | 2007 | metadata |
| *Revisions in official data and forecasting* | Statistical Methods & Applications | 2014 | metadata |
| [`reviser` 0.2.0 — *Analyzing Revisions in Real-Time Time Series Vintages*](https://packages.ropensci.org/reviser) | rOpenSci | 2026 | metadata |
| [*A Unified Statistical And Computational Framework For Ex-Post Harmonisation Of Aggregate Statistics*](https://arxiv.org/abs/2406.14163) | arXiv:2406.14163 | 2024 | metadata |

Istilah kuncinya: **vintage** (keadaan sebuah angka pada saat ia dirilis) dan **revision triangle** (matriks yang menunjukkan bagaimana taksiran satu periode berubah pada rilis-rilis berikutnya).

**Batasnya:** literatur ini bekerja pada agregat yang sudah terbit — deret waktu kecil, biasanya di lingkungan statistik/ekonometrik. Ia tidak menyentuh pipeline yang memproduksi angka tersebut, dan tidak membahas ongkos komputasi mempertahankannya.

## H. Incremental view maintenance dan versioning pada lakehouse

Juga matang. Dipakai sebagai mekanisme, bukan sebagai klaim kebaruan.

| Sumber | Bentuk | Tahun | Verifikasi |
|---|---|---|---|
| Iceberg snapshot dan time travel | Spesifikasi format | berjalan | metadata |
| [Microsoft Fabric Materialized Lake Views — *optimal refresh*](https://learn.microsoft.com/en-us/fabric/data-engineering/materialized-lake-views/refresh-materialized-lake-view) | Dokumentasi produk; no-op, incremental, atau full refresh | 2026 | metadata |
| [Feldera Incremental Computation Engine](https://github.com/feldera/feldera) — IVM SQL berbasis DBSP | Sistem/proyek sumber terbuka | 2026 | metadata |
| [*Enzyme: Incremental View Maintenance for Data Engineering*](https://arxiv.org/abs/2603.27775) | arXiv:2603.27775 | 2026 | metadata |
| [*Building a Correct-by-Design Lakehouse. Data Contracts, Versioning, and Transactional Pipelines for Humans and Agents*](https://arxiv.org/abs/2602.02335) | arXiv:2602.02335 | 2026 | metadata |

**Batasnya:** time travel Iceberg memberi snapshot **tabel Anda**, bukan vintage **indikatornya**. Keduanya tidak sama. Snapshot tabel merekam kapan Anda menulis; vintage indikator merekam kapan BPS merilis. Ketika sumber direvisi surut, kedua sumbu waktu itu berpisah.

---

## Ringkasan celah

Penelusuran ini menemukan dua literatur matang yang **belum pernah dipertemukan**.

Dunia statistik resmi punya konsep vintage dan revision triangle yang mapan, tetapi menerapkannya pada agregat yang sudah terbit, bukan pada pipeline yang memproduksinya, dan tanpa memperhitungkan ongkos komputasi.

Dunia sistem data punya mesin lengkap untuk versioning dan pemeliharaan inkremental, tetapi memodelkan perbedaan antarsumber sebagai *truth discovery* — yaitu sebagai kesalahan yang harus diselesaikan. Model itu keliru untuk statistik resmi, tempat semua sumber sama-sama sah.

Celah yang tersisa, dan yang menjadi fokus penelitian ini:

**Vintage indikator belum pernah diperlakukan sebagai objek kelas satu di dalam lakehouse, dan ongkos mempertahankannya belum pernah diukur.**

Turunannya, tiga hal yang belum terjawab:

1. Bentuk ketidaksesuaian apa yang sebenarnya muncul antarsumber resmi, dan berapa proporsi yang berasal dari revisi vintage dibanding perbedaan metodologi atau granularitas. Ini pertanyaan empiris yang belum ada datanya untuk kasus Indonesia.
2. Berapa ongkos penghitungan ulang ketika satu sumber direvisi, dan pada besaran revisi seperti apa pendekatan inkremental berhenti terbayar dibanding menghitung ulang seluruhnya.
3. Apakah angka yang pernah dilaporkan masih dapat dihasilkan ulang persis setelah sumbernya direvisi — syarat yang diminta kebijakan revisi statistik resmi, tetapi jarang diuji sebagai properti sistem.

Ketiganya dapat dijawab dengan data terbuka BPS WebAPI yang sudah ditarik, tanpa menunggu data berbayar Silastik/PST, dan tanpa memerlukan volume data besar — karena pertanyaannya tentang kebenaran dan ongkos pemeliharaan, bukan tentang throughput.
