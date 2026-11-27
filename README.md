# Rupiahville — Simulasi Ekonomi Kota (pixel art)

Jalankan: `.venv\Scripts\python.exe main.py`  ·  Tes: `.venv\Scripts\python.exe -m unittest discover -s tests`

## Kontrol
| Tombol | Fungsi |
|---|---|
| SPASI | jeda / lanjut |
| 1-5 | kecepatan 1x / 2x / 5x / 10x / 100x |
| P | Bursa Efek (chart candlestick + kontrol pasar) |
| E | Dasbor makro (gauge) |
| K | Kebijakan & pajak |
| B / R | Daftar usaha / Pasar properti |
| L | Layer peta (normal / kekayaan / usaha) |
| W / N / TAB | Tab Warga / Berita / ganti tab |
| M | Set uang warga terpilih |
| F5 / F11 / ESC | Simpan / layar penuh / menu & tutup jendela |

Klik gedung di peta: Bursa = pasar saham, Balai = kebijakan, rumah/usaha = detailnya.
Untuk transaksi properti, pilih warga di tab **WARGA**, buka **Properti (R)**, lalu beli rumah dari daftar atau beli lahan pemerintah dan bangun setelah kontraktor tersedia.

## Struktur
- `systems/ekonomi_core.py` — mesin ekonomi (tanpa pygame)
- `game/assets.py` — memotong semua aset lewat `atlas_metadata.json`
- `game/ui.py` — toolkit UI dari sprite pack · `game/windows.py` — jendela pasar/makro/kebijakan/usaha/properti
- `game/city_view.py` — render peta, mobil, emote, siang/malam · `game/menus.py` — start menu, opsi, jeda

## Produksi dan pasar
- Resep produksi generik berlaku untuk kebun, pabrik, pabrik mobil, konstruksi, servis, antar, dan kebersihan. Inventaris input, biaya pokok, progres waktu, kualitas, kapasitas, serta output masuk ke nilai inventaris bisnis yang dicatat ledger.
- Input dibeli dari pemasok eksternal dengan harga dan kuota harian; pemasok dimodelkan sebagai pihak luar, bukan bisnis lokal. Ini menjaga batas ekonomi lokal tetap eksplisit.
- Barang, jasa, kendaraan, dan input menggunakan kontrak spot yang langsung berstatus selesai. Kontrak mencatat kewajiban yang telah dipenuhi; belum ada order book, kontrak tertunda, atau penyelesaian lintas hari.
- Harga bisnis merespons stok tersedia dan permintaan yang dicatat transaksi. Pasar tenaga kerja memakai upah, keterampilan, kapasitas pekerja, jam kerja, lowongan, dan kemampuan membayar. Ini adalah aturan simulasi yang terbatas, bukan pembelajaran strategi mandiri.
- Ledger Phase 2 menambahkan nilai persediaan usaha pada rekonsiliasi. Rekonsiliasi tetap bukan audit penuh seluruh aset riil: tanah, rumah, kendaraan warga, peralatan, dan nilai pasar aset investasi belum seluruhnya diposting sebagai akun neraca.

## Simulasi
- Pada kecepatan 1x, satu jam simulasi berlangsung selama enam detik nyata; 2x, 5x, 10x, dan 100x mempercepat kelipatan tersebut.
- Warga memulai tanpa uang; gaji, bantuan kota, pajak, tabungan, kredit, dan usaha membentuk perputaran uang.
- Direktori warga menampilkan semua penduduk menurut kekayaan bersih, menyediakan pencarian nama, dan membuka profil warga saat dipilih.
- Nilai bersih warga menghitung uang, tabungan, investasi, properti, kendaraan, aset usaha, dan seluruh pinjaman.
- Bank mencatat simpanan, kredit, modal, dan agunan; kredit baru dibatasi saat modal bank tidak mencukupi, sementara pemerintah dapat menyuntik modal dengan tetap menyisakan Rp100 juta di kas kota.
- Gagal bayar dapat menyita rumah, kendaraan, atau usaha; bunga simpanan dan penyusutan agunan tercermin di neraca bank.
- Kredit tanpa agunan dibatasi Rp1-10 juta menurut kemampuan bicara, skill, dan skor kredit; kredit beragunan dibatasi Rp50 juta, selain tetap tunduk pada kemampuan cicilan dan kesehatan bank.
- Stres, takut, sedih, dan depresi berkembang dari tekanan hidup serta memengaruhi kapasitas kerja; kondisi warga bisa pulih saat hidupnya membaik.
- Warga yang belum punya kerja tetap dapat mengambil gig kuli bangunan, servis, kebersihan, dan antar barang. Kejahatan sesekali memindahkan uang, berisiko tertangkap, dan tercatat pada statistik kota.
- Warga bisa membeli lahan kosong dari pemerintah (pembayaran masuk ke kas kota), lalu membayar industri bangunan untuk membangun rumah secara terpisah. Rumah berpindah tangan lewat transaksi penjual-pembeli; sisa KPR penjual dilunasi dari hasil penjualan.
- Usaha produksi memakai resep generik: membeli input dari pemasok dengan kapasitas terbatas, memakai waktu kerja dan biaya operasi, lalu menghasilkan stok barang atau jasa. Kekurangan tenaga kerja, input, atau kas menghentikan produksi.
- Usaha dapat menjual barang dan jasa lewat kontrak yang mencatat pihak, produk, jumlah, harga, pajak, dan penyelesaian. Harga menyesuaikan stok dan permintaan yang teramati; pembeli mempertimbangkan harga, mutu, ketersediaan, dan jarak.
- Setiap warga menyimpan memori pengalaman pribadi yang terbatas: hingga 64 episode dan 16 ringkasan pengalaman serupa. Hasil penjualan investasi memengaruhi perkiraan berikutnya pada aset yang sama; memori ikut tersimpan dan dimigrasikan bersama save.
- Graph pengetahuan tiap warga membentuk konsep dan korelasi dari observasi pribadi, menyusun hipotesis deklaratif dengan provenance, lalu mengurangi confidence saat bukti bertentangan. Hanya pola yang tervalidasi memengaruhi perkiraan investasi; tidak ada kode yang dihasilkan atau dieksekusi agen.
- BDI tiap warga memperbarui beliefs dari kondisi dunia, memori pribadi, dan klaim pengetahuan tervalidasi; kebutuhan dan sinyal risiko membentuk desires dengan prioritas dan horizon yang dapat berubah atau dibatalkan. Planner GOAP deklaratif dibatasi hingga 3 langkah dan 64 ekspansi, menimbang manfaat tujuan terhadap biaya, waktu, risiko, serta dana yang tersedia tanpa mengubah dunia saat merencanakan. Eksekusi maksimal satu langkah per siklus mingguan menggunakan API ekonomi tervalidasi, termasuk mencari kerja, membeli lahan lalu membangun rumah, dan mengurangi posisi investasi berisiko.
- Kebijakan agen belajar dengan contextual bandit pribadi yang dibatasi per konteks dan per tindakan. Reward berasal dari perubahan kondisi sesudah tindakan—kesehatan, kebutuhan, kesejahteraan, keamanan finansial, stabilitas, keterampilan, kontak rumah/kerja, dan risiko—dengan bobot motivasi yang berubah; niat programmer sendiri tidak memberi reward. Hasil ditinjau pada siklus berikutnya, dan eksplorasi terbatas memungkinkan strategi berbeda berkembang dari pengalaman masing-masing warga.
- Pemilik toko dapat menguji perubahan harga kecil saat permintaan historis cukup tidak pasti dan nilai informasi melebihi estimasi risiko. Uji memakai periode pembanding dan perlakuan selama waktu simulasi, membatasi kerugian dengan kas usaha, lalu mengadopsi strategi hanya jika arus kas dan penjualan nyata membaik. Hasil—termasuk kegagalan—memperbarui memori, graph pengetahuan, dan pembelajaran; berbagi hasil dilakukan eksplisit kepada warga tertentu, bukan broadcast otomatis.
- Relasi sosial menyimpan kepercayaan dan reputasi yang berubah lewat interaksi serta transaksi nyata. Warga dapat mengamati tindakan dan membagikan satu observasi kepada penerima tertentu melalui relasi tepercaya; tidak ada broadcast otomatis. Mitra dagang dapat mengajukan, menolak, atau menegosiasikan kontrak grosir yang memindahkan kas dan stok lewat ledger. Koperasi dagang terbentuk dari kemitraan yang telah terbukti, kontribusi anggota, dan persetujuan undangan; aturan dapat diputuskan dengan satu suara per anggota. Biaya, pemeliharaan, cadangan, pembagian surplus, pengunduran diri, dan pembubaran tercermin pada dana organisasi serta aset warga.
- Siklus hidup kini mencakup kelahiran bersyarat, pertumbuhan, pendidikan anak, kedewasaan, penuaan, dan kematian. Pasangan terbentuk lewat lamaran yang memerlukan persetujuan dan relasi tepercaya; kelahiran mempertimbangkan kesehatan, kestabilan rumah tangga, keinginan menjadi orang tua, kapasitas rumah, dan biaya. Anak tinggal dalam tanggungan wali, kebutuhan hariannya dibayar pengasuh, dan keterampilan awalnya terbatas. Keluarga menyimpan relasi orang tua, anak, pasangan, saudara, serta wali; aset diwariskan menurut prioritas keluarga, sedangkan memori, pengetahuan, relasi sosial, dan keanggotaan organisasi tidak otomatis diwariskan. Pengajaran pengetahuan harus eksplisit, dapat gagal atau berubah, dan pengetahuan yang tidak ditransfer dapat hilang saat pembawanya meninggal.
- Fase 10 menampilkan tujuan aktif, motivasi, niat GOAP, strategi bandit, memori, klaim pengetahuan, eksperimen, relasi, dan organisasi pada profil warga. Dasbor makro menambah ringkasan organisasi dan klaim pengetahuan; snapshot observasi dapat diperiksa tanpa mengubah simulasi.
- Lowongan dan upah mengikuti kebutuhan tenaga kerja serta kemampuan kas usaha. Jadwal kerja dapat menjadi paruh waktu, perekrutan menyesuaikan lowongan, dan statistik memisahkan kerja penuh waktu, paruh waktu, serta gig informal.
- Pembentukan usaha dipilih agen dari peluang sektor dan kondisi pasokan, bukan dibuka oleh tahun atau ambang populasi. Keputusan tetap memakai model perilaku terbatas, bukan agen yang belajar bebas.
- Nilai apartemen dan aset usaha terdepresiasi; migrasi dan kejadian kota bersifat acak.
- AI warga mulai dengan pengalaman rendah dan belajar dari pekerjaan serta keputusan finansial.
- Wali kota meninjau pajak dan bantuan berdasarkan kondisi kota; perubahan kebijakan muncul di berita.
- Mobil hanya muncul setelah dibeli dari showroom; pabrik mobil dan dealer dapat dibuka seiring perkembangan ekonomi.
- Seed hanya diacak melalui ikon dadu. Geser peta dengan seret kiri pada peta, tombol panah, atau tombol tengah/kanan + drag; roda mouse untuk vertikal dan Shift+roda untuk horizontal.

## Ledger akuntansi
- Setiap perubahan saldo melalui operasi ekonomi tercatat sebagai jurnal debit-kredit seimbang di `World.ledger`.
- Tahap migrasi pertama mempertahankan field saldo dan mekanisme ekonomi lama sebagai sumber kebenaran; ledger menjadi jurnal mirror yang dapat direkonsiliasi lewat `World.reconcile_ledger()`. Rekonsiliasi mencakup kas, simpanan, pinjaman, investasi tercatat, dan inventaris usaha; bukan validasi penuh rumah, tanah, kendaraan, peralatan, atau nilai pasar aset investasi.
- Saldo awal dicatat sebagai opening balances, termasuk modal awal bank dari sumber eksternal. Aliran yang pihak lawannya belum dimodelkan secara terpisah memakai akun counterpart bernama: pemasok pangan/input produksi, akrual bunga/sewa, aset modal awal usaha, penyelesaian estate, input konstruksi, dan clearing bursa. Saldo akun ini tetap terlihat melalui `World.ledger.counterpart_balances`; akun laba/rugi bank adalah indikator UI, bukan saldo neraca terpisah dari ekuitas.
- Ledger menyimpan 10.000 jurnal transaksi terbaru secara rinci; transaksi yang lebih lama diringkas per kategori sementara saldo akun tetap kumulatif. Pembelian dan penjualan aset memvalidasi input serta mencatat jurnal sebelum mengubah posisi, kas, atau kas kota; penjualan menolak fraksi di luar 0-1.
- Save baru memakai envelope skema v4 dengan versi ledger dicatat terpisah; envelope v1/v2/v3 dimigrasikan otomatis. Ledger v1 dimigrasikan dengan saldo pembukaan inventaris usaha. Save pickle lama yang berisi objek `World` langsung tetap dimuat dan dimigrasikan lewat `World.migrate_save()`; versi skema yang tidak didukung atau metadata ledger yang tidak cocok ditolak tanpa mengganti scene aktif.
- Save masih memakai pickle agar save lama tetap kompatibel. Loader aplikasi hanya mengizinkan kelas game/ledger yang dikenal dan menolak global lain sebelum deserialisasi, tetapi allowlist bukan pengganti format data aman; tetap simpan backup dan hindari file save dari sumber tak dikenal.
