
# PHASE 5 — AUTONOMOUS GOAL FORMATION & PLANNING

## Tujuan

Memberikan kemampuan kepada agen untuk membentuk tujuan, menentukan prioritas, dan merencanakan tindakan.

Agen tidak boleh hanya menjalankan daftar tindakan tetap yang dibuat programmer.

## 1. Motivation System

Buat sistem motivasi dasar yang dapat memengaruhi perilaku.

Contoh:
- Bertahan hidup.
- Memenuhi kebutuhan.
- Keamanan finansial.
- Mengembangkan keterampilan.
- Meningkatkan kekayaan.
- Mencari hubungan sosial.
- Mengurangi risiko.
- Mencapai kemandirian.
- Mencari pengetahuan.

Motivasi dasar bukan daftar tujuan permanen.

Agen harus dapat membentuk subtujuan baru berdasarkan kondisi dan pengalaman.

## 2. Goal Formation

Agen harus dapat:
- Membentuk tujuan dari kebutuhan.
- Membentuk tujuan dari pengetahuan baru.
- Mengubah prioritas.
- Membatalkan tujuan yang tidak lagi relevan.
- Membentuk tujuan jangka pendek dan panjang.
- Mempertimbangkan konflik antartujuan.

Contoh:

Agen ingin meningkatkan kondisi finansial.

Dia dapat membentuk subtujuan:
- Mencari pekerjaan.
- Menghemat pengeluaran.
- Meningkatkan keterampilan.
- Mengumpulkan modal.
- Mendirikan usaha.

Subtujuan tersebut harus muncul dari proses pengambilan keputusan, bukan progression yang dipaksakan.

## 3. Planning System

Implementasikan bounded GOAP atau pendekatan perencanaan sejenis.

Agen harus dapat:
- Mempertimbangkan beberapa kemungkinan tindakan.
- Menghitung biaya dan manfaat.
- Mempertimbangkan risiko.
- Mempertimbangkan waktu.
- Mempertimbangkan ketersediaan sumber daya.
- Mengubah rencana ketika kondisi berubah.

Planner tidak boleh mengubah kondisi dunia saat melakukan simulasi rencana.

Eksekusi tindakan harus menggunakan API ekonomi yang sudah tervalidasi.

## 4. BDI Architecture

Integrasikan:
- Beliefs: apa yang diyakini agen.
- Desires: apa yang ingin dicapai.
- Intentions: tujuan yang sedang dikejar.

Beliefs harus terhubung dengan knowledge graph dan pengalaman.

## Pengujian

Buktikan bahwa:
- Agen dapat membentuk tujuan.
- Agen dapat mengubah prioritas.
- Agen dapat membuat rencana multi-langkah.
- Agen dapat membatalkan rencana yang tidak layak.
- Agen tidak dapat melakukan tindakan tanpa sumber daya yang cukup.
- Perencanaan tidak mengubah kondisi dunia.

Modul yang disarankan:
- `goals.py`
- `planner.py`
- `actions.py`

---