## High

- Pembelian jasa tidak dapat memakai tabungan, bertentangan dengan klaim Fase 2 dan memblokir konstruksi/servis bagi warga yang dananya seluruhnya tersimpan di bank.

  Bukti: buy_service (/D:/Projek Game/City/systems/ekonomi_core.py:1420)–[1430] memeriksa c.cash untuk seller eksplisit dan menghitung affordable hanya dari c.cash. Padahal pembayaran akhirnya memakai pay_from(), yang sebenarnya mampu memakai tabungan.

  Skenario reproduksi: warga memiliki kas Rp0 dan tabungan Rp1.000.000; jasa perbaikan tersedia seharga Rp200.000 + PPN. buy_service(warga, "repair", 1) mengembalikan 0.0, stok jasa tetap utuh, dan tabungan tidak dipakai—meski dana total mencukupi. Jalur build_house() terkena masalah sama karena memanggil buy_service(..., seller=builder) di ekonomi_core.py (/D:/Projek Game/City/systems/ekonomi_core.py:1371).

  Rekomendasi: gunakan dana likuid tervalidasi cash + savings saat menghitung kemampuan bayar pada kedua jalur tersebut, lalu tetap gunakan pay_from() sebagai satu-satunya settlement. Tambahkan test untuk:
  - jasa dibayar penuh dari tabungan;
  - konstruksi dengan kas nol/tabungan cukup;
  - rollback jasa dari tabungan saat jurnal gagal.

Tidak ada temuan Critical lain dari peninjauan produksi generik, inventaris bernilai biaya, kontrak spot, migrasi ledger v1→v2, maupun envelope save. Saya juga mereproduksi kasus di atas secara headless; ledger tetap bersih karena transaksi tidak pernah terjadi—ini sebabnya test rekonsiliasi saat ini tidak menangkapnya.