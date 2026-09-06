# Adaptive Data Product Configuration for Heterogeneous Official-Statistics Workloads

KK-CIV Research Program — Data Systems and Intelligent Computing (DSIC)

## 1. Posisi Penelitian

Repository ini adalah workspace penelitian bersama untuk mengembangkan dan mengevaluasi **Adaptive Data Product Configuration for Heterogeneous Official-Statistics Workloads**.

Proposal KK-CIV berfungsi sebagai **payung penelitian** dan menyediakan domain, sumber data, infrastruktur, serta konteks 5E. Repository ini tidak mencoba menjadikan seluruh proposal KK-CIV sebagai satu artikel. Sebaliknya, KK-CIV dipakai sebagai **shared experimental platform**, sedangkan setiap artikel memiliki Research Question (RQ), baseline, variabel eksperimen, metrik, dan klaim yang berbeda.

Testbed utama menggunakan lima domain official statistics yang berasal dari kerangka 5E:

- SDG 4 — Education
- SDG 6 — Environment
- SDG 7 — Energy
- SDG 8 — Economy
- SDG 15 — Ecology / spatial workload

Nilai indikator harus mempertahankan provenance dari sumber resmi yang digunakan dalam eksperimen. Data geometri, bila dipakai pada SDG 15, diperlakukan sebagai reference/master data dan tidak boleh dicampur dengan provenance indikator.

## 2. Research Question Utama

**RQ-Main**

> Dapatkah karakteristik workload digunakan untuk memilih konfigurasi data product yang lebih efisien pada official-statistics workloads yang heterogen, tanpa melanggar batas data quality, reproducibility, dan governance dibandingkan konfigurasi statis yang sama untuk semua workload?

### Sub-RQ sistem

**RQ1 — Workload representation**  
Karakteristik workload apa yang paling informatif untuk memprediksi konfigurasi yang sesuai?

**RQ2 — Configuration benefit**  
Seberapa besar adaptive configuration mengurangi processing cost dan query cost dibandingkan static configuration?

**RQ3 — Generalization**  
Apakah policy yang dibentuk pada development workloads tetap efektif ketika diterapkan pada domain yang tidak digunakan saat merancang policy?

**RQ4 — Cost of adaptation**  
Berapa profiling, decision, storage, dan maintenance overhead yang harus dibayar untuk memperoleh keuntungan adaptive configuration?

**RQ5 — Guardrails**  
Apakah adaptive policy tetap mempertahankan data quality, reproducibility, conformed dimensions, dan lineage/governance requirements?

## 3. Unit Eksperimen

Penelitian tidak menganggap nama domain sebagai konfigurasi. Konfigurasi dipilih berdasarkan karakteristik workload yang dapat diukur.

Contoh workload features:

- input size;
- row count;
- schema width;
- cardinality;
- temporal depth;
- update frequency;
- query selectivity;
- aggregation ratio;
- join fan-out;
- spatial/non-spatial flag;
- geometry complexity untuk spatial workloads;
- observed scan bytes;
- shuffle volume;
- runtime history.

Candidate configuration tidak harus semuanya diaktifkan pada eksperimen pertama. Action space dibekukan sebelum main experiment.

Contoh configuration actions:

- Iceberg partition strategy;
- partition granularity;
- target file size / compaction policy;
- sort/order strategy;
- materialization level;
- aggregate table selection;
- query-serving layout;
- spatial partition/join strategy untuk SDG 15.

## 4. Baseline dan Proposed System

Minimal comparison:

**B0 — Static Default**  
Satu konfigurasi statis digunakan untuk seluruh workload.

**B1 — Simple Heuristic**  
Konfigurasi dipilih menggunakan aturan sederhana, misalnya hanya berdasarkan ukuran data atau jenis temporal/spatial.

**B2 — Domain-Tuned Configuration**  
Konfigurasi dipilih secara manual per domain. Ini dapat dipakai sebagai pembanding tambahan, bukan sebagai oracle ilmiah.

**B3 — Adaptive Policy**  
Konfigurasi dipilih dari workload profile menggunakan policy yang dibekukan sebelum held-out evaluation.

**Oracle Retrospective — optional analysis only**  
Setelah seluruh candidate configuration selesai dijalankan, konfigurasi terbaik per workload dapat dihitung secara retrospektif untuk mengukur policy regret. Oracle tidak digunakan saat policy melakukan inference.

## 5. Empat Research Track Mahasiswa

Empat mahasiswa adalah konfigurasi ideal untuk program ini. Pembagian dilakukan berdasarkan **mekanisme sistem**, bukan satu mahasiswa per SDG.

### T1 — Workload-to-Configuration Prediction

Fokus: membentuk workload representation dan memprediksi konfigurasi terbaik dari kandidat yang tersedia.

RQ mahasiswa:

> Dapatkah workload descriptors yang murah dihitung memprediksi konfigurasi terbaik dengan regret rendah terhadap retrospective oracle?

Baseline:

- size-only heuristic;
- domain-label heuristic;
- random configuration.

Metrik utama:

- configuration accuracy;
- normalized regret terhadap oracle;
- profiling overhead;
- inference latency;
- generalization pada held-out workload.

Judul artikel kandidat:

**Predicting Data-Product Configurations from Official-Statistics Workload Profiles**

### T2 — Adaptive Physical Design

Fokus: partitioning, file layout, target file size, compaction, dan scan efficiency pada Iceberg.

RQ mahasiswa:

> Kapan workload-aware physical design memberikan query cost yang lebih rendah daripada satu physical design statis pada official-statistics workloads?

Baseline:

- unpartitioned/static layout;
- fixed partition strategy;
- manually tuned configuration.

Metrik utama:

- query latency;
- bytes scanned;
- files scanned;
- shuffle bytes;
- compaction cost;
- storage overhead.

Judul artikel kandidat:

**Workload-Aware Physical Design for Iceberg-Based Official-Statistics Data Products**

### T3 — Adaptive Materialization

Fokus: memilih kapan data harus dipertahankan sebagai detail table, aggregate table, atau materialized analytical product.

RQ mahasiswa:

> Dapatkah workload-aware materialization menurunkan analytical query cost tanpa menghasilkan storage dan maintenance overhead yang berlebihan?

Baseline:

- no materialization;
- fixed materialization;
- manually selected aggregates.

Metrik utama:

- query latency;
- storage footprint;
- refresh/maintenance cost;
- workload coverage;
- time-to-freshness.

Judul artikel kandidat:

**Adaptive Materialization for Heterogeneous Official-Statistics Analytical Workloads**

### T4 — Spatial Workload Configuration

Fokus: menguji apakah policy/configuration abstraction yang sama dapat ditransfer ke spatial official-statistics workloads atau membutuhkan spatial specialization.

RQ mahasiswa:

> Sejauh mana workload-aware configuration dapat memilih spatial partition/join strategy yang efisien untuk official-statistics data dengan reference geometry?

Baseline:

- fixed spatial partitioning;
- fixed join strategy;
- non-adaptive spatial configuration.

Metrik utama:

- spatial query latency;
- shuffle bytes;
- peak memory;
- files/partitions touched;
- correctness of spatial result;
- adaptation overhead.

Judul artikel kandidat:

**Adaptive Configuration of Spatial Official-Statistics Data Products**

## 6. Artikel Integrasi Ketua / Supervisor (Pak Ardika Satria)

Artikel utama harus menguji **system-level adaptive policy** pada beberapa action family dan domain yang heterogen.

Judul kerja:

**Adaptive Data Product Configuration for Heterogeneous Official-Statistics Workloads**

Kontribusi yang diharapkan:

1. unified workload representation untuk official-statistics data products;
2. configuration action space yang eksplisit;
3. adaptive selection policy;
4. held-out-domain evaluation;
5. multi-objective evaluation antara processing/query cost dan adaptation overhead;
6. governance, reproducibility, dan data-quality guardrails.

Hasil mahasiswa boleh menjadi building block atau evidence tambahan, tetapi klaim utama artikel integrasi harus berbeda dari klaim paper mahasiswa.

## 7. Batas Publikasi

Untuk mencegah overlap:

- T1 memiliki klaim tentang **prediction/regret**;
- T2 memiliki klaim tentang **physical design**;
- T3 memiliki klaim tentang **materialization**;
- T4 memiliki klaim tentang **spatial configuration**;
- artikel PI memiliki klaim tentang **system-level adaptive configuration across heterogeneous workloads**.

Dataset, infrastructure, dan beberapa benchmark query boleh digunakan bersama. RQ, intervensi utama, tabel hasil utama, dan novelty claim tidak boleh identik.

Dokumen rinci publication boundary harus disimpan di:

`docs/research/publication-boundaries.md`

## 8. Development dan Held-Out Workloads

Agar adaptive policy tidak hanya menghafal domain, pisahkan development dan held-out workloads.

Initial recommendation:

- development/calibration: SDG 4 dan SDG 6;
- held-out breadth: SDG 7 dan SDG 8;
- held-out stress: SDG 15.

Pembagian final harus dibekukan sebelum main evaluation.

Domain held-out tidak boleh digunakan untuk mengubah policy setelah evaluation dimulai. Perubahan karena bug harus dicatat dalam decision log.

## 9. Shared Infrastructure

Target stack:

- MinIO — object storage;
- Apache Iceberg — open table format;
- Apache Spark / PySpark — processing;
- Apache Airflow — orchestration;
- Trino — analytical query engine;
- OpenMetadata — metadata, lineage, dan governance evidence;
- Apache Sedona / GeoPandas / PostGIS — spatial extension bila diperlukan;
- Docker Compose — reproducible deployment;
- Git — code and configuration versioning.

Tidak semua service harus aktif sejak hari pertama. Main experiment hanya memakai komponen yang diperlukan oleh RQ.

## 10. Repository Structure

```text
.
├── README.md
├── .gitignore
├── .env.example
├── pyproject.toml
├── docker-compose.yml
├── Makefile
│
├── docs/
│   ├── research/
│   │   ├── program-charter.md
│   │   ├── rq-main.md
│   │   ├── hypotheses.md
│   │   ├── scope-freeze.md
│   │   ├── publication-boundaries.md
│   │   ├── experiment-freeze.md
│   │   └── decision-log.md
│   ├── architecture/
│   └── protocols/
│
├── config/
│   ├── domains/
│   ├── workloads/
│   └── experiments/
│
├── data/
│   ├── manifests/
│   ├── reference/
│   ├── raw/
│   ├── bronze/
│   ├── silver/
│   └── gold/
│
├── contracts/
│
├── infra/
│   ├── docker/
│   ├── minio/
│   ├── iceberg/
│   ├── spark/
│   ├── trino/
│   ├── airflow/
│   └── openmetadata/
│
├── src/
│   └── kkciv_adaptive/
│       ├── profiling/
│       ├── features/
│       ├── configuration/
│       ├── policies/
│       ├── pipeline/
│       ├── storage/
│       ├── query/
│       ├── spatial/
│       ├── governance/
│       ├── evaluation/
│       └── utils/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── reproducibility/
│
├── experiments/
│   ├── E0_static_baseline/
│   ├── E1_workload_profiling/
│   ├── E2_adaptive_policy/
│   ├── E3_heldout_transfer/
│   ├── E4_temporal_workloads/
│   ├── E5_spatial_workloads/
│   └── E6_system_integration/
│
├── research_tracks/
│   ├── T1_workload_to_configuration/
│   ├── T2_adaptive_physical_design/
│   ├── T3_adaptive_materialization/
│   └── T4_spatial_configuration/
│
├── results/
│   ├── raw/
│   ├── processed/
│   ├── tables/
│   ├── figures/
│   └── failure_cases/
│
├── papers/
│   ├── PI_system_paper/
│   ├── T1_student_paper/
│   ├── T2_student_paper/
│   ├── T3_student_paper/
│   └── T4_student_paper/
│
├── scripts/
└── notebooks/
    └── exploratory/
```

## 11. Aturan Data

Raw data tidak di-commit ke Git.

Yang wajib di-version-control:

- source manifest;
- source URL/identifier;
- retrieval date;
- checksum;
- schema;
- data dictionary;
- preprocessing version;
- reference-code version;
- experiment config.

Setiap result harus dapat dilacak ke:

`source manifest -> transformation version -> configuration -> experiment run -> metric -> table/figure`

## 12. Aturan Eksperimen

Sebelum main experiment:

1. freeze dataset snapshot;
2. freeze workload definitions;
3. freeze candidate configurations;
4. freeze baseline;
5. freeze primary metrics;
6. freeze development/held-out split;
7. freeze hardware/resource limits.

Eksperimen yang gagal karena bug boleh diulang, tetapi reason harus dicatat.

Konfigurasi tidak boleh diubah setelah melihat held-out result tanpa membuat experiment version baru.

## 13. Reproducibility

Setiap experiment directory minimal memiliki:

```text
README.md
config.yaml
run.sh
results-manifest.json
notes.md
```

Raw timing, query plans, scan statistics, dan logs disimpan sebelum agregasi statistik.

Hasil di `results/processed/` harus dapat dibentuk ulang dari `results/raw/` menggunakan script yang ada di repository.

## 14. Branching Strategy

Disarankan:

```text
main
├── track/T1-workload
├── track/T2-physical-design
├── track/T3-materialization
└── track/T4-spatial
```

Mahasiswa tidak membuat fork kode core yang terpisah tanpa alasan. Perubahan pada shared core dilakukan melalui pull request dan review.

Setiap pull request harus menyebut:

- research track;
- RQ yang dibantu;
- experiment yang terdampak;
- perubahan metric/config bila ada.

## 15. Definition of Done

Satu track dianggap selesai jika:

- RQ dapat dijawab dari hasil eksperimen;
- baseline dan proposed dibandingkan pada workload yang sama;
- primary metric dan guardrail tersedia;
- minimal satu failure analysis dilakukan;
- hasil dapat direproduksi;
- paper draft tidak membuat klaim di luar evidence;
- publication boundary terhadap track lain jelas.

## 16. Scope Boundary

Main research program tidak otomatis mencakup:

- text-to-SQL agent;
- dashboard production;
- novel forecasting model;
- full 17 SDGs;
- Kubernetes;
- streaming/Kafka;
- feature store;
- generative AI;
- production national SDG platform.

Komponen tersebut dapat menjadi extension atau research track baru setelah RQ utama selesai.

---

**Research umbrella:** KK-CIV 2026  
**Research group:** Data Systems and Intelligent Computing (DSIC)  
**Program focus:** Adaptive Data Product Configuration for Heterogeneous Official-Statistics Workloads
