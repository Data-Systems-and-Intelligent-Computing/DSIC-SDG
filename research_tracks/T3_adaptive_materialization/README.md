# T3 — Adaptive Materialization

Track ini menelaah kapan data sebaiknya dipertahankan sebagai tabel detail, kapan diringkas menjadi tabel agregat, dan kapan disimpan sebagai produk analitik yang sudah dimaterialisasi. Pilihan tersebut tidak ditetapkan di awal, melainkan diturunkan dari karakteristik beban kerja yang benar-benar dijalankan.

Ketiga bentuk penyimpanan itu menawarkan pertukaran yang sama: waktu query ditekan dengan membayar ruang penyimpanan dan ongkos pembaruan. Karena itu, yang digarap bukan bentuk mana yang paling baik secara umum, melainkan pada beban kerja seperti apa penghematan waktu query menutup ongkos yang menyertainya.
