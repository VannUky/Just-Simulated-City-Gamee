# PHASE 4 — KNOWLEDGE DISCOVERY & KNOWLEDGE GRAPH

## Tujuan

Memberikan kemampuan kepada agen untuk membangun pengetahuan dari pengalaman, bukan hanya menggunakan pengetahuan yang ditanamkan programmer.

## Kemampuan yang diperlukan

1. Concept formation:
   - Membentuk konsep berdasarkan pengalaman.
   - Menghubungkan konsep yang sudah dikenal.
   - Membuat relasi baru.

2. Pattern recognition:
   - Mengenali pola berulang.
   - Mengidentifikasi hubungan antarvariabel.
   - Membedakan korelasi dan hubungan sebab-akibat.

3. Hypothesis formation:
   - Membentuk dugaan berdasarkan pengalaman.
   - Menyimpan tingkat keyakinan.
   - Mempertimbangkan bukti yang mendukung dan menentang.

4. Knowledge composition:
   - Menggabungkan beberapa pengetahuan.
   - Membentuk hipotesis baru dari kombinasi konsep.
   - Mengembangkan hubungan yang sebelumnya belum diketahui.

5. Knowledge validation:
   - Menguji pengetahuan melalui pengalaman.
   - Memperbarui confidence berdasarkan hasil.
   - Menurunkan confidence jika terdapat bukti yang bertentangan.

6. Knowledge provenance:
   - Setiap klaim memiliki sumber.
   - Sumber dapat berupa pengalaman pribadi atau informasi sosial.
   - Bedakan fakta, observasi, dan hipotesis.

## Contoh perilaku

Seorang agen menyadari bahwa:
- Harga bahan baku meningkat ketika persediaan menurun.
- Produktivitas pekerja berpengalaman lebih tinggi.
- Bisnis tertentu menghasilkan keuntungan lebih besar pada kondisi pasar tertentu.

Agen dapat menggabungkan pengetahuan tersebut dan membentuk hipotesis baru.

Jangan membuat seluruh pengetahuan tersebut sebagai fakta yang sudah ditentukan programmer.

## Batasan

Jangan menggunakan `eval()` atau mengeksekusi kode Python yang dibuat agen.

Gunakan representasi konsep dan aturan deklaratif yang aman.

Konsep dan relasi harus dapat berkembang, tetapi tindakan operasional tetap harus memiliki mekanisme yang dapat dijalankan dunia simulasi.

## Pengujian

Buktikan bahwa:
- Agen dapat membuat klaim baru.
- Agen dapat menghubungkan konsep.
- Bukti negatif dapat menurunkan confidence.
- Hipotesis tidak otomatis dianggap fakta.
- Pengetahuan baru dapat memengaruhi keputusan setelah divalidasi.

Modul yang disarankan: `systems/agents/knowledge.py`.

---
