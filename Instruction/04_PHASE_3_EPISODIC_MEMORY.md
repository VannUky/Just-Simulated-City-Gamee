# PHASE 3 — EPISODIC MEMORY SYSTEM

## Tujuan

Memberikan kemampuan kepada setiap agen untuk mengingat pengalaman, keputusan, interaksi, keberhasilan, dan kegagalan.

Agen tidak boleh selalu memulai pengambilan keputusan dari kondisi seolah-olah tidak memiliki pengalaman.

## Kemampuan yang diperlukan

1. Episodic memory:
   - Menyimpan pengalaman penting.
   - Merekam tindakan yang dilakukan.
   - Merekam konteks keputusan.
   - Merekam hasil tindakan.
   - Merekam keberhasilan dan kegagalan.

2. Memory retrieval:
   - Mengambil pengalaman berdasarkan relevansi.
   - Mengambil pengalaman berdasarkan waktu.
   - Mengambil pengalaman berdasarkan konteks.
   - Mengutamakan pengalaman yang memiliki dampak besar.

3. Memory management:
   - Kapasitas memori terbatas.
   - Pengalaman dapat dilupakan.
   - Pengalaman penting dapat dipertahankan.
   - Pengalaman serupa dapat diringkas.
   - Ringkasan harus tetap merujuk pada sumber pengalaman.

4. Personal memory:
   - Setiap agen memiliki pengalaman pribadi.
   - Agen tidak otomatis mengetahui pengalaman agen lain.

5. Memory persistence:
   - Memori harus bertahan setelah save/load.
   - Migrasi save lama harus aman.

## Integrasi

Integrasikan dengan aktivitas ekonomi yang sudah ada.

Contoh:
- Agen pernah gagal menjalankan bisnis karena kekurangan modal.
- Agen mengingat bahwa harga suatu barang pernah meningkat.
- Agen pernah mengalami kerugian akibat keputusan investasi.
- Agen pernah bekerja dengan seseorang yang memiliki keterampilan tertentu.

Pengalaman tersebut harus dapat memengaruhi keputusan berikutnya.

## Pengujian

Buktikan bahwa:
- Agen dapat menyimpan pengalaman.
- Agen dapat mengambil pengalaman relevan.
- Pengalaman dapat memengaruhi keputusan.
- Memori tidak tumbuh tanpa batas.
- Save/load mempertahankan memori.

Buat modul terpisah jika sesuai dengan arsitektur proyek, misalnya `systems/agents/memory.py`.

---