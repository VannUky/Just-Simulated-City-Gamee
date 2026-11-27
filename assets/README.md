# City & Macro Simulation — Complete Expansion Asset Pack (Pack 3)

## Gaya Visual & Standar Integrasi
- **Style:** Micro Pastel Top-Down Pixel Art (konsisten dengan Pack 1 & Pack 2).
- **Outline:** Soft Dark `#1E1B2E` (`RGB(30, 27, 46)`).
- **Konsistensi Routing Bangunan:** Semua 12 variasi bangunan (dalam state `active`, `bankrupt`, dan `constructing`) menggunakan kanvas seragam `32x32` px dengan `pivot: [16, 31]` dan `door_point: [16, 30]` sehingga logika pathfinding/routing warga tidak perlu diubah.

## Daftar Sheet & Metadata
1. `01_buildings_variations.png` — 12 jenis bangunan (`house_small`, `house_medium`, `house_luxury`, `apartment`, `house_abandoned`, `shop_grocery`, `shop_retail`, `factory`, `farm_garden`, `showroom`, `bank`, `gov_office`) × 3 state (`active`, `bankrupt`, `constructing`).
2. `02_construction_and_property.png` — Tile tanah kosong, kavling dijual, fondasi, scaffolding, crane kecil, material (semen, kayu, bata), serta tanda properti (`DIJUAL`, `DISEWA`, `DISITA BANK`).
3. `03_economy_and_transaction_vfx.png` — 6 ikon produk, 6 ikon sektor usaha, dan 6 VFX transaksi beranimasi 4-frame (`cash_in`, `cash_out`, `tax`, `salary`, `installment`, `default`).
4. `04_citizens_4dir_walk.png` — 6 variasi karakter warga dengan animasi jalan 4 arah konsisten (`down`, `up`, `left`, `right` × 4 frame).
5. `05_vehicles_and_street_props.png` — 5 kendaraan layanan & komersial 4 arah (`motorcycle`, `delivery_truck`, `construction_vehicle`, `ambulance`, `police_car`) + 8 prop jalan.
6. `06_status_events_and_portraits.png` — 6 ikon status warga (`hunger`, `stress`, `sick`, `unemployed`, `crime`, `retired`), 4 overlay event cuaca/kota beranimasi 4-frame (`rain`, `drought`, `festival`, `fire`), dan 5 potret avatar `24x24` px (termasuk Wali Kota).
7. `07_ui_icons_buttons_and_modals.png` — 10 ikon HUD ekonomi & kota, tombol aksi 4-state (`normal`, `hover`, `pressed`, `disabled`), dan modal konfirmasi transaksi berisiko.
8. `atlas_metadata.json` — Koordinat potong, `pivot`, `door_point`, `direction`, dan `state` untuk seluruh sprite.

Runtime saat ini masih memakai atlas lama di `Assets`; manifest yang cocok disimpan sebagai `atlas_metadata_legacy.json`. Metadata Pack 3 di `atlas_metadata.json` dipertahankan, tetapi belum diintegrasikan ke UI.
