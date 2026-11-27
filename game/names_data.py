"""Dataset nama untuk warga kota (campuran Indonesia dan luar negeri)."""

INDO_MALE = """Budi Agus Andi Dedi Eko Fajar Gilang Hadi Irfan Joko Bambang Rizky Dimas Bayu Arif Yudi Rudi
Hendra Wahyu Teguh Slamet Sutrisno Darmawan Ahmad Muhammad Reza Fikri Ilham Galih Rangga Aditya Naufal
Farhan Rafi Bagas Putra Anjas Yoga Krisna Wawan Joni Tono Sigit Heru Ari Anton Doni Ferdi Gunawan Haris
Iwan Jaya Lukman Maman Nanda Oki Panji Rendi Surya Taufik Usman Vino Zainal""".split()

INDO_FEMALE = """Siti Sri Dewi Putri Ayu Rina Wati Yuni Lestari Ratna Indah Fitri Nur Maya Sari Intan Rani Tiara
Citra Dian Eka Fani Gita Hana Ika Jihan Kartika Lia Mega Novi Okta Pipit Rahma Salsa Tari Umi Vera Winda
Yanti Zahra Aisyah Bunga Cindy Dinda Elisa Farah Gina Hesti Imas Julia Kiki Lina Mira Nia Olivia Prita
Rosa Santi Tuti Wulan""".split()

INDO_LAST = """Santoso Wijaya Pratama Saputra Hidayat Kusuma Susanto Nugroho Setiawan Rahayu Utami Purnama
Siregar Nasution Harahap Lubis Hutapea Simanjuntak Sitompul Gunawan Wibowo Prasetyo Permana Firmansyah
Ramadhan Hakim Maulana Kurniawan Suryanto Halim Tanuwijaya Budiman Wardhana Anggraini Safitri Handayani
Puspita Maharani Sulistyo Yulianto Cahyono Mahendra Siswanto Hartono Susilo Lestari Wulandari""".split()

FOREIGN_MALE = """James John Michael David Daniel Liam Noah Lucas Ethan Oliver Hiroshi Kenji Takumi Min-jun Ji-ho
Wei Chen Rahul Arjun Omar Carlos Mateo Luca Marco Hans Lars Pierre Andrei Ivan Ahmed""".split()

FOREIGN_FEMALE = """Emma Olivia Sophia Mia Emily Sakura Yui Mei Li Ji-woo Seo-yeon Priya Ananya Fatima Layla Sofia
Isabella Camila Giulia Anna Elsa Ingrid Chloe Marie Natasha Olga Zoe Amelia""".split()

FOREIGN_LAST = """Smith Johnson Brown Miller Wilson Taylor Anderson Tanaka Sato Suzuki Kim Park Lee Wang Zhang
Patel Sharma Khan Garcia Martinez Rossi Silva Muller Schmidt Dubois Ivanov Nielsen Johansson Santos
Fernandez""".split()


def random_name(female, rng, foreign_chance=0.18):
    """Kembalikan 'Nama Belakang'. foreign_chance = peluang nama luar negeri."""
    if rng.random() < foreign_chance:
        first = rng.choice(FOREIGN_FEMALE if female else FOREIGN_MALE)
        last = rng.choice(FOREIGN_LAST)
    else:
        first = rng.choice(INDO_FEMALE if female else INDO_MALE)
        last = rng.choice(INDO_LAST)
    return f"{first} {last}"
