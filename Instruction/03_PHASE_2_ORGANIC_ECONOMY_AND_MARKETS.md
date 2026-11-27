# PHASE 2 — GENERIC ECONOMY, MARKETS & INSTITUTIONS

Mulai implementasi Fase 2 berdasarkan roadmap utama proyek.

Fase 1 (Accounting Ledger) telah selesai dan dinyatakan lulus. Gunakan sistem ledger yang sudah ada sebagai fondasi seluruh aktivitas ekonomi.

## TUJUAN UTAMA

Mengembangkan ekonomi yang saling terhubung dan memungkinkan aktivitas bisnis, produksi, perdagangan, pekerjaan, serta institusi berkembang melalui keputusan agen dan interaksi pasar.

Jangan membuat sistem progression berbasis tahun, jumlah penduduk, atau unlock yang ditentukan programmer.

## 1. Generic Production System

Buat sistem produksi generik yang mendukung:

- Input bahan baku.
- Kebutuhan tenaga kerja dan keterampilan.
- Waktu produksi.
- Output barang atau jasa.
- Biaya operasional.
- Kapasitas produksi.
- Inventaris.
- Produktivitas.
- Kegagalan produksi jika sumber daya tidak mencukupi.

Bisnis harus benar-benar menggunakan input dan menghasilkan output melalui sistem ini.

Hindari implementasi produksi khusus untuk setiap jenis bisnis jika mekanisme generik dapat digunakan.

## 2. Generic Market & Trading

Kembangkan mekanisme pasar yang memungkinkan:

- Penjual menawarkan barang dan jasa.
- Pembeli memilih berdasarkan harga, kebutuhan, kualitas, dan ketersediaan.
- Harga terbentuk dari interaksi penawaran dan permintaan.
- Persediaan memengaruhi kemampuan penjualan.
- Perdagangan antarpelaku ekonomi.
- Kontrak perdagangan dengan kewajiban yang jelas.
- Transaksi tercatat melalui Accounting Ledger.

Jangan membuat harga pasar hanya bergerak berdasarkan random walk atau perubahan harga yang ditentukan secara langsung oleh programmer.

## 3. Labor Market

Integrasikan tenaga kerja dengan aktivitas ekonomi.

Pertimbangkan:
- Lowongan pekerjaan.
- Perekrutan.
- Upah.
- Keterampilan.
- Produktivitas.
- Biaya tenaga kerja.
- Perpindahan pekerjaan.
- Penawaran dan permintaan tenaga kerja.

Pisahkan statistik pekerja penuh waktu, paruh waktu, dan pekerjaan informal jika sistem yang ada mendukungnya.

## 4. Business Formation & Management

Agen harus dapat membentuk dan mengelola usaha melalui mekanisme ekonomi yang tersedia.

Pertimbangkan:
- Modal awal.
- Pembiayaan.
- Pemilihan sektor.
- Pembelian input.
- Perekrutan pekerja.
- Penentuan harga.
- Pengelolaan inventaris.
- Pendapatan dan biaya.
- Keuntungan dan kerugian.
- Ekspansi atau penutupan usaha.

Jangan membuat bisnis muncul secara otomatis karena tahun tertentu atau jumlah penduduk tertentu.

## 5. Contracts & Institutions

Buat fondasi kontrak generik yang dapat digunakan untuk:

- Perdagangan.
- Pekerjaan.
- Penyewaan.
- Konstruksi.
- Pembiayaan.
- Kerja sama bisnis.

Institusi harus dapat berkembang dari kebutuhan dan interaksi ekonomi, bukan melalui event unlock yang dipaksakan.

Jangan memaksakan pembentukan koperasi, serikat, bank, atau organisasi tertentu jika mekanisme dasarnya belum siap.

## 6. Economic Metrics

Perbaiki pengukuran ekonomi agar memiliki definisi yang konsisten.

Perhatikan:
- GDP berdasarkan value added, bukan sekadar total penjualan.
- CPI berdasarkan keranjang konsumsi yang terdefinisi.
- Produktivitas.
- Tingkat pengangguran.
- Pendapatan dan distribusi kekayaan.
- Profitabilitas bisnis.
- Uang beredar.
- Arus transaksi antarsektor.

Jangan mengklaim metrik sebagai indikator ekonomi yang akurat jika definisi dan perhitungannya belum sesuai.

## 7. Accounting Integration

WAJIB menggunakan Accounting Ledger dari Fase 1.

Pastikan:
- Tidak ada perubahan saldo yang melewati ledger.
- Semua transaksi memiliki pihak dan sumber dana yang jelas.
- Tidak ada uang yang tercipta atau hilang tanpa mekanisme yang sah.
- Transaksi gagal tidak meninggalkan perubahan parsial.
- Neraca pelaku ekonomi tetap dapat direkonsiliasi.

## 8. BATASAN IMPLEMENTASI

- Pertahankan sistem gameplay dan kontrol pemain yang sudah ada.
- Jangan mengubah proyek menjadi city builder konvensional.
- Jangan mengimplementasikan BDI, GOAP, reinforcement learning, knowledge graph, atau sistem memori pada fase ini.
- Jangan menghapus sistem lama sebelum penggantinya terbukti berfungsi.
- Hindari hardcoded progression dan event yang memaksakan perkembangan ekonomi.
- Pertahankan kompatibilitas save/load.
- Gunakan standard library jika memungkinkan.
- Perhatikan performa untuk populasi hingga 140 warga.

## 9. PENGUJIAN

Buat pengujian untuk:
- Produksi dan konsumsi input.
- Ketersediaan inventaris.
- Penawaran dan permintaan.
- Pembentukan harga.
- Perekrutan dan pembayaran upah.
- Keuntungan dan kerugian bisnis.
- Kegagalan kontrak.
- Rekonsiliasi ledger.
- Tidak adanya penciptaan uang ilegal.
- Kompatibilitas save lama.
- Performa simulasi.

Gunakan beberapa random seed untuk menguji variasi hasil ekonomi.

## 10. ATURAN PENYELESAIAN

Kerjakan hanya Fase 2.

Jangan menganggap fase selesai hanya karena modul baru berhasil dibuat. Semua mekanisme harus terintegrasi dengan ekonomi yang sudah ada.

Jika menemukan konflik dengan arsitektur Fase 1, hentikan bagian terkait dan laporkan sebelum melakukan perubahan berisiko.

Setelah implementasi:
1. Jalankan seluruh test.
2. Laporkan file yang berubah.
3. Laporkan fitur yang sudah terintegrasi.
4. Laporkan fitur yang belum selesai.
5. Laporkan hasil benchmark.
6. Laporkan masalah yang masih tersisa.

Jangan lanjut ke Fase 3 tanpa persetujuan.