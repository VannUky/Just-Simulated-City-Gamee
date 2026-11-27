"""
ekonomi_core.py  --  mesin simulasi ekonomi (TANPA pygame, bisa dites headless)

Siklus uang:  warga -> toko -> pabrik -> gaji -> warga,  plus pajak, bank, pasar saham/kripto, properti.
Semua warga mulai dari Rp0. Uang awal hanya ada di Kas Kota (treasury) dan modal Bank.
"""
import math
import random
from collections import deque

from systems.accounting import AccountingLedger, ledgered_transaction
from systems.agents.actions import (
    available_actions, execute_action, planning_state,
)
from systems.agents.goals import (
    BDIState, Intention, form_goals, update_beliefs,
)
from systems.agents.learning import (
    LearningState, learning_context, objective_weights, outcome_snapshot,
    settle_pending, social_contact_count,
)
from systems.agents.memory import EpisodicMemory
from systems.agents.knowledge import KnowledgeGraph
from systems.agents.experiments import (
    ExperimentState, begin_experiment_day, capture_experiment_market,
    consider_price_experiment, finish_experiment_day,
    share_experiment_result as _share_experiment_result,
)
from systems.agents.social import (
    consider_organization, consider_social_action, end_relationship,
    ensure_social_state, new_social_state, observe_action, propose_organization,
    propose_trade_cooperation, propose_organization_rule,
    record_interaction, record_trade_interaction,
    relationship, reputation, respond_organization_invitation,
    respond_trade_offer, share_knowledge, vote_organization_rule,
)
from systems.agents.family import (
    active_partner, appoint_guardian, children_of, consider_family_action,
    consider_teaching, ensure_family_state, family_heirs, guardians_of,
    handle_death, handle_departure, new_family_state, parents_of,
    propose_partnership, register_birth, respond_partnership, siblings_of,
    teach_knowledge,
)
from systems.agents.lifecycle import (
    advance_age, consider_births, daily_mortality_probability, food_payer,
    is_adult,
)
from systems.agents.planner import BoundedPlanner
from game.names_data import random_name

HPD, DPM, DPY = 24, 30, 360          # jam/hari, hari/bulan, hari/tahun
RETIRE_AGE = 60
MAP_W, MAP_H = 1280, 800
ROAD_W = 48                          # tiga tile untuk jalan kota yang lebih lega
TICKS_PER_DAY = 8                    # titik harga intrahari untuk candlestick
PROD_PER_WORKER = 4.5                # unit barang per pekerja per hari
LOT_PRICE = 30_000_000
BUILD_COST = 15_000_000
AGENT_PLANNER = BoundedPlanner(max_depth=3, max_expansions=64)
STARTUP = {
    "shop": 15_000_000, "factory": 35_000_000, "farm": 8_000_000,
    "showroom": 35_000_000, "car_factory": 120_000_000,
    "builder": 20_000_000, "repair": 12_000_000,
    "delivery": 10_000_000, "cleaning": 8_000_000,
}
INPUT_PRICES = {
    "seeds": 20_000.0,
    "raw_materials": 100_000.0,
    "energy": 20_000.0,
    "components": 2_000_000.0,
    "building_materials": 1_000_000.0,
    "spare_parts": 80_000.0,
    "fuel": 20_000.0,
    "cleaning_supplies": 35_000.0,
}
DAILY_IMPORT_CAPACITY = {item: 1_000.0 for item in INPUT_PRICES}
DAILY_IMPORT_CAPACITY["components"] = 30.0
PRODUCTION_RECIPES = {
    "farm": {
        "product": "food", "inputs": {"seeds": 0.12}, "output": 6.75,
        "labor_hours": 8.0, "operating_cost": 8_000.0, "capacity": 8.0,
        "skill": "skill", "spoilage": 0.02,
    },
    "factory": {
        "product": "goods", "inputs": {"raw_materials": 0.1, "energy": 0.5},
        "output": 4.5, "labor_hours": 8.0, "operating_cost": 15_000.0,
        "capacity": 8.0, "skill": "skill", "spoilage": 0.015,
    },
    "car_factory": {
        "product": "vehicles", "inputs": {"components": 0.1, "energy": 0.5},
        "output": 0.025, "labor_hours": 8.0, "operating_cost": 40_000.0,
        "capacity": 4.0, "skill": "skill", "spoilage": 0.0,
    },
    "builder": {
        "product": "construction", "inputs": {"building_materials": 0.12},
        "output": 0.1, "labor_hours": 8.0, "operating_cost": 35_000.0,
        "capacity": 4.0, "skill": "construction_skill", "spoilage": 0.0,
    },
    "repair": {
        "product": "repair", "inputs": {"spare_parts": 0.1},
        "output": 0.8, "labor_hours": 6.0, "operating_cost": 5_000.0,
        "capacity": 8.0, "skill": "repair_skill", "spoilage": 0.0,
    },
    "delivery": {
        "product": "delivery", "inputs": {"fuel": 0.1},
        "output": 0.8, "labor_hours": 6.0, "operating_cost": 5_000.0,
        "capacity": 8.0, "skill": "skill", "spoilage": 0.0,
    },
    "cleaning": {
        "product": "cleaning", "inputs": {"cleaning_supplies": 0.1},
        "output": 1.0, "labor_hours": 6.0, "operating_cost": 5_000.0,
        "capacity": 8.0, "skill": "skill", "spoilage": 0.0,
    },
}
UNSECURED_LOAN_MIN = 1_000_000
UNSECURED_LOAN_MAX = 10_000_000
SECURED_LOAN_MAX = 50_000_000
CAR_COST, CAR_PRICE = 10_000_000.0, 25_000_000.0
BASE_HOUSE_VALUE = 300_000_000
MAX_POP = 140
KUR_LIMIT = 6                        # jumlah usaha pertama yang dapat kredit usaha rakyat

SKINS = [(255, 224, 189), (241, 194, 125), (224, 172, 105), (198, 134, 66), (141, 85, 36), (92, 56, 28)]
HAIRS = [(20, 20, 20), (60, 40, 20), (110, 70, 30), (170, 110, 50), (220, 190, 90), (130, 30, 30), (90, 90, 100)]
SHIRTS = [(224, 80, 80), (80, 160, 224), (90, 190, 110), (240, 170, 50), (170, 100, 210),
          (240, 120, 170), (70, 200, 200), (240, 240, 240), (60, 60, 80)]
PANTS = [(50, 60, 110), (60, 60, 60), (110, 80, 50), (40, 90, 70), (90, 50, 90)]


def rp(x):
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e12:
        return f"{sign}Rp{x / 1e12:.2f}T"
    if x >= 1e9:
        return f"{sign}Rp{x / 1e9:.2f}M"
    if x >= 1e6:
        return f"{sign}Rp{x / 1e6:.1f}jt"
    if x >= 1e3:
        return f"{sign}Rp{x / 1e3:.0f}rb"
    return f"{sign}Rp{x:.0f}"


def annuity(p, annual_rate, months):
    r = annual_rate / 12
    if r <= 0:
        return p / months
    return p * r / (1 - (1 + r) ** -months)


# ----------------------------------------------------------------------------- kebijakan
class Policy:
    def __init__(self):
        self.min_wage = 3_000_000
        self.tax_pph = 0.05            # pajak penghasilan (gaji di atas PTKP)
        self.pph_exempt = 4_500_000    # PTKP per bulan
        self.tax_ppn = 0.11            # pajak belanja
        self.tax_pbb = 0.005           # pajak properti per tahun
        self.tax_corp = 0.22           # pajak laba usaha
        self.tax_stock = 0.001         # pajak transaksi jual saham
        self.tax_crypto = 0.0021       # pajak transaksi jual kripto
        self.deposit_rate = 0.05       # bunga tabungan / tahun
        self.loan_rate = 0.10          # bunga kredit / tahun
        self.welfare = 1_000_000       # bansos / bulan untuk yang menganggur
        self.gov_jobs_share = 0.30     # maks pegawai kota (porsi penduduk)


# key, label, step, min, max, format
POLICY_FIELDS = [
    ("min_wage", "Upah minimum", 250_000, 500_000, 15_000_000, "rp"),
    ("tax_pph", "PPh gaji", 0.01, 0, 0.5, "pct"),
    ("pph_exempt", "PTKP / bulan", 500_000, 0, 20_000_000, "rp"),
    ("tax_ppn", "PPN belanja", 0.01, 0, 0.5, "pct"),
    ("tax_pbb", "PBB / tahun", 0.001, 0, 0.05, "pct1"),
    ("tax_corp", "Pajak laba usaha", 0.01, 0, 0.6, "pct"),
    ("tax_stock", "Pajak jual saham", 0.001, 0, 0.2, "pct2"),
    ("tax_crypto", "Pajak jual kripto", 0.001, 0, 0.2, "pct2"),
    ("deposit_rate", "Bunga tabungan", 0.005, 0, 0.3, "pct1"),
    ("loan_rate", "Bunga kredit", 0.005, 0.01, 0.5, "pct1"),
    ("welfare", "Bansos / bulan", 250_000, 0, 5_000_000, "rp"),
    ("gov_jobs_share", "Maks pegawai kota", 0.05, 0, 0.8, "pct"),
]


# ----------------------------------------------------------------------------- kota
class Lot:
    __slots__ = ("rect", "door", "road_y", "kind", "building", "land_owner")

    def __init__(self, rect, door, road_y, kind):
        self.rect, self.door, self.road_y, self.kind = rect, door, road_y, kind
        self.building = None
        self.land_owner = None


def generate_city(rng):
    ROAD, BX, BY = ROAD_W, 5, 4
    bw = (MAP_W - (BX + 1) * ROAD) / BX          # 160
    bh = (MAP_H - (BY + 1) * ROAD) / BY          # 120
    vroads = [ROAD / 2 + i * (bw + ROAD) for i in range(BX + 1)]
    hroads = [ROAD / 2 + j * (bh + ROAD) for j in range(BY + 1)]
    lots = []
    for i in range(BX):
        for j in range(BY):
            x0 = ROAD + i * (bw + ROAD)
            y0 = ROAD + j * (bh + ROAD)
            lw, lh = bw / 2, bh / 2
            for a in range(2):
                for b in range(2):
                    rect = (x0 + a * lw, y0 + b * lh, lw, lh)
                    cx = rect[0] + lw / 2
                    if b == 0:
                        door, road = (cx, y0 + 1), hroads[j]
                    else:
                        door, road = (cx, y0 + bh - 1), hroads[j + 1]
                    lots.append(Lot(rect, door, road, "biz"))
    hall = min(lots, key=lambda l: (l.door[0] - MAP_W / 2) ** 2 + (l.door[1] - MAP_H / 2) ** 2)
    hall.kind = "hall"
    others = [l for l in lots if l is not hall]
    exch = min(others, key=lambda l: (l.door[0] - hall.door[0]) ** 2 + (l.door[1] - hall.door[1]) ** 2 + 1e-3 * rng.random())
    exch.kind = "exchange"
    rest = [l for l in others if l is not exch]
    rng.shuffle(rest)
    for k, l in enumerate(rest):
        l.kind = "park" if k < 5 else ("house" if k == 5 else "biz")
    return lots, vroads, hroads, hall


class House:
    kind = "house"

    def __init__(self, w, lot):
        r = w.rng
        self.w, self.lot = w, lot
        self.quality = r.uniform(0.8, 1.3)
        self.base_structure_value = BASE_HOUSE_VALUE
        self.cap = 140
        self.owner = None            # None = milik Kota/pengembang
        self.occupants = []
        self.color_i = r.randrange(6)
        self.condition = 1.0
        self.bank_owned = False
        self.bank_value = 0.0

    @property
    def value(self):
        return self.land_value + self.structure_value

    @property
    def land_value(self):
        return self.w.lot_price

    @property
    def structure_value(self):
        return self.base_structure_value * self.quality * self.w.house_index * self.condition

    def rent_pp(self):
        return self.value * self.w.rent_yield / 12 / self.cap

    @property
    def free(self):
        return self.cap - len(self.occupants)


class Hall:
    """Balai Kota = pemberi kerja pemerintah. Jumlah pegawai mengikuti anggaran."""
    kind = "hall"
    name = "Balai Kota"

    def __init__(self, w, lot):
        self.w, self.lot = w, lot
        lot.building = self
        self.workers = []
        self.max_workers = 0

    @property
    def wage(self):
        return self.w.policy.min_wage * 1.1

    @property
    def vacancies(self):
        return max(0, self.max_workers - len(self.workers))

    def pay_for(self, c):
        return self.wage

    def can_hire(self):
        return self.vacancies > 0


class Business:
    def __init__(self, w, kind, lot, owner, capital):
        r = w.rng
        self.w, self.kind, self.lot, self.owner = w, kind, lot, owner
        self.ledger_id = w.next_business_id
        w.next_business_id += 1
        lot.building = self
        self.cash = capital * 0.35
        self.land_value = w.lot_price
        self.equipment_value = capital * 0.4
        self.car_stock = 0.0
        self.input_inventory = {}
        self.input_costs = {}
        self.service_inventory = {}
        self.service_costs = {}
        self.production_progress = 0.0
        self.production_failed = ""
        self.work_hours = 40.0
        self.workers = []
        self.max_workers = (8 if kind in ("factory", "car_factory") else
                            (2 if kind in ("builder", "repair", "delivery", "cleaning") else 4))
        self.wage = w.policy.min_wage * r.uniform(1.0, 1.12)
        self.stock = 0.0
        self.price = {
            "farm": 20_000.0, "factory": 32_000.0, "shop": 44_000.0,
            "showroom": CAR_PRICE, "car_factory": CAR_PRICE,
            "builder": BUILD_COST, "repair": 200_000.0,
            "delivery": 150_000.0, "cleaning": 100_000.0,
        }.get(kind, 44_000.0)
        self.markup = 0.38           # khusus toko
        self.cost_avg = 32_000.0     # khusus toko: harga beli rata-rata
        self.innovation_price_multiplier = 1.0
        self.rev = self.exp = 0.0
        self.last_profit = 0.0
        self.loss_months = 0
        self.vac_weeks = 0
        self.age_days = 0
        self.demand_today = self.sold_today = 0.0
        self.daily_demand = deque(maxlen=7)
        self.soldout_hist = deque(maxlen=7)
        self.over_hist = deque(maxlen=7)
        self.prod = 0.0
        self.unit_cost = (
            CAR_COST if kind == "car_factory"
            else max(1_000.0, self.price * 0.5)
        )
        self.quality = max(0.25, min(1.5, 0.65 + 0.5 * owner.skill))
        self.market_product = (
            PRODUCTION_RECIPES[kind]["product"]
            if kind in PRODUCTION_RECIPES
            else ("retail_goods" if kind == "shop" else "vehicles")
        )
        self.loan = None
        labels = {"factory": "Pabrik", "farm": "Kebun", "shop": "Toko",
                  "showroom": "Showroom", "car_factory": "Pabrik Mobil",
                  "builder": "Industri Bangunan", "repair": "Jasa Servis",
                  "delivery": "Jasa Antar", "cleaning": "Jasa Kebersihan"}
        self.name = labels[kind] + " " + owner.first

    @property
    def inventory_value(self):
        unit_cost = self.cost_avg if self.kind == "shop" else self.unit_cost
        vehicle_unit_cost = self.unit_cost if self.kind == "car_factory" else CAR_COST
        return (
            self.stock * unit_cost
            + self.car_stock * vehicle_unit_cost
            + sum(quantity * self.input_costs.get(item, INPUT_PRICES.get(item, 0.0))
                  for item, quantity in self.input_inventory.items())
            + sum(quantity * self.service_costs.get(item, 0.0)
                  for item, quantity in self.service_inventory.items())
        )

    @property
    def asset_value(self):
        return self.cash + self.inventory_value + self.equipment_value + self.land_value

    @property
    def vacancies(self):
        return max(0, self.max_workers - len(self.workers))

    def pay_for(self, c):
        skill = (c.construction_skill if self.kind == "builder" else
                 (c.repair_skill if self.kind == "repair" else c.skill))
        fraction = self.work_hours / 40.0
        return max(self.w.policy.min_wage * fraction,
                   self.wage * (0.85 + 0.5 * skill)
                   * c.work_capacity * fraction)

    def payroll_week(self):
        return sum(self.pay_for(c) for c in self.workers) * 7 / DPM

    def can_hire(self):
        return self.vacancies > 0 and self.cash >= (self.payroll_week() + self.wage * 7 / DPM) * 4

    def initialize_startup_inventory(self, capital):
        budget = capital * 0.25
        recipe = PRODUCTION_RECIPES.get(self.kind)
        if recipe:
            input_cost = sum(
                quantity * INPUT_PRICES[item]
                for item, quantity in recipe["inputs"].items()
            )
            if input_cost > 0:
                batches = budget / input_cost
                for item, quantity in recipe["inputs"].items():
                    self.input_inventory[item] = quantity * batches
                    self.input_costs[item] = INPUT_PRICES[item]
        elif self.kind == "shop":
            self.stock = budget / max(self.cost_avg, 1.0)
        elif self.kind == "showroom":
            self.car_stock = max(1.0, budget / CAR_COST)
            self.cash = max(
                0.0, self.cash - max(0.0, self.car_stock * CAR_COST - budget)
            )


# ----------------------------------------------------------------------------- pasar
class Asset:
    def __init__(self, sym, name, kind, price, vol, drift, liq):
        self.sym, self.name, self.kind = sym, name, kind
        self.price = float(price)
        self.base = float(price)         # harga awal (untuk indeks)
        self.fund = float(price)
        self.vol, self.drift, self.liq = vol, drift, liq
        self.hist = deque([float(price)] * 60, maxlen=120)      # penutupan harian
        self.ticks = deque(maxlen=TICKS_PER_DAY * 400)           # (harga, volume) intrahari
        self.flow = 0.0
        self.traded = 0.0                # nilai transaksi hari ini (Rp)
        # --- kontrol pemain
        self.halted = False              # perdagangan dihentikan
        self.vol_mult = 1.0              # pengali volatilitas
        self.bias = 0.0                  # tambahan tren per tahun (+ bullish / - bearish)

    def ma(self, n=30):
        h = list(self.hist)[-n:]
        return sum(h) / len(h)

    def momentum(self):
        return self.price / self.ma(30) - 1

    def change(self, n=30):
        n = min(n, len(self.hist))
        return self.price / self.hist[-n] - 1

    def add_day(self, p0, p1, rng, volume):
        """Pecah pergerakan sehari (p0 -> p1) jadi TICKS_PER_DAY titik (jembatan Brownian)."""
        n = TICKS_PER_DAY
        sg = self.vol * (self.vol_mult if not self.halted else 0.0) / math.sqrt(DPY * n) * 0.9
        weights = [rng.uniform(0.4, 1.6) for _ in range(n)]
        tw = sum(weights)
        for k in range(1, n + 1):
            f = k / n
            px = p0 * (p1 / p0) ** f
            if k < n:
                px *= math.exp(rng.gauss(0, sg) * math.sqrt(4 * f * (1 - f)))
            self.ticks.append((max(px, 1e-6), volume * weights[k - 1] / tw))
        self.hist.append(p1)


class Market:
    def __init__(self, rng):
        self.rng = rng
        self.sent = 0.0
        A = Asset
        self.assets = {a.sym: a for a in [
            A("KOTA", "Kota Infra", "stock", 2500, 0.22, 0.07, 2e9),
            A("TANI", "Tani Makmur", "stock", 1800, 0.18, 0.06, 2e9),
            A("TEKA", "Teka Teknologi", "stock", 4200, 0.35, 0.10, 2e9),
            A("MIGA", "Miga Energi", "stock", 3100, 0.30, 0.08, 2e9),
            A("RITL", "Ritel Raya", "stock", 1200, 0.20, 0.06, 2e9),
            A("BITO", "Bito Coin", "crypto", 500_000, 0.75, 0.12, 1e9),
            A("ETRA", "Etra Coin", "crypto", 35_000, 0.85, 0.12, 1e9),
            A("DOGO", "Dogo Coin", "crypto", 450, 1.10, 0.05, 1e9),
        ]}
        self._prehistory(180)

    def _prehistory(self, days):
        """Riwayat harga awal supaya chart tidak kosong: random walk lalu diskala agar berakhir di harga awal."""
        r = self.rng
        for a in self.assets.values():
            path = [1.0]
            for _ in range(days):
                ret = a.drift / DPY + a.vol / math.sqrt(DPY) * r.gauss(0, 1) - 0.01 * math.log(path[-1])
                path.append(path[-1] * (1 + ret))
            k = a.base / path[-1]
            a.hist.clear()
            a.ticks.clear()
            for i in range(days):
                base_vol = a.liq * 0.0006 * r.uniform(0.5, 1.6)
                a.add_day(path[i] * k, path[i + 1] * k, r, base_vol)
            a.price = a.base

    def step(self, econ):
        r = self.rng
        self.sent = 0.96 * self.sent + r.gauss(0, 0.006)
        for a in self.assets.values():
            p0 = a.price
            if a.halted:                      # perdagangan dihentikan: harga beku
                a.flow = 0.0
                a.traded = 0.0
                a.add_day(p0, p0, r, 0.0)
                continue
            mu = a.drift / DPY + a.bias / DPY
            sg = a.vol * a.vol_mult / math.sqrt(DPY)
            beta = 1.0 if a.kind == "stock" else 1.6
            ret = mu + sg * r.gauss(0, 1) + beta * self.sent * 0.2
            if a.kind == "stock":
                ret += econ * 0.0005
            elif r.random() < 1 / 70:
                ret += r.choice((-1, 1)) * r.uniform(0.08, 0.30)
            a.fund *= 1 + a.drift / DPY
            ret -= 0.004 * math.log(a.price / a.fund)
            ret += max(-0.06, min(0.06, a.flow / a.liq))
            a.price = max(a.price * (1 + ret), a.fund * 0.05)
            volume = a.traded + a.liq * 0.0006 * r.uniform(0.5, 1.6) * (1 + 6 * abs(ret))
            a.add_day(p0, a.price, r, volume)
            a.flow = 0.0
            a.traded = 0.0

    # ---- data untuk chart
    def candles(self, sym, tf_days=1, limit=60):
        """Gabungkan tick jadi candle (open, high, low, close, volume). tf_days: 1 / 7 / 30."""
        t = list(self.assets[sym].ticks)
        n = max(1, int(TICKS_PER_DAY * tf_days))
        out = []
        end = len(t)
        while end > 0 and len(out) < limit:
            chunk = t[max(0, end - n):end]
            prices = [c[0] for c in chunk]
            out.append((prices[0], max(prices), min(prices), prices[-1], sum(c[1] for c in chunk)))
            end -= n
        out.reverse()
        return out

    def index(self, kind):
        """Indeks gabungan (100 = harga awal) dari penutupan harian."""
        group = [a for a in self.assets.values() if a.kind == kind]
        n = min(len(a.hist) for a in group)
        return [100 * sum(list(a.hist)[-n + i] / a.base for a in group) / len(group) for i in range(n)]

    def fear_greed(self):
        """0 (takut) .. 1 (serakah): dari sentimen dan momentum rata-rata."""
        mom = sum(a.change(14) for a in self.assets.values()) / len(self.assets)
        return max(0.0, min(1.0, 0.5 + self.sent * 4 + mom * 1.5))


# ----------------------------------------------------------------------------- bank
class Loan:
    def __init__(self, borrower, principal, rate, months, kind, ref=None):
        self.borrower, self.balance, self.kind, self.ref = borrower, principal, kind, ref
        self.rate = rate / 12
        self.months = months
        self.pay = annuity(principal, rate, months)
        self.missed = 0


class Bank:
    def __init__(self, capital):
        self.cash = capital
        self.equity = capital
        self.deposits = 0.0
        self.profit = 0.0
        self.loss = 0.0
        self.loan_book = 0.0
        self.repossessed_assets = 0.0


# ----------------------------------------------------------------------------- warga
class Citizen:
    def __init__(self, w, cid, young=False, child=False):
        r = w.rng
        bt = r.betavariate
        self.w, self.id = w, cid
        self.female = r.random() < 0.5
        self.name = random_name(self.female, r)
        self.age = 0.0 if child else (
            r.uniform(18, 26) if young else r.uniform(18, 48)
        )
        self.risk, self.greed, self.frugal = bt(2, 2), bt(2, 2), bt(2, 2)
        self.herd, self.optimism, self.patience = bt(2, 2.5), bt(2, 2), bt(2, 2)
        self.skill, self.entre = (
            (r.uniform(0.02, 0.08), r.uniform(0.0, 0.12))
            if child else (bt(2.2, 2.2), bt(1.3, 3.5))
        )
        self.persuasion = bt(2, 2)
        self.construction_skill = r.uniform(0.01, 0.06) if child else bt(1.5, 3.0)
        self.repair_skill = r.uniform(0.01, 0.06) if child else bt(1.5, 3.0)
        self.parenting_desire = (self.optimism + self.patience) / 2.0
        self.education_level = (
            0.0 if child else min(0.8, max(0.1, self.skill))
        )
        self.school_days = 0
        self.adult_since_day = None if child else w.day
        self.cash = 0.0
        self.savings = 0.0
        self.hold = {}               # simbol -> [unit, harga rata-rata]
        self.loans = []
        self.home = None
        self.houses = []
        self.job = None
        self.business = None
        self.unemp_days = 0
        self.missed_rent = 0
        self.missed_pay = 0
        self.credit_block = 0
        self.hunger = 0
        self.health = 100.0
        self.happy = 50.0
        self.stress = 0.0
        self.fear = 0.0
        self.sadness = 0.0
        self.depression = 0.0
        self.gigs_done = 0
        self.last_gig = ""
        self.last_gig_day = -1
        self.crimes = 0
        self.exp_acc = 0.0
        self.est_exp = 2_000_000.0
        self.learning = 0.02
        self.financial_literacy = 0.0
        self.credit_score = 560.0
        self.vehicle_value = 0.0
        self.vehicle_color = None
        self.thoughts = deque(maxlen=8)
        self.memory = EpisodicMemory()
        self.knowledge = KnowledgeGraph()
        self.bdi = BDIState()
        self.adaptive_learning = LearningState()
        self.experiments = ExperimentState()
        self.look = (r.randrange(len(SKINS)), r.randrange(len(HAIRS)),
                     r.randrange(len(SHIRTS)), r.randrange(len(PANTS)))
        self.label = self._label()

    def _label(self):
        if self.entre > 0.55 and self.risk > 0.5:
            return "Pengusaha Nekat"
        if self.risk > 0.72:
            return "Penjudi Pasar"
        if self.frugal > 0.7 and self.risk < 0.45:
            return "Penabung Hemat"
        if self.greed > 0.72:
            return "Pemburu Cuan"
        if self.herd > 0.7:
            return "Pengikut Tren"
        if self.skill > 0.7:
            return "Pekerja Ahli"
        if self.frugal < 0.28:
            return "Si Boros"
        return "Warga Biasa"

    @property
    def first(self):
        return self.name.split()[0]

    @property
    def holdings_value(self):
        a = self.w.market.assets
        return sum(h[0] * a[s].price for s, h in self.hold.items())

    @property
    def debt(self):
        return sum(l.balance for l in self.loans)

    @property
    def emotion(self):
        if self.depression >= 0.65:
            return "depresi"
        if self.fear >= 0.65:
            return "takut"
        if self.sadness >= 0.65:
            return "sedih"
        if self.stress >= 0.7:
            return "tertekan"
        return "stabil" if self.happy >= 45 else "murung"

    @property
    def work_capacity(self):
        return max(0.55, min(1.1, 0.78 + self.happy / 250
                             - self.stress * 0.16 - self.depression * 0.2))

    @property
    def assets(self):
        business_assets = self.business.asset_value if self.business else 0.0
        vacant_land = sum(self.w.lot_price for lot in self.w.lots
                          if lot.land_owner is self and lot.building is None)
        social_assets = sum(
            organization["fund"]
            * organization["members"].get(str(self.id), {}).get("share", 0.0)
            for organization in getattr(self.w, "social_state", {}).get(
                "organizations", {}
            ).values()
            if organization["status"] == "active"
        )
        return (self.cash + self.savings + self.holdings_value
                + sum(h.value for h in self.houses) + business_assets
                + vacant_land + self.vehicle_value + social_assets)

    @property
    def networth(self):
        return self.assets - self.debt

    def income_est(self):
        if self.job:
            return self.job.pay_for(self)
        if self.business:
            return max(self.business.last_profit, 0) + self.w.policy.min_wage * 0.8
        return self.w.policy.welfare

    def think(self, msg):
        self.thoughts.appendleft((self.w.day, msg))

    def learn(self, amount, financial=False):
        self.learning = min(1.0, self.learning + amount * (1.0 - self.learning))
        if financial:
            self.financial_literacy = min(1.0, self.financial_literacy + amount * (1.0 - self.financial_literacy))


def _consumer_business_scope(world, citizen, want):
    return [
        business for business in world.businesses
        if business.kind in ("shop", "farm", "factory")
    ]


def _showroom_business_scope(world, showroom):
    return [
        business for business in world.businesses
        if business is showroom or business.kind == "car_factory"
    ]


def _shop_restock_business_scope(world, shop):
    return [
        business for business in world.businesses
        if business is shop or (
            business.kind in ("factory", "farm") and business.stock >= 1
        )
    ]


def _random_event_business_scope(world):
    return [
        business for business in world.businesses
        if business.kind in ("farm", "shop")
    ]


def _one_business_scope(world, business, *args, **kwargs):
    return [business]


def _production_business_scope(world, business=None, *args, **kwargs):
    if business is not None:
        return [business]
    return [
        business for business in world.businesses
        if business.kind in PRODUCTION_RECIPES
    ]


def _all_business_scope(world, *args, **kwargs):
    return world.businesses


def _organization_business_scope(world, organization_id):
    organization = ensure_social_state(world)["organizations"].get(
        str(organization_id)
    )
    if organization is None:
        return []
    business_ids = {
        member["business_id"]
        for member in organization["members"].values()
    }
    return [
        business for business in world.businesses
        if business.ledger_id in business_ids
    ]


def _cooperation_business_scope(world, offer_id):
    offer = ensure_social_state(world)["offers"].get(str(offer_id))
    if offer is None:
        return []
    business_ids = {
        offer["buyer_business_id"], offer["seller_business_id"],
    }
    return [
        business for business in world.businesses
        if business.ledger_id in business_ids
    ]


# ----------------------------------------------------------------------------- dunia
class World:
    def __init__(self, seed=None, n_pop=60):
        self.seed = seed if seed is not None else random.randrange(1000, 1_000_000)
        self.rng = random.Random(self.seed)
        self.policy = Policy()
        self.market = Market(self.rng)
        # Dana awal berasal dari kas kota; cadangan bank adalah bagian dari dana tersebut.
        self.bank = Bank(300_000_000)
        self.treasury = 3_000_000_000.0
        self.max_population = MAX_POP
        self.days_per_year = DPY
        self.day, self.hour = 0, 7.0
        self.house_index = 1.0
        self.rent_yield = 0.065
        self.lots, self.vroads, self.hroads, hall_lot = generate_city(self.rng)
        self.exchange_lot = next(l for l in self.lots if l.kind == "exchange")
        self.houses = [House(self, l) for l in self.lots if l.kind == "house"]
        for h in self.houses:
            h.lot.building = h
        self.hall = Hall(self, hall_lot)
        self.businesses = []
        self.citizens = []
        self.loans = []
        self.next_id = 1
        self.next_business_id = 1
        self.mayor_id = None
        self.next_election_day = DPY
        self.government_learning = 0.02
        self.auto_policy = True
        self.last_random_event = -90
        self.events = []             # (id, kind, title, sub)
        self._ev = 0
        self.crime_history = deque(maxlen=30)
        self.gig_count = 0
        self.trade_contracts = deque(maxlen=2_000)
        self.next_trade_id = 1
        self.social_state = new_social_state()
        self.family_state = new_family_state()
        self.import_supply_remaining = dict(DAILY_IMPORT_CAPACITY)
        self.rev_week = 0.0
        self.rev_ma = 0.0
        self.sales_hist = deque([0.0] * 30, maxlen=30)
        self.sales_today = 0.0
        self.cpi_base = None
        self.series = {k: deque(maxlen=500) for k in
                       ("uang", "kekayaan", "nganggur", "gini", "ihk", "pdb", "kas_kota",
                        "penduduk", "emosi", "kriminal")}
        for _ in range(n_pop):
            self.add_citizen()
        self.housing_market()
        self.weekly_start()
        self.job_market()
        self._initialize_ledger()
        self.record()
        self.log("info", "SELAMAT DATANG", f"{n_pop} warga, semua mulai dari Rp0")

    def migrate_save(self):
        """Tambahkan state baru ke save lama tanpa menghapus progres pemain."""
        for attr, value in (("auto_policy", True), ("mayor_id", None),
                            ("next_election_day", self.day + DPY),
                            ("government_learning", 0.02), ("last_random_event", self.day),
                            ("max_population", MAX_POP), ("days_per_year", DPY),
                            ("observability_schema_version", 1)):
            if not hasattr(self, attr):
                setattr(self, attr, value)
        bank = self.bank
        if not hasattr(bank, "loan_book"):
            bank.loan_book = sum(loan.balance for loan in self.loans)
        if not hasattr(bank, "equity"):
            bank.equity = bank.cash + bank.loan_book - bank.deposits
        if not hasattr(bank, "repossessed_assets"):
            bank.repossessed_assets = 0.0
        for house in self.houses:
            if not hasattr(house, "condition"):
                house.condition = 1.0
            if not hasattr(house, "base_structure_value"):
                house.base_structure_value = BASE_HOUSE_VALUE
            if not hasattr(house, "bank_owned"):
                house.bank_owned = False
            if not hasattr(house, "bank_value"):
                house.bank_value = 0.0
        for lot in self.lots:
            if not hasattr(lot, "land_owner"):
                lot.land_owner = None
        for citizen in self.citizens:
            for attr, value in (("learning", 0.02), ("financial_literacy", 0.0),
                                ("credit_score", 560.0), ("vehicle_value", 0.0),
                                ("vehicle_color", None), ("persuasion", 0.5),
                                ("construction_skill", 0.25), ("repair_skill", 0.25),
                                ("stress", 0.0), ("fear", 0.0), ("sadness", 0.0),
                                ("depression", 0.0), ("gigs_done", 0),
                                ("last_gig", ""), ("crimes", 0)):
                if not hasattr(citizen, attr):
                    setattr(citizen, attr, value)
            if not hasattr(citizen, "memory"):
                citizen.memory = EpisodicMemory()
            if not hasattr(citizen, "knowledge"):
                citizen.knowledge = KnowledgeGraph()
            if not hasattr(citizen, "bdi"):
                citizen.bdi = BDIState()
            if not hasattr(citizen, "adaptive_learning"):
                citizen.adaptive_learning = LearningState()
            if not hasattr(citizen, "experiments"):
                citizen.experiments = ExperimentState()
            if not hasattr(citizen, "parenting_desire"):
                citizen.parenting_desire = (
                    getattr(citizen, "optimism", 0.5)
                    + getattr(citizen, "patience", 0.5)
                ) / 2.0
            if not hasattr(citizen, "education_level"):
                citizen.education_level = min(0.8, citizen.age / 60.0)
            if not hasattr(citizen, "school_days"):
                citizen.school_days = 0
            if not hasattr(citizen, "adult_since_day"):
                citizen.adult_since_day = self.day if citizen.age >= 18 else None
        for business in self.businesses:
            if not hasattr(business, "innovation_price_multiplier"):
                business.innovation_price_multiplier = 1.0
            if not hasattr(business, "land_value"):
                business.land_value = self.lot_price
            if not hasattr(business, "equipment_value"):
                business.equipment_value = STARTUP.get(business.kind, 0) * 0.7
            if not hasattr(business, "car_stock"):
                business.car_stock = 0.0
            if not hasattr(business, "input_inventory"):
                business.input_inventory = {}
            if not hasattr(business, "input_costs"):
                business.input_costs = {}
            if not hasattr(business, "service_inventory"):
                business.service_inventory = {}
            if not hasattr(business, "service_costs"):
                business.service_costs = {}
            if not hasattr(business, "production_progress"):
                business.production_progress = 0.0
            if not hasattr(business, "production_failed"):
                business.production_failed = ""
            if not hasattr(business, "work_hours"):
                business.work_hours = 40.0
            if not hasattr(business, "unit_cost"):
                business.unit_cost = (
                    CAR_COST if business.kind == "car_factory"
                    else max(1_000.0, business.price * 0.5)
                )
            if not hasattr(business, "quality"):
                business.quality = 1.0
            if not hasattr(business, "market_product"):
                business.market_product = (
                    PRODUCTION_RECIPES[business.kind]["product"]
                    if business.kind in PRODUCTION_RECIPES
                    else ("retail_goods" if business.kind == "shop" else "vehicles")
                )
        for citizen in self.citizens:
            if not hasattr(citizen, "last_gig_day"):
                citizen.last_gig_day = -1
        if not hasattr(self, "trade_contracts"):
            self.trade_contracts = deque(maxlen=2_000)
        elif not isinstance(self.trade_contracts, deque):
            self.trade_contracts = deque(self.trade_contracts, maxlen=2_000)
        ensure_social_state(self)
        ensure_family_state(self)
        if not hasattr(self, "next_trade_id"):
            self.next_trade_id = 1
        if not hasattr(self, "import_supply_remaining"):
            self.import_supply_remaining = dict(DAILY_IMPORT_CAPACITY)
        if not hasattr(self, "crime_history"):
            self.crime_history = deque(maxlen=30)
        if not hasattr(self, "gig_count"):
            self.gig_count = 0
        if not hasattr(self, "series"):
            self.series = {}
        for key in ("uang", "kekayaan", "nganggur", "gini", "ihk", "pdb",
                    "kas_kota", "penduduk", "emosi", "kriminal"):
            self.series.setdefault(key, deque(maxlen=500))
        if not hasattr(self, "next_business_id"):
            self.next_business_id = 1
        for business in self.businesses:
            if not hasattr(business, "ledger_id"):
                business.ledger_id = self.next_business_id
                self.next_business_id += 1
            else:
                self.next_business_id = max(self.next_business_id, business.ledger_id + 1)
        if not hasattr(self, "ledger"):
            self._initialize_ledger()
        elif self.ledger.schema_version != AccountingLedger.SCHEMA_VERSION:
            self.ledger.migrate_schema(self.day, self._ledger_snapshot())
        self._ledger_capture_depth = 0

    def _initialize_ledger(self):
        self.ledger = AccountingLedger()
        self._ledger_capture_depth = 0
        self.ledger.seed_opening_balances(self.day, self._ledger_snapshot())

    def _ledger_snapshot(self, citizen_ids=None, business_ids=None):
        balances = {
            "government:cash": (self.treasury, "debit"),
            "bank:cash": (self.bank.cash, "debit"),
            "bank:deposits": (self.bank.deposits, "credit"),
            "bank:loan_book": (self.bank.loan_book, "debit"),
            "bank:equity": (self.bank.equity, "credit"),
            "bank:repossessed_assets": (self.bank.repossessed_assets, "debit"),
        }
        for citizen in self.citizens:
            if citizen_ids is not None and citizen.id not in citizen_ids:
                continue
            prefix = f"citizen:{citizen.id}"
            balances[f"{prefix}:cash"] = (citizen.cash, "debit")
            balances[f"{prefix}:savings"] = (citizen.savings, "debit")
            balances[f"{prefix}:loan_liability"] = (
                sum(loan.balance for loan in citizen.loans), "credit"
            )
            for symbol, holding in citizen.hold.items():
                balances[f"{prefix}:investment:{symbol}"] = (
                    holding[0] * holding[1], "debit"
                )
        for business in self.businesses:
            if business_ids is not None and business.ledger_id not in business_ids:
                continue
            balances[f"business:{business.ledger_id}:cash"] = (business.cash, "debit")
            balances[f"business:{business.ledger_id}:inventory"] = (
                business.inventory_value, "debit"
            )
        for organization in self.social_state["organizations"].values():
            balances[
                f"organization:{organization['id']}:cash"
            ] = (organization.get("fund", 0.0), "debit")
        return balances

    def reconcile_ledger(self, tolerance=0.01):
        return self.ledger.reconcile(self._ledger_snapshot(), tolerance)

    # ---- util
    @property
    def lot_price(self):
        return LOT_PRICE * self.house_index

    def log(self, kind, title, sub=""):
        self._ev += 1
        self.events.append((self._ev, kind, title, sub))
        if len(self.events) > 60:
            self.events = self.events[-60:]

    @ledgered_transaction("government_receipt", "counterpart:government_receipts")
    def gov_in(self, amount):
        self.treasury += amount
        self.rev_week += amount

    def workplaces(self):
        return [self.hall] + self.businesses

    def employment_stats(self):
        counts = {
            "full_time": 0, "part_time": 0, "informal": 0,
            "self_employed": 0, "unemployed": 0,
        }
        for citizen in self.citizens:
            if citizen.job is not None:
                hours = getattr(citizen.job, "work_hours", 40.0)
                counts["full_time" if hours >= 35 else "part_time"] += 1
            elif citizen.business is not None:
                counts["self_employed"] += 1
            else:
                last_gig_day = getattr(citizen, "last_gig_day", -1)
                days_since_gig = self.day - last_gig_day
                if last_gig_day >= 0 and 0 <= days_since_gig < 7:
                    counts["informal"] += 1
                else:
                    counts["unemployed"] += 1
        return counts

    def _record_trade_contract(self, buyer, seller, product, quantity, unit_price,
                               quality=1.0, tax_amount=0.0):
        if quantity <= 0:
            return None
        gross_amount = quantity * unit_price + tax_amount
        if not all(math.isfinite(value) and value >= 0 for value in (
                quantity, unit_price, quality, tax_amount, gross_amount)):
            raise ValueError("Nilai kontrak perdagangan harus terbatas dan nonnegatif.")

        def party_id(party):
            if isinstance(party, Citizen):
                return f"citizen:{party.id}"
            if isinstance(party, Business):
                return f"business:{party.ledger_id}"
            return str(party)

        contract = {
            "id": self.next_trade_id,
            "day": self.day,
            "buyer": party_id(buyer),
            "seller": party_id(seller),
            "product": str(product),
            "quantity": float(quantity),
            "unit_price": float(unit_price),
            "quality": float(quality),
            "tax_amount": float(tax_amount),
            "gross_amount": float(gross_amount),
            "status": "settled",
        }
        self.trade_contracts.append(contract)
        self.next_trade_id += 1
        record_trade_interaction(self, buyer, seller, contract)
        return contract

    @ledgered_transaction(
        "cooperative_trade_settlement",
        "counterpart:cooperative_trade",
        business_selector=_cooperation_business_scope,
    )
    def _settle_cooperation_trade(self, offer_id):
        state = ensure_social_state(self)
        offer = state["offers"].get(str(offer_id))
        if offer is None or offer["status"] != "pending":
            return None
        buyer = next(
            (item for item in self.businesses
             if item.ledger_id == offer["buyer_business_id"]),
            None,
        )
        seller = next(
            (item for item in self.businesses
             if item.ledger_id == offer["seller_business_id"]),
            None,
        )
        quantity = offer["quantity"]
        unit_price = offer["unit_price"]
        if (buyer is None or seller is None or buyer.kind != "shop"
                or seller.kind not in ("farm", "factory")
                or quantity <= 0 or unit_price <= 0
                or quantity > seller.stock
                or unit_price < seller.price * 0.8
                or unit_price > seller.price * 1.2):
            return None

        organization = None
        fee = 0.0
        organization_id = offer["organization_id"]
        if organization_id is not None:
            organization = state["organizations"].get(str(organization_id))
            if (organization is None or organization["status"] != "active"
                    or str(offer["buyer_id"]) not in organization["members"]
                    or str(offer["seller_id"]) not in organization["members"]):
                return None
            fee_rate = organization["rules"]["brokerage_fee_rate"]
            fee = quantity * unit_price * fee_rate
        goods_total = quantity * unit_price
        if buyer.cash < goods_total + fee:
            return None

        buyer.cash -= goods_total + fee
        buyer.exp += goods_total + fee
        seller.cash += goods_total
        seller.rev += goods_total
        seller.stock -= quantity
        seller.demand_today += quantity
        seller.sold_today += quantity
        new_stock = buyer.stock + quantity
        buyer.cost_avg = (
            buyer.stock * buyer.cost_avg + goods_total
        ) / new_stock
        buyer.stock = new_stock
        contract = self._record_trade_contract(
            buyer, seller, seller.market_product, quantity, unit_price
        )
        if organization is not None:
            organization["fund"] += fee
            organization["undistributed_profit"] += fee
            organization["trade_count"] = organization.get("trade_count", 0) + 1
            organization["reputation"] = min(
                1.0, organization["reputation"] + 0.001
            )
            contract["organization_id"] = organization["id"]
            contract["cooperation_fee"] = fee
        return contract

    @ledgered_transaction(
        "organization_formation",
        "counterpart:organization_contributions",
        business_selector=_organization_business_scope,
    )
    def activate_social_organization(self, organization_id):
        organization = ensure_social_state(self)["organizations"].get(
            str(organization_id)
        )
        if (organization is None or organization["status"] != "pending"
                or not all(
                    member["accepted"]
                    for member in organization["members"].values()
                )):
            return False
        contributions = []
        for member_id, member in organization["members"].items():
            business = next(
                (item for item in self.businesses
                 if item.ledger_id == member["business_id"]),
                None,
            )
            contribution = member["contribution"]
            if (business is None or not math.isfinite(contribution)
                    or contribution <= 0 or business.cash < contribution):
                return False
            contributions.append((member_id, member, business, contribution))
        total = sum(item[3] for item in contributions)
        if not math.isfinite(total) or total <= 0:
            return False
        for _, member, business, contribution in contributions:
            business.cash -= contribution
            member["share"] = contribution / total
        organization["fund"] = total
        organization["contributed_capital"] = total
        organization["status"] = "active"
        organization["activated_day"] = self.day
        self.log(
            "info", f"{organization['name'].upper()} TERBENTUK",
            f"{len(contributions)} usaha menyetor {rp(total)}",
        )
        return True

    @ledgered_transaction(
        "organization_monthly_settlement",
        "counterpart:organization_operations",
        include_all=True,
    )
    def settle_social_organizations(self):
        for organization in ensure_social_state(self)["organizations"].values():
            if organization["status"] != "active":
                continue
            members = organization["members"]
            rules = organization["rules"]
            maintenance = (
                rules["monthly_maintenance_per_member"] * len(members)
            )
            if organization["fund"] >= maintenance:
                organization["fund"] -= maintenance
                organization["maintenance_failures"] = 0
                organization["reputation"] = min(
                    1.0, organization["reputation"] + 0.005
                )
            else:
                organization["maintenance_failures"] += 1
                organization["reputation"] = max(
                    0.0, organization["reputation"] - 0.05
                )
                if organization["maintenance_failures"] >= 2:
                    self._dissolve_social_organization(organization)
                    continue

            reserve = max(
                maintenance * rules["reserve_months"],
                organization["contributed_capital"] * 0.5,
            )
            distributable = min(
                organization["undistributed_profit"],
                max(0.0, organization["fund"] - reserve),
            )
            distribution = distributable * rules["profit_share_rate"]
            if distribution > 0:
                for member_id, member in members.items():
                    payout = distribution * member["share"]
                    business = next(
                        (item for item in self.businesses
                         if item.ledger_id == member["business_id"]),
                        None,
                    )
                    citizen = next(
                        (item for item in self.citizens
                         if str(item.id) == member_id),
                        None,
                    )
                    if business is not None:
                        business.cash += payout
                        business.rev += payout
                    elif citizen is not None:
                        citizen.cash += payout
                organization["fund"] -= distribution
                organization["undistributed_profit"] -= distribution
            organization["last_settlement_day"] = self.day
        return True

    def _dissolve_social_organization(self, organization):
        fund = organization["fund"]
        members = list(organization["members"].items())
        remaining_fund = fund
        for index, (member_id, member) in enumerate(members):
            payout = (
                remaining_fund if index == len(members) - 1
                else fund * member["share"]
            )
            business = next(
                (item for item in self.businesses
                 if item.ledger_id == member["business_id"]),
                None,
            )
            citizen = next(
                (item for item in self.citizens
                 if str(item.id) == member_id),
                None,
            )
            if business is not None:
                business.cash += payout
            elif citizen is not None:
                citizen.cash += payout
            member["share"] = 0.0
            remaining_fund -= payout
        if remaining_fund > 0 and not members:
            founder = next(
                (item for item in self.citizens
                 if item.id == organization["founder_id"]),
                None,
            )
            if founder is not None:
                founder.cash += remaining_fund
        organization["fund"] = 0.0
        organization["undistributed_profit"] = 0.0
        organization["status"] = "dissolved"
        organization["dissolved_day"] = self.day
        self.log(
            "bad", f"{organization['name'].upper()} DIBUBARKAN",
            "Dana dikembalikan sesuai porsi anggota.",
        )

    @ledgered_transaction(
        "organization_member_exit",
        "counterpart:organization_exit",
        include_all=True,
    )
    def leave_social_organization(self, citizen, organization_id):
        if citizen not in self.citizens:
            raise ValueError("Anggota organisasi tidak ditemukan.")
        organization = ensure_social_state(self)["organizations"].get(
            str(organization_id)
        )
        member_id = str(citizen.id)
        if (organization is None or organization["status"] != "active"
                or member_id not in organization["members"]):
            return False
        member = organization["members"].pop(member_id)
        payout = organization["fund"] * member["share"]
        business = next(
            (item for item in self.businesses
             if item.ledger_id == member["business_id"]),
            None,
        )
        if business is not None:
            business.cash += payout
        else:
            citizen.cash += payout
        organization["fund"] -= payout
        organization["undistributed_profit"] *= max(
            0.0, 1.0 - member["share"]
        )
        remaining_share = sum(
            item["share"] for item in organization["members"].values()
        )
        if len(organization["members"]) < 2:
            for remaining in organization["members"].values():
                remaining["share"] = 1.0
            self._dissolve_social_organization(organization)
        elif remaining_share > 0:
            for remaining in organization["members"].values():
                remaining["share"] /= remaining_share
        return payout

    def social_relationship(self, source, target):
        return relationship(self, source, target)

    def social_reputation(self, citizen):
        return reputation(self, citizen)

    def record_social_interaction(
            self, actor, other, kind, success=None, outcome=""):
        return record_interaction(
            self, actor, other, kind, success, outcome
        )

    def end_social_relationship(self, actor, other):
        return end_relationship(self, actor, other)

    def observe_social_action(
            self, observer, actor, action, values, context=None):
        return observe_action(
            self, observer, actor, action, values, context
        )

    def share_social_knowledge(self, sender, receiver, observation_id):
        return share_knowledge(self, sender, receiver, observation_id)

    def propose_cooperative_trade(
            self, buyer, seller, quantity, unit_price, organization_id=None):
        return propose_trade_cooperation(
            self, buyer, seller, quantity, unit_price, organization_id
        )

    def respond_cooperative_trade(
            self, citizen, offer_id, decision, quantity=None, unit_price=None):
        return respond_trade_offer(
            self, citizen, offer_id, decision, quantity, unit_price
        )

    def propose_social_organization(
            self, founder, invitees, name, contribution):
        return propose_organization(
            self, founder, invitees, name, contribution
        )

    def respond_social_invitation(self, citizen, organization_id, accept):
        return respond_organization_invitation(
            self, citizen, organization_id, accept
        )

    def propose_organization_rule(self, citizen, organization_id, rule, value):
        return propose_organization_rule(
            self, citizen, organization_id, rule, value
        )

    def vote_organization_rule(
            self, citizen, organization_id, proposal_id, approve):
        return vote_organization_rule(
            self, citizen, organization_id, proposal_id, approve
        )

    @ledgered_transaction("production_input_purchase",
                          "counterpart:external_input_supplier",
                          business_selector=_one_business_scope)
    def buy_production_inputs(self, business, commodity, amount):
        if business not in self.businesses or commodity not in INPUT_PRICES:
            return 0.0
        try:
            amount = float(amount)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Jumlah input produksi harus berupa angka terbatas.") from None
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Jumlah input produksi harus berupa angka terbatas.")
        if amount <= 1e-9:
            return 0.0

        unit_price = INPUT_PRICES[commodity]
        available = max(0.0, self.import_supply_remaining.get(commodity, 0.0))
        affordable = max(0.0, business.cash) / unit_price
        quantity = min(amount, available, affordable)
        if quantity <= 1e-9:
            return 0.0
        cost = quantity * unit_price
        previous_quantity = business.input_inventory.get(commodity, 0.0)
        previous_cost = business.input_costs.get(commodity, unit_price)
        total_quantity = previous_quantity + quantity
        business.input_costs[commodity] = (
            previous_quantity * previous_cost + cost
        ) / total_quantity
        business.input_inventory[commodity] = total_quantity
        business.cash -= cost
        self.import_supply_remaining[commodity] = available - quantity
        self._record_trade_contract(
            business, f"external_supplier:{commodity}", commodity,
            quantity, unit_price,
        )
        return quantity

    def avg_price(self):
        ps = [s.price for s in self.businesses if s.kind == "shop"]
        return sum(ps) / len(ps) if ps else 0.0

    def labor_force(self):
        return [c for c in self.citizens if c.age < RETIRE_AGE]

    def unemployment(self):
        lf = self.labor_force()
        if not lf:
            return 0.0
        return sum(1 for c in lf if c.job is None and c.business is None) / len(lf)

    def employment_rate(self):
        return 1 - self.unemployment()

    @property
    def crime_rate(self):
        return sum(self.crime_history) / len(self.crime_history) if self.crime_history else 0.0

    # ---- waktu
    def advance(self, hours):
        self.hour += hours
        while self.hour >= HPD:
            self.hour -= HPD
            self.day += 1
            self.daily()

    @property
    def year(self):
        return self.day // DPY + 1

    # ---- warga masuk / keluar
    def add_citizen(self, young=False, child=False):
        c = Citizen(self, self.next_id, young, child)
        self.next_id += 1
        self.citizens.append(c)
        return c

    @ledgered_transaction(
        "birth_settlement",
        "counterpart:birth_medical_services",
        include_all=True,
        track_world_collections=True,
    )
    def birth_child(self, parent_a, parent_b):
        if (parent_a not in self.citizens or parent_b not in self.citizens
                or parent_a is parent_b or not is_adult(parent_a)
                or not is_adult(parent_b)
                or active_partner(self, parent_a) is not parent_b):
            return None
        birthing_parent = next(
            (
                parent for parent in (parent_a, parent_b)
                if parent.female and 20.0 <= parent.age <= 40.0
            ),
            None,
        )
        if (birthing_parent is None or parent_a.home is None
                or parent_a.home is not parent_b.home
                or parent_a.home.free <= 0):
            return None
        dependent_ids = {
            child.id for child in children_of(self, parent_a)
            if child.age < 18.0
        }
        if (len(dependent_ids) >= 2 or len(self.citizens) >= self.max_population
                or parent_a.health < 50.0 or parent_b.health < 50.0
                or min(parent_a.happy, parent_b.happy) < 40.0):
            return None
        birth_cost = 250_000.0
        if parent_a.cash + parent_a.savings + parent_b.cash + parent_b.savings < birth_cost:
            return None
        remaining_cost = birth_cost
        for parent in sorted(
                (parent_a, parent_b),
                key=lambda item: item.cash + item.savings,
                reverse=True):
            contribution = min(
                remaining_cost, parent.cash + parent.savings
            )
            if contribution and not self.pay_from(parent, contribution):
                raise RuntimeError("Biaya kelahiran berubah saat penyelesaian.")
            parent.exp_acc += contribution
            remaining_cost -= contribution
        if remaining_cost > 0.01:
            raise RuntimeError("Biaya kelahiran tidak terbayar penuh.")

        child = self.add_citizen(child=True)
        child.skill = min(
            0.2,
            (parent_a.skill + parent_b.skill) * 0.1
            + self.rng.uniform(0.01, 0.08),
        )
        child.learning = 0.02
        self.move_in(child, parent_a.home)
        register_birth(self, (parent_a, parent_b), child)
        self.log(
            "good", f"{child.first.upper()} LAHIR",
            f"Anak dari {parent_a.first} dan {parent_b.first}",
        )
        return child

    def propose_partnership(self, proposer, recipient):
        return propose_partnership(self, proposer, recipient)

    def respond_partnership(self, recipient, proposal_id, accept):
        return respond_partnership(self, recipient, proposal_id, accept)

    def family_partner(self, citizen):
        return active_partner(self, citizen)

    def family_parents(self, child):
        return parents_of(self, child)

    def family_children(self, parent):
        return children_of(self, parent)

    def family_siblings(self, citizen):
        return siblings_of(self, citizen)

    def family_guardians(self, child):
        return guardians_of(self, child)

    def appoint_family_guardian(self, child, guardian):
        return appoint_guardian(self, child, guardian)

    def teach_family_knowledge(
            self, teacher, child, observation_id, method="teaching"):
        return teach_knowledge(
            self, teacher, child, observation_id, method
        )

    @ledgered_transaction("estate_settlement", "counterpart:estate_settlement",
                          include_all=True, track_world_collections=True)
    def remove_citizen(self, c, inherit=True, cause="meninggal"):
        if (c not in self.citizens
                or not is_adult(c) and cause == "pindah"):
            return False
        heirs = family_heirs(self, c) if inherit else []
        heir = heirs[0] if heirs else None
        if cause == "pindah":
            handle_departure(self, c)
        else:
            handle_death(self, c)
        for organization in list(
                ensure_social_state(self)["organizations"].values()):
            if str(c.id) in organization["members"]:
                if organization["status"] == "active":
                    self.leave_social_organization(c, organization["id"])
                elif organization["status"] == "pending":
                    organization["status"] = "cancelled"
        for offer in ensure_social_state(self)["offers"].values():
            if (offer["status"] == "pending"
                    and c.id in (offer["sender_id"], offer["recipient_id"])):
                offer["status"] = "cancelled"
        c.dead = True
        if c.home:
            c.home.occupants.remove(c)
            c.home = None
        if c.job:
            c.job.workers.remove(c)
            c.job = None
        self.citizens.remove(c)
        if heir:
            for loan in list(c.loans):
                c.loans.remove(loan)
                loan.borrower = heir
                heir.loans.append(loan)
        else:
            for loan in list(c.loans):
                self.default_loan(loan)
        if heir:
            heir.cash += c.cash
            heir.savings += c.savings
            for s, h in c.hold.items():
                if s in heir.hold:
                    u = heir.hold[s][0] + h[0]
                    heir.hold[s] = [u, (heir.hold[s][0] * heir.hold[s][1] + h[0] * h[1]) / u]
                else:
                    heir.hold[s] = h
            for h in c.houses:
                h.owner = heir
                heir.houses.append(h)
            if c.business:
                b = c.business
                if heir.business is None:
                    b.owner = heir
                    heir.business = b
                    if heir.job:
                        heir.job.workers.remove(heir)
                        heir.job = None
                    if b.loan:
                        b.loan.borrower = heir
                        if b.loan not in heir.loans:
                            heir.loans.append(b.loan)
                    c.business = None
                else:
                    self.close_business(b, quiet=True)
        else:
            self.bank.deposits -= c.savings
            self.bank.equity += c.savings
            for h in c.houses:
                h.owner = None
            if c.business:
                self.close_business(c.business, quiet=True)
        if cause != "pindah":
            self.log("info", f"{c.first.upper()} {cause.upper()}", f"Umur {int(c.age)}")
        return True

    # ---- bank
    @ledgered_transaction("deposit", "counterpart:deposit_accrual")
    def deposit(self, c, amt):
        amt = max(0.0, min(amt, c.cash))
        c.cash -= amt
        c.savings += amt
        self.bank.cash += amt
        self.bank.deposits += amt

    @ledgered_transaction("withdrawal", "counterpart:withdrawal_accrual")
    def withdraw(self, c, amt):
        amt = max(0.0, min(amt, c.savings))
        c.savings -= amt
        self.bank.cash -= amt
        self.bank.deposits -= amt
        c.cash += amt
        return amt

    @ledgered_transaction("payment", "counterpart:payment_settlement")
    def pay_from(self, c, amt):
        """Bayar dari tunai lalu tabungan. Semua atau tidak sama sekali."""
        if c not in self.citizens:
            raise ValueError("Warga pembayar tidak ditemukan.")
        try:
            amt = float(amt)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Nominal pembayaran harus berupa angka terbatas.") from None
        if not math.isfinite(amt) or amt < 0:
            raise ValueError("Nominal pembayaran harus nonnegatif dan terbatas.")
        if amt == 0:
            return True

        values = (c.cash, c.savings, self.bank.cash, self.bank.deposits, c.exp_acc)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Saldo pembayaran tidak valid.")
        available_cash = max(0.0, c.cash)
        available_savings = max(0.0, c.savings)
        available = available_cash + available_savings
        if not math.isfinite(available):
            raise ValueError("Total dana pembayaran tidak valid.")
        if available < amt:
            return False
        take = min(available_cash, amt)
        rest = amt - take
        next_cash = c.cash - take
        next_savings = c.savings - rest
        next_bank_cash = self.bank.cash - rest
        next_deposits = self.bank.deposits - rest
        next_exp_acc = c.exp_acc + amt
        if not all(math.isfinite(value) for value in (
                next_cash, next_savings, next_bank_cash, next_deposits,
                next_exp_acc)):
            raise ValueError("Hasil pembayaran tidak valid.")
        c.cash = next_cash
        c.savings = next_savings
        self.bank.cash = next_bank_cash
        self.bank.deposits = next_deposits
        c.exp_acc = next_exp_acc
        return True

    def credit_ok(self, c, amount, months, kind, rate):
        b = self.bank
        if (c not in self.citizens or not is_adult(c)
                or not math.isfinite(amount) or amount <= 0
                or not math.isfinite(rate) or rate < 0
                or not math.isfinite(months) or months <= 0):
            return False
        if kind == "personal" and amount > self.unsecured_limit(c):
            return False
        if kind in ("biz", "mortgage", "vehicle") and amount > SECURED_LOAN_MAX:
            return False
        if self.day < c.credit_block:
            return False
        if b.equity <= 0 or b.equity < 0.08 * (b.loan_book + amount):
            return False
        if b.cash - amount < max(0.1 * b.deposits, 0.05 * b.equity):
            return False
        pay = annuity(amount, rate, months)
        nw = c.networth
        if kind == "biz":
            if len(self.businesses) < KUR_LIMIT and c.entre > 0.3:
                return pay <= max(1_000_000, 0.35 * c.income_est())
            return pay <= 0.35 * c.income_est() and nw >= 0.12 * amount
        if kind == "personal":
            return pay <= 0.35 * c.income_est() and c.credit_score >= 500
        return pay <= 0.35 * c.income_est() and nw >= 0.1 * amount and c.credit_score >= 500

    def unsecured_limit(self, c):
        credit = max(0.0, min(1.0, (c.credit_score - 300.0) / 550.0))
        confidence = 0.50 * c.persuasion + 0.30 * c.skill + 0.20 * credit
        return UNSECURED_LOAN_MIN + (UNSECURED_LOAN_MAX - UNSECURED_LOAN_MIN) * confidence

    def apply_personal_loan(self, c, amount, months=12):
        """Ajukan pinjaman tanpa agunan dengan plafon berbasis karakter dan riwayat kredit."""
        if c not in self.citizens or not is_adult(c):
            return None
        amount = float(amount)
        if not self.credit_ok(c, amount, months, "personal", self.policy.loan_rate):
            return None
        return self.make_loan(c, amount, self.policy.loan_rate, months, "personal")

    @ledgered_transaction("loan_disbursement", "counterpart:loan_settlement",
                          track_world_collections=True)
    def make_loan(self, c, amount, rate, months, kind, ref=None):
        if (c not in self.citizens or not is_adult(c)
                or not math.isfinite(amount) or amount <= 0
                or not math.isfinite(rate) or rate < 0
                or not math.isfinite(months) or months <= 0
                or self.bank.cash < amount):
            raise ValueError("Data pinjaman tidak valid atau kas bank tidak mencukupi.")
        if kind == "personal" and amount > self.unsecured_limit(c):
            raise ValueError("Pinjaman tanpa agunan melebihi plafon warga.")
        if kind in ("biz", "mortgage", "vehicle") and amount > SECURED_LOAN_MAX:
            raise ValueError("Pinjaman beragunan melebihi batas Rp50 juta.")
        l = Loan(c, amount, rate, months, kind, ref)
        self.bank.cash -= amount
        self.bank.loan_book += amount
        c.cash += amount
        c.loans.append(l)
        self.loans.append(l)
        return l

    def end_loan(self, l):
        if l in l.borrower.loans:
            l.borrower.loans.remove(l)
        if l in self.loans:
            self.loans.remove(l)

    def loan_due(self, l):
        interest = l.balance * l.rate
        return min(l.pay, l.balance + interest), interest

    @ledgered_transaction("loan_repayment", "counterpart:loan_interest")
    def loan_paid(self, l, pay, interest):
        self.bank.cash += pay
        self.bank.profit += interest
        self.bank.equity += interest
        l.borrower.credit_score = min(850.0, l.borrower.credit_score + 1.5)
        principal = min(l.balance, max(0.0, pay - interest))
        l.balance -= principal
        self.bank.loan_book -= principal
        l.months -= 1
        l.missed = 0
        if l.balance < 1 or l.months <= 0:
            self.bank.loss += max(0.0, l.balance)
            self.bank.loan_book -= max(0.0, l.balance)
            self.bank.equity -= max(0.0, l.balance)
            self.end_loan(l)

    @ledgered_transaction("loan_default", "counterpart:loan_writeoff",
                          include_all=True, track_world_collections=True)
    def default_loan(self, l):
        c = l.borrower
        recovery = 0.0
        if l.kind == "mortgage" and l.ref in self.houses:
            h = l.ref
            recovery = min(l.balance, h.value * 0.7)
            h.bank_owned = True
            h.bank_value = recovery
            self.bank.repossessed_assets += recovery
        elif l.kind == "vehicle":
            recovery = min(l.balance, c.vehicle_value * 0.65)
            self.bank.repossessed_assets += recovery
        elif l.kind == "biz" and l.ref in self.businesses:
            recovery = min(l.balance, l.ref.asset_value * 0.65)
            self.bank.repossessed_assets += recovery
            l.ref.loan = None
        loss = max(0.0, l.balance - recovery)
        self.bank.loss += loss
        self.bank.loan_book -= l.balance
        self.bank.equity -= loss
        self.end_loan(l)
        c.credit_block = self.day + DPY
        c.credit_score = max(300.0, c.credit_score - 140)
        if l.kind == "mortgage":
            h = l.ref
            h.owner = None
            if h in c.houses:
                c.houses.remove(h)
            self.log("bad", f"{c.first.upper()} GAGAL BAYAR KPR", "Rumah disita bank")
        elif l.kind == "biz" and l.ref in self.businesses:
            self.close_business(l.ref, "gagal bayar kredit", seized=True)
        elif l.kind == "vehicle":
            c.vehicle_value = 0.0
            c.vehicle_color = None
            self.log("bad", f"{c.first.upper()} MOBILNYA DITARIK", "Gagal membayar kredit kendaraan")

    # ---- usaha
    @ledgered_transaction("business_startup", "counterpart:business_startup_assets",
                          include_businesses=True, track_world_collections=True)
    def found_business(self, c, kind, force=False):
        lots = [l for l in self.lots if l.kind == "biz" and l.building is None
                and l.land_owner is None]
        if not is_adult(c) or not lots or c.business or kind not in STARTUP:
            return False
        p = self.policy
        cost = self.lot_price + STARTUP[kind]
        own = min(0.8 * (c.cash + c.savings), cost * 0.7)
        need = cost - own
        if need > SECURED_LOAN_MAX:
            return False
        kur = len(self.businesses) < KUR_LIMIT
        rate = p.loan_rate * (0.4 if kur else 1.0)
        months = 60 if kur else 48
        if need > 1:
            if not force and not self.credit_ok(c, need, months, "biz", rate):
                return False
            if self.bank.cash - need < 0:
                return False
        first = len(self.businesses) == 0
        if need > 1:
            loan = self.make_loan(c, need, rate, months, "biz")
        if not self.pay_from(c, cost):
            if need > 1:
                self.end_loan(loan)
                self.bank.cash += need
                self.bank.loan_book -= need
                c.cash -= need
            return False
        if c.job:
            c.job.workers.remove(c)
            c.job = None
        lot = self.rng.choice(lots)
        lot.land_owner = None
        b = Business(self, kind, lot, c, STARTUP[kind])
        b.initialize_startup_inventory(STARTUP[kind])
        c.business = b
        self.businesses.append(b)
        self.gov_in(self.lot_price)
        if need > 1:
            b.loan = loan
            loan.ref = b
        word = {"factory": "PABRIK", "farm": "KEBUN", "shop": "TOKO",
                "showroom": "SHOWROOM", "car_factory": "PABRIK MOBIL",
                "builder": "INDUSTRI BANGUNAN", "repair": "JASA SERVIS",
                "delivery": "JASA ANTAR", "cleaning": "JASA KEBERSIHAN"}[kind]
        if first:
            self.log("good", "BISNIS PERTAMA DI KOTA DIBUKA", f"{c.name} membuka {word.lower()}")
        else:
            self.log("good", f"{c.first.upper()} MEMBUKA {word}", f"Modal {rp(cost)}")
        c.think(f"Buka {word.lower()} sendiri, semoga untung.")
        c.learn(0.02, financial=True)
        return True

    @ledgered_transaction("land_purchase", "counterpart:land_transfer")
    def buy_land(self, c, lot=None):
        """Beli lahan kosong dari pemerintah; biaya lahan masuk ke kas pemerintah."""
        if c not in self.citizens or not is_adult(c):
            return None
        available = [item for item in self.lots if item.kind == "biz"
                     and item.building is None and item.land_owner is None]
        if lot is None:
            if not available:
                return None
            lot = min(available, key=lambda item: item.rect[2] * item.rect[3])
        if lot not in available or not self.pay_from(c, self.lot_price):
            return None
        lot.land_owner = c
        self.gov_in(self.lot_price)
        c.think(f"Membeli lahan dari pemerintah seharga {rp(self.lot_price)}.")
        self.log("info", f"{c.first.upper()} MEMBELI LAHAN", f"Harga {rp(self.lot_price)} masuk ke kas kota")
        return lot

    @ledgered_transaction("house_construction", "counterpart:construction_inputs",
                          include_businesses=True, track_world_collections=True)
    def build_house(self, c, lot=None):
        """Bangun rumah di lahan milik warga lewat perusahaan kontraktor."""
        if c not in self.citizens or not is_adult(c):
            return None
        owned = [item for item in self.lots if item.land_owner is c
                 and item.building is None and item.kind == "biz"]
        if lot is None:
            lot = owned[0] if owned else None
        builders = [business for business in self.businesses
                    if business.market_product == "construction"
                    and business.service_inventory.get("construction", 0.0) >= 1.0]
        if lot not in owned or not builders:
            return None
        builder = min(builders, key=lambda business: business.price)
        contract_price = builder.price
        if self.buy_service(c, "construction", 1.0, seller=builder) < 1.0 - 1e-9:
            return None
        home = House(self, lot)
        home.base_structure_value = contract_price
        home.owner = c
        lot.kind = "house"
        lot.building = home
        lot.land_owner = None
        self.houses.append(home)
        c.houses.append(home)
        if c.home is None and home.free > 0:
            self.move_in(c, home)
        c.think(f"Membangun rumah di lahan sendiri dengan kontraktor seharga {rp(BUILD_COST)}.")
        self.log("good", "RUMAH BARU DIBANGUN",
                 f"{c.first} · biaya bangunan {rp(contract_price)}")
        return home

    @ledgered_transaction("service_contract_settlement",
                          "counterpart:service_trade",
                          business_selector=_all_business_scope)
    def buy_service(self, c, product, quantity, max_unit_price=None, seller=None):
        if c not in self.citizens:
            return 0.0
        try:
            quantity = float(quantity)
            maximum = (
                float(max_unit_price)
                if max_unit_price is not None else math.inf
            )
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Jumlah atau harga jasa tidak valid.") from None
        if (not math.isfinite(quantity) or quantity < 0
                or (not math.isfinite(maximum) and maximum != math.inf)
                or maximum < 0):
            raise ValueError("Jumlah atau harga jasa tidak valid.")
        if quantity <= 1e-9:
            return 0.0

        providers = [
            business for business in self.businesses
            if (business.market_product == product
                and business.service_inventory.get(product, 0.0) > 1e-9
                and (seller is None or business is seller)
                and 0 < business.price <= maximum)
        ]
        providers.sort(key=lambda business: (
            business.price / max(0.5, min(1.5, business.quality)),
            -business.service_inventory.get(product, 0.0),
        ))
        if not providers:
            return 0.0
        if not math.isfinite(c.cash) or not math.isfinite(c.savings):
            raise ValueError("Saldo dana warga tidak valid.")
        available_funds = max(0.0, c.cash) + max(0.0, c.savings)
        if not math.isfinite(available_funds):
            raise ValueError("Dana pembelian jasa tidak valid.")
        if seller is not None and (
                seller.service_inventory.get(product, 0.0) < quantity
                or available_funds
                < quantity * seller.price * (1 + self.policy.tax_ppn)):
            return 0.0
        remaining = quantity
        completed = 0.0
        for provider in providers:
            available = provider.service_inventory.get(product, 0.0)
            gross_unit_price = provider.price * (1 + self.policy.tax_ppn)
            available_funds = max(0.0, c.cash) + max(0.0, c.savings)
            if not math.isfinite(available_funds):
                raise ValueError("Dana pembelian jasa tidak valid.")
            affordable = available_funds / gross_unit_price
            traded = min(remaining, available, affordable)
            if traded <= 1e-9:
                continue
            net = traded * provider.price
            tax = net * self.policy.tax_ppn
            gross = net + tax
            if not self.pay_from(c, gross):
                continue
            provider.service_inventory[product] = available - traded
            if provider.service_inventory[product] <= 1e-9:
                provider.service_inventory.pop(product, None)
                provider.service_costs.pop(product, None)
            provider.cash += net
            provider.rev += net
            provider.demand_today += traded
            provider.sold_today += traded
            if tax:
                self.gov_in(tax)
            self.sales_today += gross
            self._record_trade_contract(
                c, provider, product, traded, provider.price, provider.quality,
                tax,
            )
            remaining -= traded
            completed += traded
            if remaining <= 1e-9:
                break
        return completed

    @ledgered_transaction("house_purchase", "counterpart:house_transfer",
                          track_world_collections=True)
    def buy_house(self, c, house):
        """Beli rumah dari pemilik saat ini atau pemerintah dengan uang tunai/KPR."""
        if (c not in self.citizens or not is_adult(c)
                or house not in self.houses or house.bank_owned
                or house.owner is c):
            return False
        price = house.value
        fee = price * 0.01
        liquid = c.cash + c.savings
        down = min(price, max(price * 0.2, price - SECURED_LOAN_MAX, liquid - fee))
        loan_amount = price - down
        seller = house.owner
        seller_loans = [loan for loan in self.loans
                        if loan.kind == "mortgage" and loan.ref is house]
        payoff = sum(loan.balance for loan in seller_loans)
        if price < payoff:
            return False
        if liquid < down + fee:
            return False
        mortgage = None
        if loan_amount > 1:
            if not self.credit_ok(c, loan_amount, 240, "mortgage", self.policy.loan_rate):
                return False
            mortgage = self.make_loan(c, loan_amount, self.policy.loan_rate, 240, "mortgage", house)
        if not self.pay_from(c, price + fee):
            if mortgage:
                self.end_loan(mortgage)
                self.bank.cash += loan_amount
                self.bank.loan_book -= loan_amount
                c.cash -= loan_amount
            return False
        should_move = c.home is None or (c.home.owner is not c and not c.houses)
        if seller:
            seller.cash += price - payoff
            for seller_loan in seller_loans:
                self.bank.cash += seller_loan.balance
                self.bank.loan_book -= seller_loan.balance
                self.end_loan(seller_loan)
            if house in seller.houses:
                seller.houses.remove(house)
            if seller.home is house:
                house.occupants.remove(seller)
                seller.home = None
        else:
            self.gov_in(price)
        self.gov_in(fee)
        house.owner = c
        c.houses.append(house)
        if mortgage:
            mortgage.ref = house
        if should_move and c.home is not None:
            c.home.occupants.remove(c)
            c.home = None
        if should_move and house.free > 0:
            self.move_in(c, house)
        c.think(f"Membeli rumah dari {seller.first if seller else 'pemerintah'} seharga {rp(price)}.")
        self.log("info", f"{c.first.upper()} MEMBELI RUMAH", f"Harga {rp(price)} · pajak transaksi {rp(fee)}")
        return True

    @ledgered_transaction("business_closure", "counterpart:business_liquidation",
                          track_world_collections=True)
    def close_business(self, b, reason="", quiet=False, seized=False):
        debt = b.loan.balance if b.loan else b.owner.debt
        for w in list(b.workers):
            w.job = None
            w.unemp_days = 0
        b.workers.clear()
        if b.loan:
            recovery = min(b.loan.balance, max(0.0, b.asset_value * 0.65))
            loss = max(0.0, b.loan.balance - recovery)
            self.bank.repossessed_assets += recovery
            self.bank.loss += loss
            self.bank.loan_book -= b.loan.balance
            self.bank.equity -= loss
            self.end_loan(b.loan)
            b.loan = None
            seized = True
        o = b.owner
        o.business = None
        if not seized:
            o.cash += max(0.0, b.cash + b.inventory_value + b.equipment_value * 0.5)
            self.gov_in(max(0.0, b.land_value * 0.8))
        b.lot.land_owner = None
        b.lot.building = None
        if b in self.businesses:
            self.businesses.remove(b)
        if not quiet:
            self.log("bad", f"{o.first.upper()} BANGKRUT", f"Umur {int(o.age)} · utang {rp(debt)} · {b.name} tutup")
            o.think("Usahaku bangkrut. Harus cari kerja lagi.")

    # ---- pasar finansial untuk warga
    def _record_asset_trade(self, citizen, symbol, next_cash, next_units,
                            average_price, tax, category):
        ledger = getattr(self, "ledger", None)
        if ledger is None:
            return
        citizen_id = f"citizen:{citizen.id}"
        before = self._ledger_snapshot({citizen.id}, set())
        after = dict(before)
        after[f"{citizen_id}:cash"] = (next_cash, "debit")
        investment_account = f"{citizen_id}:investment:{symbol}"
        if next_units <= 1e-9:
            after.pop(investment_account, None)
        else:
            after[investment_account] = (
                next_units * average_price, "debit"
            )
        after["government:cash"] = (self.treasury + tax, "debit")
        ledger.record_snapshot_change(
            self.day, category, category, before, after,
            "counterpart:market_clearing",
        )

    def buy_asset(self, c, sym, amount):
        if c not in self.citizens:
            raise ValueError("Warga pembeli tidak ditemukan.")
        if not is_adult(c):
            raise ValueError("Warga harus dewasa untuk membeli aset.")
        if sym not in self.market.assets:
            raise ValueError(f"Aset {sym!r} tidak ditemukan.")
        try:
            amount = float(amount)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Nilai pembelian aset harus berupa angka terbatas.") from None
        if (not math.isfinite(amount) or amount < 0
                or not math.isfinite(c.cash) or c.cash < 0):
            raise ValueError("Nilai pembelian aset atau kas warga tidak valid.")

        a = self.market.assets[sym]
        amount = min(amount, c.cash)
        if amount < 50_000 or a.halted:
            return 0.0
        try:
            price = float(a.price)
            flow = float(a.flow)
            traded = float(a.traded)
            owned_units, average_price = map(
                float, c.hold.get(sym, (0.0, price))
            )
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Harga atau posisi aset tidak valid.") from None
        if (not math.isfinite(price) or price <= 0
                or not math.isfinite(flow) or not math.isfinite(traded)
                or not math.isfinite(owned_units) or owned_units < 0
                or not math.isfinite(average_price) or average_price <= 0):
            raise ValueError("Harga atau posisi aset tidak valid.")
        units = amount / price
        next_units = owned_units + units
        next_average_price = (
            (owned_units * average_price + amount) / next_units
        )
        next_cash = c.cash - amount
        next_flow = flow + amount
        next_traded = traded + amount
        if not all(math.isfinite(value) for value in (
                units, next_units, next_average_price, next_cash,
                next_flow, next_traded)):
            raise ValueError("Hasil pembelian aset tidak valid.")

        self._record_asset_trade(
            c, sym, next_cash, next_units, next_average_price, 0.0,
            "asset_purchase",
        )
        c.cash = next_cash
        c.hold[sym] = [next_units, next_average_price]
        a.flow = next_flow
        a.traded = next_traded
        c.memory.record(
            self.day, "investment", "purchase", {"asset": sym},
            "position opened", None, impact=0.1,
        )
        return amount

    def sell_asset(self, c, sym, frac=1.0):
        if c not in self.citizens:
            raise ValueError("Warga penjual tidak ditemukan.")
        if not is_adult(c):
            raise ValueError("Warga harus dewasa untuk menjual aset.")
        if sym not in self.market.assets:
            raise ValueError(f"Aset {sym!r} tidak ditemukan.")
        try:
            fraction = float(frac)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Fraksi penjualan harus berupa angka antara 0 dan 1.") from None
        if not math.isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("Fraksi penjualan harus berupa angka antara 0 dan 1.")

        h = c.hold.get(sym)
        if not h:
            return 0.0
        a = self.market.assets[sym]
        if a.halted:
            return 0.0
        try:
            owned_units, average_price = map(float, h)
            price = float(a.price)
            tax_rate = float(self.policy.tax_stock if a.kind == "stock"
                             else self.policy.tax_crypto)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Posisi atau harga aset tidak valid.") from None
        if (not math.isfinite(owned_units) or owned_units < 0
                or not math.isfinite(average_price) or average_price <= 0
                or not math.isfinite(price) or price <= 0
                or not math.isfinite(tax_rate) or not 0 <= tax_rate <= 1
                or not math.isfinite(c.cash) or not math.isfinite(self.treasury)
                or not math.isfinite(a.flow) or not math.isfinite(a.traded)):
            raise ValueError("Saldo atau data aset tidak valid untuk penjualan.")
        momentum = a.momentum() * 4 + a.change(10) * 2
        volatility = a.vol
        if not math.isfinite(momentum) or not math.isfinite(volatility):
            raise ValueError("Data pasar tidak valid untuk pengalaman investasi.")
        momentum = max(-1.0, min(1.0, momentum))
        units = min(owned_units, owned_units * fraction)
        if units <= 0:
            return 0.0
        remaining_units = max(0.0, owned_units - units)
        gross = units * price
        if not math.isfinite(gross):
            raise ValueError("Nilai penjualan aset tidak valid.")
        tax = gross * tax_rate
        proceeds = gross - tax
        next_cash = c.cash + proceeds
        next_treasury = self.treasury + tax
        next_flow = a.flow - gross
        next_traded = a.traded + gross
        next_rev_week = self.rev_week + tax
        if not all(math.isfinite(value) for value in (
                tax, proceeds, next_cash, next_treasury, next_flow,
                next_traded, next_rev_week)):
            raise ValueError("Saldo hasil penjualan aset tidak valid.")

        self._record_asset_trade(
            c, sym, next_cash, remaining_units, average_price, tax,
            "asset_sale",
        )

        c.cash = next_cash
        self.treasury = next_treasury
        self.rev_week += tax
        if remaining_units <= 1e-9:
            del c.hold[sym]
        else:
            c.hold[sym] = [remaining_units, average_price]
        a.flow = next_flow
        a.traded = next_traded
        realized_return = price * (1 - tax_rate) / average_price - 1
        value = max(-1.0, min(1.0, realized_return))
        episode = c.memory.record(
            self.day, "investment", "sale", {"asset": sym},
            f"realized return {value:+.1%}", value > 0,
            impact=min(1.0, abs(value)), value=value,
        )
        c.knowledge.observe(
            self.day,
            "personal_experience",
            f"investment-sale:{episode.source_ids[-1]}",
            {
                "market_momentum": momentum,
                "market_volatility": volatility,
                "realized_return": value,
            },
            context={"asset": sym},
        )
        return gross

    def perceive(self, c, a):
        prior = 0.08 if a.kind == "stock" else 0.10
        mom = max(-1.0, min(1.0, a.momentum() * 4 + a.change(10) * 2))
        noise = 0.12 * (1.0 - c.financial_literacy) + 0.015
        est = (1 - c.herd) * prior + c.herd * mom + (c.optimism - 0.5) * 0.25 + self.rng.gauss(0, noise)
        estimate = est - 0.5 * (1 - c.risk) * a.vol
        experience = c.memory.retrieve(
            domain="investment",
            action="sale",
            context={"asset": a.sym},
            current_day=self.day,
            limit=8,
        )
        if experience:
            observation_count = sum(item.source_count for item in experience)
            average_return = sum(
                item.mean_value * item.source_count for item in experience
            ) / observation_count
            confidence = min(1.0, observation_count / 3.0)
            estimate += max(
                -0.04, min(0.04, average_return * 0.08)
            ) * confidence
        estimate += c.knowledge.prediction_adjustment(
            "market_momentum",
            "realized_return",
            mom,
            context={"asset": a.sym},
            current_day=self.day,
        )
        return estimate

    def finance(self, c):
        """Keputusan keuangan mingguan: nabung, jual, atau beli aset."""
        if not is_adult(c):
            return
        r = self.rng
        p = self.policy
        est = max(c.est_exp, 1_500_000)
        reserve = est * (0.25 + 0.6 * c.frugal)
        if c.cash > reserve * 1.5:
            amt = (c.cash - reserve) * (0.3 + 0.6 * c.frugal)
            self.deposit(c, amt)
            if amt > est and r.random() < 0.3:
                c.think(f"Kelebihan uang, nabung {rp(amt)} di bank.")
        if c.cash < est * 0.15 and c.savings > 0:
            self.withdraw(c, min(c.savings, est * 0.3))
        liquid = c.cash + c.savings
        need_cash = liquid < est * 0.8
        for sym, h in list(c.hold.items()):
            a = self.market.assets[sym]
            pnl = a.price / h[1] - 1
            sc = self.perceive(c, a)
            why = None
            if need_cash and r.random() < 0.7:
                why = "butuh uang tunai"
            elif pnl < -(0.08 + 0.30 * c.risk) and r.random() < min(
                    1.0, 0.8 * (1 - 0.5 * c.patience) + 0.2 * c.fear):
                why = f"takut rugi makin dalam ({pnl * 100:.0f}%)"
            elif pnl > 0.15 + 0.6 * c.greed and r.random() < 0.5 * (1 - c.greed) + 0.1:
                why = f"ambil untung ({pnl * 100:+.0f}%)"
            elif sc < -0.1 and r.random() > c.patience:
                why = "prospeknya kelihatan jelek"
            if why:
                got = self.sell_asset(c, sym, 1.0 if r.random() < 0.7 else 0.5)
                c.think(f"Jual {sym} {rp(got)}: {why}.")
        liquid = c.cash + c.savings
        reserve_months = (1.5 + 4 * c.frugal - 1.2 * c.financial_literacy
                         + 1.5 * c.fear + c.depression)
        investable = liquid - est * reserve_months
        effective_risk = max(0.0, c.risk - 0.45 * c.fear - 0.3 * c.depression)
        if investable > est * (0.5 - 0.25 * c.financial_literacy) and r.random() < (
                0.15 + 0.5 * effective_risk + 0.2 * c.financial_literacy):
            best = None
            for a in self.market.assets.values():
                sc = self.perceive(c, a)
                if sc > p.deposit_rate * (1 - 0.5 * effective_risk) and (best is None or sc > best[0]):
                    best = (sc, a)
            if best:
                a = best[1]
                amt = investable * (0.15 + 0.6 * effective_risk) * r.uniform(0.4, 1)
                if c.cash < amt:
                    self.withdraw(c, amt - c.cash)
                spent = self.buy_asset(c, a.sym, amt)
                if spent:
                    mood = "lagi naik, takut ketinggalan" if a.momentum() > 0.03 else "kelihatan murah"
                    c.think(f"Beli {a.sym} {rp(spent)}: {mood}.")
                    c.learn(0.015, financial=True)
            elif r.random() < 0.15:
                c.think("Pasar kelihatan nggak menarik, mending simpan di bank.")

    def maybe_start_business(self, c):
        r = self.rng
        if (not is_adult(c) or c.business or c.age >= RETIRE_AGE
                or c.entre < 0.3):
            return
        lot_count = sum(
            lot.kind == "biz" and lot.building is None and lot.land_owner is None
            for lot in self.lots
        )
        if lot_count <= 0:
            return

        population = max(1, len(self.citizens))
        unbuilt_owned_lots = sum(
            lot.land_owner is not None and lot.building is None
            for lot in self.lots
        )
        worn_houses = sum(house.condition < 0.85 for house in self.houses)
        vehicle_demand = 0.0
        for citizen in self.citizens:
            if (citizen.vehicle_value or not citizen.home
                    or not (citizen.job or citizen.business)):
                continue
            price = CAR_PRICE * self.house_index
            liquid = citizen.cash + citizen.savings
            down = min(liquid * 0.5, price * 0.4)
            loan_amount = price - down
            if self.credit_ok(
                    citizen, loan_amount, 60, "vehicle",
                    self.policy.loan_rate + 0.03):
                vehicle_demand += 0.01
        demand = {
            "farm": population * 0.65,
            "factory": population * 0.45,
            "shop": population * 0.8,
            "builder": unbuilt_owned_lots * 0.05,
            "repair": worn_houses * 0.1,
            "delivery": max(0.2, population * 0.035),
            "cleaning": worn_houses * 0.05,
            "car_factory": vehicle_demand,
            "showroom": vehicle_demand,
        }
        price = {
            "farm": 20_000.0, "factory": 32_000.0, "shop": 44_000.0,
            "builder": BUILD_COST, "repair": 200_000.0,
            "delivery": 150_000.0, "cleaning": 100_000.0,
            "car_factory": CAR_PRICE, "showroom": CAR_PRICE,
        }
        opportunities = []
        for kind, expected_demand in demand.items():
            if kind not in STARTUP:
                continue
            firms = [business for business in self.businesses if business.kind == kind]
            if kind == "shop" and not any(
                    business.kind in ("farm", "factory")
                    for business in self.businesses):
                continue
            supplied = sum(
                business.prod + max(0.0, business.stock / 7.0)
                + max(0.0, business.car_stock / 7.0)
                + sum(max(0.0, quantity) / 7.0
                      for quantity in business.service_inventory.values())
                for business in firms
            )
            unmet = max(0.0, expected_demand - supplied)
            if unmet <= 0:
                continue

            recipe = PRODUCTION_RECIPES.get(kind)
            if recipe:
                input_cost = sum(
                    quantity * INPUT_PRICES[item]
                    for item, quantity in recipe["inputs"].items()
                )
                expected_margin = (
                    price[kind] * recipe["output"] - input_cost
                    - recipe["operating_cost"]
                    - self.policy.min_wage * recipe["labor_hours"] / (8 * DPM)
                )
            elif kind == "shop":
                expected_margin = price[kind] * 0.2
            elif kind == "showroom":
                expected_margin = max(0.0, CAR_PRICE - CAR_COST)
            else:
                expected_margin = price[kind] * 0.25
            if expected_margin <= 0:
                continue
            supply_gap = min(1.0, unmet / max(expected_demand, 1.0))
            profitability = sum(
                max(-1.0, min(1.0, business.last_profit / STARTUP[kind]))
                for business in firms
            ) / max(1, len(firms))
            score = expected_margin * supply_gap * (1.0 + 0.25 * profitability)
            if score > 0:
                opportunities.append((score, kind))
        if not opportunities:
            return

        opportunities.sort(reverse=True)
        best_score = opportunities[0][0]
        chance = (
            0.07 * c.entre * (0.5 + c.risk)
            * (0.2 + 0.8 * c.learning)
            * max(0.2, 1.0 - 0.4 * c.stress - 0.3 * c.depression)
            * min(2.0, best_score / 25_000.0)
        )
        if r.random() >= min(0.12, chance):
            return
        weights = [
            score * (1.0 + r.random() * (0.2 + 0.8 * c.risk))
            for score, _ in opportunities
        ]
        kind = max(
            zip(weights, (kind for _, kind in opportunities)),
            key=lambda item: item[0],
        )[1]
        self.found_business(c, kind)

    @ledgered_transaction("vehicle_purchase", "counterpart:vehicle_financing",
                          include_businesses=True)
    def buy_car(self, c):
        if (not is_adult(c) or c.vehicle_value or not c.home
                or not (c.job or c.business)):
            return False
        dealers = [
            business for business in self.businesses
            if business.market_product == "vehicles" and business.car_stock >= 1
        ]
        if not dealers:
            return False
        dealer = min(dealers, key=lambda b: b.car_stock)
        price = CAR_PRICE * self.house_index
        liquid = c.cash + c.savings
        down = min(liquid * 0.5, price * 0.4)
        loan_amount = price - down
        rate = self.policy.loan_rate + 0.03
        if not self.credit_ok(c, loan_amount, 60, "vehicle", rate):
            return False
        loan = self.make_loan(c, loan_amount, rate, 60, "vehicle", c)
        if not self.pay_from(c, price):
            self.end_loan(loan)
            self.bank.cash += loan_amount
            self.bank.loan_book -= loan_amount
            c.cash -= loan_amount
            return False
        dealer.car_stock -= 1
        dealer.cash += price
        dealer.rev += price
        dealer.demand_today += 1.0
        dealer.sold_today += 1.0
        self._record_trade_contract(
            c, dealer, "vehicles", 1.0, price, dealer.quality
        )
        c.vehicle_value = price
        c.vehicle_color = self.rng.choice(("red", "blue", "yellow", "purple"))
        c.learn(0.03, financial=True)
        c.think(f"Membeli mobil seharga {rp(price)} dengan kredit.")
        self.log("good", f"{c.first.upper()} MEMBELI MOBIL", f"Harga {rp(price)} · cicilan 5 tahun")
        return True

    def maybe_buy_car(self, c):
        if (not is_adult(c) or c.vehicle_value or not c.home
                or not (c.job or c.business) or self.rng.random() > 0.01):
            return
        self.buy_car(c)

    def maybe_buy_house(self, c):
        r = self.rng
        if not is_adult(c) or c.age >= 65 or r.random() > 0.15:
            return
        if any(lot.land_owner is c and lot.building is None for lot in self.lots):
            return
        stock = [h for h in self.houses if h.owner is not c and not h.bank_owned]
        if not stock:
            return
        renter = c.home is None or c.home.owner is not c
        investor = c.greed * c.risk > 0.35 and len(c.houses) < 4
        if not ((renter and not c.houses) or investor):
            return
        h = min(stock, key=lambda x: x.value)
        self.buy_house(c, h)

    def maybe_buy_land(self, c):
        if (not is_adult(c) or c.age >= 60 or c.houses
                or any(lot.land_owner is c for lot in self.lots)
                or (c.home is not None and c.home.owner is c)):
            return
        reserve = max(3 * c.est_exp, 5_000_000)
        if c.cash + c.savings < self.lot_price + BUILD_COST + reserve:
            return
        if self.rng.random() > 0.025 * (0.5 + c.patience) * (1 - 0.5 * c.fear):
            return
        self.buy_land(c)

    def maybe_build_house(self, c):
        if not is_adult(c):
            return
        owned = [lot for lot in self.lots if lot.land_owner is c and lot.building is None]
        if not owned or c.cash + c.savings < BUILD_COST + max(c.est_exp, 2_000_000):
            return
        if self.rng.random() > 0.25 * (0.5 + c.patience) * (1 - 0.5 * c.depression):
            return
        self.build_house(c, owned[0])

    # ---- rumah
    def move_in(self, c, h):
        c.home = h
        h.occupants.append(c)
        c.missed_rent = 0

    def housing_market(self):
        homeless = [c for c in self.citizens if c.home is None]
        if not homeless:
            return
        self.rng.shuffle(homeless)
        for c in homeless:
            free = [h for h in self.houses if h.free > 0]
            if not free:
                break
            mine = [h for h in c.houses if h.free > 0]
            h = mine[0] if mine else min(free, key=lambda x: x.rent_pp() * (1 + 0.1 * self.rng.random()))
            self.move_in(c, h)
            c.think("Dapat tempat tinggal baru.")

    # ---- pasar kerja
    def job_market(self):
        r = self.rng
        emps = [e for e in self.workplaces() if e.vacancies > 0 and e.can_hire()]
        if not emps:
            return
        seekers = [
            c for c in self.citizens
            if is_adult(c) and c.age < RETIRE_AGE and c.business is None
            and (c.job is None or r.random() < 0.03)
        ]
        r.shuffle(seekers)
        for c in seekers:
            emps = [e for e in emps if e.vacancies > 0]
            if not emps:
                break
            self._match_job(c, emps)

    def _match_job(self, c, employers):
        if not is_adult(c) or not employers:
            return False
        best = max(employers, key=lambda employer: employer.pay_for(c))
        wage = best.pay_for(c)
        if c.job is None:
            reserve = (
                self.policy.min_wage * (0.9 + 0.5 * c.greed)
                * (0.985 ** c.unemp_days)
            )
            if wage < reserve:
                return False
        else:
            if wage <= c.job.pay_for(c) * 1.12 or not best.can_hire():
                return False
            c.job.workers.remove(c)
        best.workers.append(c)
        c.job = best
        c.unemp_days = 0
        c.missed_pay = 0
        c.think(f"Diterima kerja di {best.name}, gaji {rp(wage)}/bln.")
        c.learn(0.0015)
        return True

    def try_seek_job(self, c):
        if (c not in self.citizens or not is_adult(c)
                or c.age >= RETIRE_AGE
                or c.business is not None):
            return False
        employers = [
            employer for employer in self.workplaces()
            if employer.vacancies > 0 and employer.can_hire()
        ]
        return self._match_job(c, employers)

    def agent_decision_cycle(self, c):
        """Update one citizen's BDI state and execute at most one validated step."""
        if c not in self.citizens or not is_adult(c):
            return False
        if not hasattr(c, "bdi"):
            c.bdi = BDIState()
        if not hasattr(c, "adaptive_learning"):
            c.adaptive_learning = LearningState()
        state = c.bdi
        learning = c.adaptive_learning
        if learning.last_decision_day == self.day:
            return False
        settle_pending(learning, self, c)
        learning.last_decision_day = self.day
        update_beliefs(self, c, state)
        goals = form_goals(self, c, state)
        current_state = planning_state(self, c)
        actions = available_actions(self, c, current_state)
        context = learning_context(c)
        candidates = []
        for goal in goals:
            plan = AGENT_PLANNER.plan(current_state, goal, actions)
            if plan is not None and plan.actions:
                base_score = (
                    goal.priority * goal.expected_benefit / (1.0 + plan.cost)
                )
                arm = f"{goal.id}|{plan.actions[0].token}"
                score = learning.score(context, arm, base_score)
                candidates.append(
                    (score, goal.priority, goal.id, goal, plan, context, arm)
                )
        if not candidates:
            if (state.intention is not None
                    and state.intention.status == "active"):
                state.intention.status = "cancelled"
            state.intention = None
            if consider_social_action(self, c):
                return True
            if consider_family_action(self, c):
                return True
            if consider_teaching(self, c):
                return True
            if consider_organization(self, c):
                return True
            return consider_price_experiment(
                self,
                c,
                state.motivations.get("learning", 0.0),
                state.motivations,
            )

        _, _, _, goal, plan, context, arm = max(
            candidates, key=lambda item: (item[0], item[1], item[2])
        )
        action_ids = tuple(action.token for action in plan.actions)
        previous = state.intention
        if (previous is not None and previous.goal_id == goal.id
                and previous.status == "active"
                and previous.action_ids[previous.next_step:] == action_ids):
            intention = Intention(
                goal.id, previous.action_ids, previous.planned_day,
                previous.next_step, previous.last_action_day,
            )
        else:
            if previous is not None and previous.status == "active":
                previous.status = "cancelled"
            intention = Intention(goal.id, action_ids, self.day)
        before = outcome_snapshot(self, c)
        social_need = 1.0 / (1.0 + social_contact_count(c))
        weights = objective_weights(state.motivations, social_need)
        if not execute_action(self, c, plan.actions[0]):
            learning.update(context, arm, -0.25, self.day)
            intention.status = "cancelled"
            state.intention = None
            return False
        learning.remember(context, arm, before, weights, self.day)
        intention.next_step += 1
        intention.last_action_day = self.day
        if intention.next_step >= len(intention.action_ids):
            intention.status = "completed"
        state.intention = intention
        return True

    def share_experiment_result(self, sender, receiver, experiment_id):
        """Explicitly share one completed experiment with one other citizen."""
        return _share_experiment_result(
            self, sender, receiver, experiment_id
        )

    # ---- konsumsi
    @ledgered_transaction("consumer_purchase", "counterpart:consumer_settlement",
                          business_selector=_consumer_business_scope)
    def buy_goods(self, c, want):
        if c not in self.citizens:
            return 0.0
        try:
            want = float(want)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Jumlah pembelian barang harus berupa angka terbatas.") from None
        if not math.isfinite(want) or want < 0:
            raise ValueError("Jumlah pembelian barang harus nonnegatif dan terbatas.")
        p = self.policy
        sellers = [
            business for business in self.businesses
            if business.kind in ("shop", "farm", "factory")
            and business.stock > 1e-6 and business.price > 0
        ]
        if not sellers or want <= 0:
            return 0.0
        hx, hy = c.home.lot.door if c.home else (MAP_W / 2, MAP_H / 2)

        def score(seller):
            d = math.hypot(seller.lot.door[0] - hx, seller.lot.door[1] - hy)
            quality_discount = max(0.5, min(1.5, seller.quality))
            scarcity = 1.0 + min(0.5, 1.0 / max(seller.stock, 1.0))
            return seller.price * scarcity / quality_discount + 15 * d

        order = sorted(sellers, key=score)
        if not math.isfinite(c.cash) or not math.isfinite(c.savings):
            raise ValueError("Saldo dana warga tidak valid.")
        available_funds = max(0.0, c.cash) + max(0.0, c.savings)
        if not math.isfinite(available_funds):
            raise ValueError("Dana pembelian warga tidak valid.")
        remaining, spent, got = want, 0.0, 0.0
        for seller in order:
            if remaining <= 1e-9:
                break
            unit = seller.price * (1 + p.tax_ppn)
            afford = (available_funds - spent) / unit
            requested = min(remaining, afford)
            seller.demand_today += requested
            q = min(requested, seller.stock)
            available_for_purchase = available_funds - spent
            net = q * seller.price
            tax = net * p.tax_ppn
            cost = net + tax
            if q > 0 and cost > available_for_purchase:
                q *= max(0.0, available_for_purchase / cost - 1e-14)
                net = q * seller.price
                tax = net * p.tax_ppn
                cost = net + tax
            if q <= 1e-6:
                continue
            seller.stock -= q
            seller.cash += net
            seller.rev += net
            seller.sold_today += q
            self.gov_in(tax)
            self._record_trade_contract(
                c, seller, seller.market_product, q, seller.price, seller.quality,
                tax,
            )
            spent += cost
            got += q
            remaining -= q
        if spent and not self.pay_from(c, spent):
            raise RuntimeError("Dana berubah saat penyelesaian pembelian barang.")
        self.sales_today += spent
        return got

    def citizen_daily(self, c):
        r = self.rng
        p = self.policy
        advance_age(self, c)
        px = self.avg_price()
        lux_cash = max(0.0, c.cash - c.est_exp * (0.2 + 0.5 * c.frugal))
        spend = lux_cash * 0.06 * (1 - 0.6 * c.frugal)
        want = 1.0 + (spend / (px * (1 + p.tax_ppn)) if px > 0 else 0.0)
        got = self.buy_goods(food_payer(self, c), want)
        if got < 0.99 and self.treasury >= 25_000:
            got += self.purchase_emergency_ration(c, 1.0 - got)
        if got < 0.99:
            c.hunger += 1
            c.health -= 3
            if c.hunger == 3:
                c.think("Lapar, nggak ada uang buat makan.")
        else:
            c.hunger = 0
            c.health = min(100.0, c.health + 1)
        target = (40 + 15 * (c.home is not None) + 15 * (c.job is not None or c.business is not None)
                  + 10 * (got > 1.2) + 10 * min(1.0, (c.cash + c.savings) / (3 * c.est_exp))
                  - 20 * (c.hunger > 0))
        c.happy += 0.1 * (target - c.happy)
        strain = (0.32 * (c.hunger > 0) + 0.22 * (c.home is None)
                  + 0.18 * (c.job is None and c.business is None and c.age < RETIRE_AGE)
                  + 0.16 * (c.missed_rent > 0) + 0.14 * (c.missed_pay > 0)
                  + 0.18 * (c.debt > max(c.income_est() * 6, 1_000_000))
                  + 0.12 * self.crime_rate)
        relief = (0.12 * (c.home is not None) + 0.10 * (c.job is not None or c.business is not None)
                  + 0.10 * (c.cash + c.savings > c.est_exp * 2)
                  + 0.08 * (c.health > 75))
        c.stress = max(0.0, min(1.0, c.stress * 0.94 + strain * 0.18 - relief * 0.12))
        c.fear = max(0.0, min(1.0, c.fear * 0.96 + self.crime_rate * 0.12
                              + (0.12 if c.missed_pay or c.missed_rent else 0.0)
                              + (0.08 if c.debt > c.income_est() * 12 else 0.0)))
        c.sadness = max(0.0, min(1.0, c.sadness * 0.96
                                 + (0.10 if c.hunger else 0.0)
                                 + max(0.0, (45.0 - c.happy) / 450)))
        depression_pressure = (max(0.0, (55.0 - c.happy) / 55) * 0.5
                               + c.stress * 0.35 + c.sadness * 0.15)
        recovery = max(0.0, c.happy - 60) / 4000
        c.depression = max(0.0, min(1.0, c.depression * 0.995
                                    + depression_pressure * 0.01 - recovery))
        if c.depression > 0.55 and self.day % 7 == c.id % 7:
            c.think("Merasa murung berkepanjangan; butuh dukungan dan keadaan yang lebih baik.")
        if (is_adult(c) and c.job is None and c.business is None
                and c.age < RETIRE_AGE):
            c.unemp_days += 1
        if c.age >= RETIRE_AGE and c.job:
            c.job.workers.remove(c)
            c.job = None
            c.think("Pensiun dari pekerjaan.")
        if c.health <= 0:
            self.remove_citizen(c, cause="meninggal kelaparan")
        elif r.random() < daily_mortality_probability(self, c):
            self.remove_citizen(c, cause="meninggal")
        elif c.unemp_days > 150 and c.cash + c.savings < 200_000 and r.random() < 0.004:
            self.log("info", f"{c.first.upper()} PINDAH KOTA", "Menganggur terlalu lama")
            self.remove_citizen(c, inherit=False, cause="pindah")

    @ledgered_transaction("emergency_food_purchase",
                          "counterpart:emergency_food_supplier")
    def purchase_emergency_ration(self, c, shortfall):
        if c not in self.citizens or shortfall <= 0 or self.treasury < 25_000:
            return 0.0
        ration = min(shortfall, self.treasury / 25_000)
        amount = ration * 25_000
        self.treasury -= amount
        c.exp_acc += amount
        return ration

    # ---- produksi
    @ledgered_transaction("production_cycle", "counterpart:production_conversion",
                          business_selector=_production_business_scope)
    def production_cycle(self, business=None):
        if business is not None and (
                business not in self.businesses
                or business.kind not in PRODUCTION_RECIPES):
            raise ValueError("Usaha tidak terdaftar atau tidak memiliki resep produksi.")
        if business is None:
            self.import_supply_remaining = dict(DAILY_IMPORT_CAPACITY)
        producers = (
            [business] if business is not None
            else [item for item in self.businesses if item.kind in PRODUCTION_RECIPES]
        )
        for firm in producers:
            firm.age_days += 1
            recipe = PRODUCTION_RECIPES[firm.kind]
            skill_name = recipe["skill"]
            crew = [firm.owner] + list(firm.workers)
            effective_hours = 0.0
            weighted_skill = 0.0
            for worker in crew:
                skill = max(0.0, min(1.0, getattr(worker, skill_name, worker.skill)))
                hours_fraction = (
                    1.0 if worker is firm.owner
                    else max(0.0, min(1.0, firm.work_hours / 40.0))
                )
                contribution = (
                    8.0 * worker.work_capacity * hours_fraction
                    * max(0.1, 0.6 + 0.8 * skill)
                )
                effective_hours += contribution
                weighted_skill += contribution * skill

            firm.prod = 0.0
            firm.production_failed = ""
            if effective_hours <= 0:
                firm.production_failed = "labor"
                continue
            average_skill = weighted_skill / effective_hours
            firm.quality = max(0.25, min(1.5, 0.65 + average_skill * 0.7))
            firm.production_progress = min(
                firm.production_progress + effective_hours,
                recipe["labor_hours"] * recipe["capacity"] * 2,
            )
            desired_batches = min(
                recipe["capacity"],
                firm.production_progress / recipe["labor_hours"],
            )
            if desired_batches <= 1e-9:
                continue

            for commodity, per_batch in recipe["inputs"].items():
                required = per_batch * desired_batches
                held = firm.input_inventory.get(commodity, 0.0)
                if held < required:
                    self.buy_production_inputs(firm, commodity, required - held)

            batches = desired_batches
            for commodity, per_batch in recipe["inputs"].items():
                batches = min(
                    batches,
                    firm.input_inventory.get(commodity, 0.0) / per_batch,
                )
            if recipe["operating_cost"] > 0:
                batches = min(
                    batches,
                    max(0.0, firm.cash) / recipe["operating_cost"],
                )
            if batches <= 1e-9:
                firm.production_failed = "inputs_or_cash"
                continue

            input_cost = 0.0
            for commodity, per_batch in recipe["inputs"].items():
                quantity = per_batch * batches
                unit_cost = firm.input_costs.get(
                    commodity, INPUT_PRICES[commodity]
                )
                input_cost += quantity * unit_cost
                remaining = firm.input_inventory.get(commodity, 0.0) - quantity
                if remaining <= 1e-9:
                    firm.input_inventory.pop(commodity, None)
                    firm.input_costs.pop(commodity, None)
                else:
                    firm.input_inventory[commodity] = remaining

            operating_cost = recipe["operating_cost"] * batches
            firm.cash -= operating_cost
            firm.exp += input_cost + operating_cost
            output = recipe["output"] * batches
            output_cost = (input_cost + operating_cost) / output
            product = recipe["product"]
            if product in ("construction", "repair", "delivery", "cleaning"):
                old_quantity = firm.service_inventory.get(product, 0.0)
                old_cost = firm.service_costs.get(product, 0.0)
                total_quantity = old_quantity + output
                firm.service_costs[product] = (
                    old_quantity * old_cost + output * output_cost
                ) / total_quantity
                firm.service_inventory[product] = total_quantity
            elif product == "vehicles":
                old_quantity = firm.car_stock
                total_quantity = old_quantity + output
                firm.unit_cost = (
                    old_quantity * firm.unit_cost + output * output_cost
                ) / total_quantity
                firm.car_stock = total_quantity
            else:
                old_quantity = firm.stock
                total_quantity = old_quantity + output
                firm.unit_cost = (
                    old_quantity * firm.unit_cost + output * output_cost
                ) / total_quantity
                firm.stock = total_quantity
            firm.prod = output
            firm.production_progress = max(
                0.0,
                firm.production_progress - batches * recipe["labor_hours"],
            )
            if batches + 1e-9 < desired_batches:
                firm.production_failed = "inputs_or_cash"

    def factory_daily(self, business):
        self.production_cycle(business)

    @ledgered_transaction("vehicle_restock", "counterpart:vehicle_supply",
                          business_selector=_showroom_business_scope)
    def showroom_daily(self, showroom):
        factories = [b for b in self.businesses if b.kind == "car_factory" and b.car_stock >= 1]
        if not factories or showroom.cash < CAR_COST:
            return
        factory = max(factories, key=lambda b: b.car_stock)
        factory.car_stock -= 1
        showroom.car_stock += 1
        showroom.cash -= CAR_COST
        showroom.exp += CAR_COST
        factory.cash += CAR_COST
        factory.rev += CAR_COST
        factory.demand_today += 1.0
        factory.sold_today += 1.0
        self._record_trade_contract(
            showroom, factory, "vehicles", 1.0, CAR_COST, factory.quality
        )

    @ledgered_transaction("shop_restock", "counterpart:goods_supply",
                          business_selector=_shop_restock_business_scope)
    def shop_restock(self, s):
        dem = sum(s.daily_demand) / len(s.daily_demand) if s.daily_demand else 3.0
        target = max(5.0, dem * 2.5 + 2)
        need = target - s.stock
        s.age_days += 1
        if need <= 0:
            return target
        fs = sorted([b for b in self.businesses if b.kind in ("factory", "farm") and b.stock >= 1],
                    key=lambda b: b.price)
        for f in fs:
            if need <= 1e-6:
                break
            q = min(need, f.stock, s.cash / f.price)
            if q <= 1e-6:
                continue
            cost = q * f.price
            s.cash -= cost
            s.exp += cost
            f.cash += cost
            f.rev += cost
            f.stock -= q
            f.demand_today += q
            f.sold_today += q
            s.cost_avg = (s.stock * s.cost_avg + q * f.price) / (s.stock + q)
            s.stock += q
            self._record_trade_contract(
                s, f, f.market_product, q, f.price, f.quality
            )
            need -= q
        return target

    @ledgered_transaction("market_price_settlement",
                          "counterpart:inventory_spoilage",
                          business_selector=_all_business_scope)
    def adjust_prices(self, targets):
        for b in self.businesses:
            recipe = PRODUCTION_RECIPES.get(b.kind)
            service_stock = sum(b.service_inventory.values())
            sellable_stock = b.stock + b.car_stock + service_stock
            unmet = max(0.0, b.demand_today - b.sold_today)
            average_demand = (
                sum(b.daily_demand) / len(b.daily_demand)
                if b.daily_demand else max(b.demand_today, b.prod, 1.0)
            )
            target_stock = max(1.0, average_demand * 2.5, b.prod * 4.0)
            low = unmet > 0.5 or sellable_stock < 1.0
            high = sellable_stock > target_stock * 1.5

            if b.kind == "shop":
                if low:
                    b.markup = min(b.markup * 1.03, 1.2)
                elif high:
                    b.markup = max(b.markup * 0.985, 0.08)
                b.price = max(b.cost_avg * (1 + b.markup), 1000.0)
                b.price = max(
                    1000.0,
                    b.price * b.innovation_price_multiplier,
                )
            else:
                pressure = max(-1.0, min(1.0, (unmet - (sellable_stock - target_stock))
                                          / max(target_stock, 1.0)))
                if b.kind in ("farm", "factory"):
                    base_floor = 4_000.0 if b.kind == "farm" else 8_000.0
                elif b.kind == "showroom":
                    base_floor = CAR_PRICE * 0.5
                elif recipe:
                    base_floor = max(1_000.0, b.unit_cost * 1.05)
                else:
                    base_floor = 1_000.0
                previous_price = max(1.0, b.price)
                candidate_price = previous_price * math.exp(0.025 * pressure)
                b.price = max(
                    base_floor,
                    min(candidate_price, max(base_floor, previous_price * 1.05)),
                )

            if recipe and b.stock > 0:
                b.stock *= 1.0 - recipe["spoilage"]
            elif b.kind == "shop" and b.stock > 0:
                b.stock *= 0.98
            if b.kind not in PRODUCTION_RECIPES and b.kind != "shop":
                b.age_days += 1
            b.soldout_hist.append(low)
            b.over_hist.append(high)
            b.daily_demand.append(b.demand_today)
            b.demand_today = b.sold_today = 0.0

    # ---- mingguan
    @ledgered_transaction("weekly_government_settlement", "counterpart:welfare_settlement",
                          include_all=True)
    def weekly_start(self):
        p = self.policy
        amt = p.welfare * 7 / DPM
        if amt > 0 and self.day > 0:
            for c in self.citizens:
                if c.job is None and c.business is None and c.age >= 18 and c.cash + c.savings < 20_000_000:
                    if self.treasury >= amt:
                        self.treasury -= amt
                        c.cash += amt
        self.rev_ma = 0.7 * self.rev_ma + 0.3 * self.rev_week
        self.rev_week = 0.0
        wage_week = self.hall.wage * 7 / DPM
        budget = self.rev_ma * 0.8 + self.treasury / 30
        cap = int(len(self.citizens) * p.gov_jobs_share)
        self.hall.max_workers = max(0, min(int(budget / wage_week), cap))
        excess = len(self.hall.workers) - self.hall.max_workers
        for _ in range(max(0, excess)):
            w = min(self.hall.workers, key=lambda x: x.skill)
            self.hall.workers.remove(w)
            w.job = None
            w.think("Dirumahkan dari Balai Kota (anggaran kota menipis).")

    @ledgered_transaction("payroll", "counterpart:payroll_accrual", include_all=True)
    def payroll(self):
        p = self.policy
        for b in self.workplaces():
            is_hall = b is self.hall
            for w in list(b.workers):
                gm = b.pay_for(w)
                gross = gm * 7 / DPM
                src = self.treasury if is_hall else b.cash
                if src >= gross:
                    if is_hall:
                        self.treasury -= gross
                    else:
                        b.cash -= gross
                        b.exp += gross
                    tax = max(0.0, gm - p.pph_exempt) * p.tax_pph * 7 / DPM
                    if tax:
                        self.gov_in(tax)
                    w.cash += gross - tax
                    w.missed_pay = 0
                    w.learn(0.001)
                else:
                    w.missed_pay += 1
                    if w.missed_pay >= 2:
                        b.workers.remove(w)
                        w.job = None
                        w.think(f"Gaji {b.name} macet, berhenti kerja.")

    def weekly_business(self, b):
        pw = b.payroll_week()
        sold = sum(b.soldout_hist)
        over = sum(b.over_hist)
        if len(b.soldout_hist) >= 7:
            if sold >= 4:
                b.work_hours = 40.0
            elif over >= 5:
                b.work_hours = 20.0
            if sold >= 4 and b.cash > pw * 6 + 5_000_000 and b.vacancies == 0 and b.max_workers < 14:
                b.max_workers += 1
            elif (over >= 5 and b.work_hours <= 20.0
                  and len(b.workers) > 1 and b.age_days > 30):
                w = min(b.workers, key=lambda x: x.skill)
                b.workers.remove(w)
                w.job = None
                w.think(f"Di-PHK {b.name} karena stok menumpuk.")
                b.max_workers = len(b.workers)
        if b.vacancies > 0:
            b.vac_weeks += 1
            if b.vac_weeks >= 2 and b.cash > pw * 6:
                b.wage *= 1.02
        else:
            b.vac_weeks = 0
            if self.unemployment() > 0.25:
                b.wage *= 0.995
        b.wage = max(b.wage, self.policy.min_wage)
        if b.workers and b.cash < pw * 1.2:
            w = min(b.workers, key=lambda x: x.skill)
            b.workers.remove(w)
            w.job = None
            b.max_workers = len(b.workers)
            w.think(f"Di-PHK {b.name} karena kas tipis.")

    # ---- bulanan
    def monthly_business(self, b):
        p = self.policy
        profit = b.rev - b.exp
        if b.loan:
            pay, interest = self.loan_due(b.loan)
            if b.cash >= pay:
                b.cash -= pay
                b.exp += interest
                self.loan_paid(b.loan, pay, interest)
                if b.loan and b.loan not in self.loans:
                    b.loan = None
                profit -= interest
            else:
                b.loan.missed += 1
                if b.loan.missed >= 3:
                    self.default_loan(b.loan)
                    return
        tax = min(max(0.0, profit) * p.tax_corp, max(0.0, b.cash))
        if tax:
            b.cash -= tax
            self.gov_in(tax)
        b.last_profit = profit - tax
        pw = b.payroll_week()
        reserve = pw * 2 + 5_000_000
        draw = 0.0
        if b.cash > reserve:
            draw = min(b.cash - reserve, max(0.6 * max(b.last_profit, 0.0), p.min_wage * 0.8))
        if draw > 0:
            b.cash -= draw
            ptax = max(0.0, draw - p.pph_exempt) * p.tax_pph
            if ptax:
                self.gov_in(ptax)
            b.owner.cash += draw - ptax
        if profit < 0:
            b.loss_months += 1
        else:
            b.loss_months = 0
            if b.kind == "shop":
                b.markup = max(b.markup * 0.99, 0.08)
        if profit < 0 and b.kind == "shop":
            b.markup = min(b.markup * 1.05, 1.2)
        b.rev = b.exp = 0.0
        if b.age_days > 60 and (b.cash < 0 or (b.loss_months >= 4 and b.cash < pw * 2)):
            self.close_business(b)

    @ledgered_transaction("monthly_settlement",
                          "counterpart:interest_and_rent_accruals",
                          include_all=True, track_world_collections=True)
    def monthly(self):
        p = self.policy
        for c in self.citizens:
            if c.savings > 0:
                i = c.savings * p.deposit_rate / 12
                c.savings += i
                self.bank.deposits += i
                self.bank.profit -= i
                self.bank.equity -= i
        for h in self.houses:
            for o in list(h.occupants):
                if o is h.owner:
                    continue
                rent = h.rent_pp()
                if self.pay_from(o, rent):
                    o.missed_rent = 0
                    if h.owner:
                        h.owner.cash += rent
                    elif h.bank_owned:
                        self.bank.cash += rent
                        self.bank.profit += rent
                        self.bank.equity += rent
                    else:
                        self.gov_in(rent)
                else:
                    o.missed_rent += 1
                    if o.missed_rent >= 2:
                        h.occupants.remove(o)
                        o.home = None
                        o.think("Diusir dari rumah sewa karena nunggak.")
                        self.log("bad", f"{o.first.upper()} DIUSIR", "Nunggak sewa 2 bulan")
        for c in list(self.citizens):
            for l in list(c.loans):
                if l.kind == "biz":
                    continue
                pay, interest = self.loan_due(l)
                if self.pay_from(c, pay):
                    self.loan_paid(l, pay, interest)
                else:
                    l.missed += 1
                    c.credit_score = max(300.0, c.credit_score - 8)
                    if l.missed >= 3:
                        self.default_loan(l)
            c.est_exp = 0.6 * c.est_exp + 0.4 * max(c.exp_acc, 1_000_000)
            c.exp_acc = 0.0
            c.learn(0.0005, financial=True)
        for b in list(self.businesses):
            if b in self.businesses:
                self.monthly_business(b)
                b.equipment_value *= 0.994
        for h in self.houses:
            old_bank_value = h.bank_value
            h.condition = max(0.45, h.condition * 0.998)
            if h.bank_owned:
                h.bank_value = min(h.bank_value, h.value * 0.7)
                change = h.bank_value - old_bank_value
                self.bank.repossessed_assets += change
                self.bank.equity += change
        for c in self.citizens:
            c.vehicle_value *= 0.985
        occ = sum(len(h.occupants) for h in self.houses) / max(1, sum(h.cap for h in self.houses))
        self.house_index *= 1 + (0.003 if occ > 0.9 else (-0.001 if occ < 0.6 else 0.0005))
        self.settle_social_organizations()
    @ledgered_transaction("migration_entry", "counterpart:migration_settlement",
                          track_world_collections=True)
    def migration_daily(self):
        free = sum(h.free for h in self.houses)
        if free <= 0 or len(self.citizens) >= MAX_POP:
            return
        openings = sum(getattr(work, "vacancies", 0) for work in self.workplaces())
        chance = 0.0008 + min(0.012, openings / max(1, len(self.citizens)) * 0.002)
        chance *= max(0.0, 1.0 - self.unemployment() * 1.5)
        if self.treasury < 100_000_000:
            chance *= 0.25
        if self.rng.random() >= chance:
            return
        c = self.add_citizen(young=True)
        self.housing_market()
        self.log("info", f"{c.first.upper()} PINDAH KE KOTA", "Pendatang baru mulai dari Rp0")

    @ledgered_transaction("gig_payment", "counterpart:gig_contracts", include_all=True)
    def gig_market(self):
        """Pekerjaan harian singkat dari proyek kota; dibayar dari kas, bukan uang baru."""
        seekers = [c for c in self.citizens if c.age < RETIRE_AGE
                   and c.job is None and c.business is None]
        if not seekers or self.treasury < 500_000:
            return
        slots = min(4, max(1, int(len(seekers) * 0.12)))
        pay = min(150_000.0, max(60_000.0, self.policy.min_wage / 30))
        tasks = (
            ("kuli bangunan", "construction_skill", "builder"),
            ("tukang servis", "repair_skill", "repair"),
            ("jasa kebersihan", "skill", "cleaning"),
            ("jasa antar", "skill", "delivery"),
        )
        self.rng.shuffle(seekers)
        for citizen in seekers[:slots]:
            task, skill_name, business_kind = max(
                tasks,
                key=lambda option: getattr(citizen, option[1]) + self.rng.random() * 0.15,
            )
            skill = getattr(citizen, skill_name)
            if citizen.stress > 0.8 and self.rng.random() > 0.35:
                continue
            provider = next((business for business in self.businesses
                             if business.kind == business_kind), None)
            contract = pay * 2 if provider else pay
            if self.treasury < contract:
                break
            self.treasury -= contract
            if provider:
                provider.cash += contract - pay
                provider.rev += contract
                provider.exp += pay
            citizen.cash += pay
            citizen.gigs_done += 1
            citizen.last_gig = task
            citizen.last_gig_day = self.day
            citizen.learn(0.002)
            if skill_name == "construction_skill":
                citizen.construction_skill = min(1.0, skill + 0.008)
            elif skill_name == "repair_skill":
                citizen.repair_skill = min(1.0, skill + 0.008)
            citizen.think(f"Mengambil gig {task} dan mendapat {rp(pay)}.")
            self.gig_count += 1

    @ledgered_transaction("crime_settlement", "counterpart:crime_settlement",
                          include_all=True)
    def crime_daily(self):
        """Kejadian kriminal berisiko rendah yang memindahkan uang dan berdampak sosial."""
        offenders = [c for c in self.citizens if c.age >= 18
                     and c.job is None and c.business is None]
        targets = [c for c in self.citizens if c.cash >= 500_000]
        committed = 0
        if offenders and targets:
            for offender in offenders:
                desperation = max(0.0, 1.0 - (offender.cash + offender.savings) / 1_000_000)
                chance = 0.00015 + 0.0012 * self.unemployment() + 0.001 * desperation
                chance *= 0.5 + offender.risk
                if self.rng.random() >= chance:
                    continue
                target = self.rng.choice(targets)
                if target is offender:
                    continue
                amount = min(target.cash, self.rng.uniform(50_000, 250_000))
                if self.rng.random() < 0.55:
                    target.cash -= amount
                    offender.cash += amount
                    offender.crimes += 1
                    offender.stress = min(1.0, offender.stress + 0.08)
                    target.fear = min(1.0, target.fear + 0.1)
                    target.stress = min(1.0, target.stress + 0.06)
                    target.think("Uangku dicuri; aku jadi waspada di kota.")
                    self.log("bad", "PENCURIAN TERJADI", f"{rp(amount)} dicuri dari warga")
                else:
                    fine = min(offender.cash, amount * 1.5)
                    offender.cash -= fine
                    self.gov_in(fine)
                    offender.crimes += 1
                    offender.fear = min(1.0, offender.fear + 0.18)
                    self.log("info", "PELAKU PENCURIAN TERTANGKAP",
                             f"Denda {rp(fine)} masuk ke kas pemerintah")
                committed += 1
        self.crime_history.append(committed / max(1, len(self.citizens)))

    @ledgered_transaction("random_event_settlement", "counterpart:event_settlement",
                          business_selector=_random_event_business_scope)
    def random_event(self):
        if self.day - self.last_random_event < 20 or self.rng.random() >= 0.018:
            return
        self.last_random_event = self.day
        farms = [b for b in self.businesses if b.kind == "farm"]
        event = self.rng.choice(("rain", "drought", "festival", "market"))
        if event == "rain" and farms:
            for farm in farms:
                farm.stock += farm.prod * 4
            self.log("good", "PANEN MELIMPAH", "Hujan meningkatkan pasokan pangan kota")
        elif event == "drought" and farms:
            for farm in farms:
                farm.stock *= 0.72
            self.log("bad", "KEMARAU", "Hasil panen turun; pasokan pangan menipis")
        elif event == "festival":
            active = [b for b in self.businesses if b.kind in ("shop", "farm")]
            if active and self.treasury >= 1_000_000:
                grant = min(5_000_000, self.treasury)
                business = self.rng.choice(active)
                self.treasury -= grant
                business.cash += grant
                self.log("good", "FESTIVAL KOTA", f"Kontrak pasokan {rp(grant)} diberikan ke {business.name}")
            else:
                self.log("info", "FESTIVAL KOTA", "Kegiatan warga meramaikan pusat kota")
        else:
            asset = self.rng.choice(list(self.market.assets.values()))
            move = self.rng.uniform(-0.035, 0.045)
            asset.price = max(1.0, asset.price * (1.0 + move))
            asset.hist.append(asset.price)
            self.log("good" if move >= 0 else "bad", "KABAR PASAR MENGGERAKKAN HARGA",
                     f"{asset.sym} {move * 100:+.1f}%")

    @ledgered_transaction("government_settlement", "counterpart:government_recapitalization")
    def government_cycle(self):
        if self.day >= self.next_election_day:
            eligible = [c for c in self.citizens if c.age >= 18]
            if eligible:
                mayor = max(eligible, key=lambda c: c.skill * 0.45 + c.entre * 0.25
                            + c.learning * 0.30 + self.rng.random() * 0.1)
                self.mayor_id = mayor.id
                mayor.think("Warga memilihku memimpin kota. Aku masih belajar mengelola anggaran.")
                self.log("info", f"{mayor.first.upper()} TERPILIH JADI WALI KOTA",
                         "Kebijakan fiskal kini menyesuaikan keadaan kota")
            self.next_election_day += 4 * DPY
        if self.mayor_id is None or self.day % 90:
            return
        mayor = next((c for c in self.citizens if c.id == self.mayor_id), None)
        if mayor is None:
            self.next_election_day = min(self.next_election_day, self.day)
            return
        capital_target = 0.08 * self.bank.loan_book
        capital_gap = max(0.0, capital_target - self.bank.equity)
        bailout = min(capital_gap, max(0.0, self.treasury - 100_000_000))
        if bailout:
            self.treasury -= bailout
            self.bank.cash += bailout
            self.bank.equity += bailout
            self.log("info", "BANK DIREKAPITALISASI PEMERINTAH",
                     f"Dukungan {rp(bailout)} · cadangan kota tetap {rp(self.treasury)}")
        if not self.auto_policy:
            return
        unemployment = self.unemployment()
        old_tax = self.policy.tax_pph
        old_welfare = self.policy.welfare
        if self.treasury < 250_000_000 and unemployment < 0.3:
            self.policy.tax_pph = min(0.25, self.policy.tax_pph + 0.002 * (0.5 + mayor.greed))
        elif unemployment > 0.28:
            self.policy.tax_pph = max(0.0, self.policy.tax_pph - 0.0015 * (0.5 + mayor.optimism))
            self.policy.welfare = min(2_000_000, self.policy.welfare + 25_000)
        elif self.treasury > 1_000_000_000 and unemployment < 0.12:
            self.policy.welfare = max(500_000, self.policy.welfare - 25_000)
        mayor.learn(0.02)
        self.government_learning = min(1.0, self.government_learning + 0.02 * (1.0 - self.government_learning))
        mayor.think("Meninjau pajak dan belanja kota berdasarkan kondisi ekonomi.")
        if self.policy.tax_pph != old_tax or self.policy.welfare != old_welfare:
            self.log("info", "KEBIJAKAN PEMERINTAH BERUBAH",
                     f"Pajak penghasilan {old_tax:.1%} → {self.policy.tax_pph:.1%} · "
                     f"bantuan {rp(old_welfare)} → {rp(self.policy.welfare)}")

    @ledgered_transaction("yearly_tax_settlement", "counterpart:tax_settlement",
                          include_all=True)
    def yearly(self):
        p = self.policy
        for h in self.houses:
            if h.owner:
                tax = h.value * p.tax_pbb
                if self.pay_from(h.owner, tax):
                    self.gov_in(tax)
            elif h.bank_owned:
                tax = min(h.value * p.tax_pbb, self.bank.cash)
                self.bank.cash -= tax
                self.bank.equity -= tax
                self.gov_in(tax)
        for b in self.businesses:
            tax = min(self.lot_price * p.tax_pbb, max(0.0, b.cash))
            b.cash -= tax
            b.exp += tax
            self.gov_in(tax)
        self.log("info", f"TAHUN {self.year} DIMULAI", f"Kas kota {rp(self.treasury)}")

    # ---- harian
    def daily(self):
        d = self.day
        r = self.rng
        begin_experiment_day(self)
        self.market.step(self.employment_rate() - 0.7)
        if d % 7 == 0:
            self.weekly_start()
        self.job_market()
        self.production_cycle()
        for b in self.businesses:
            if b.kind == "showroom":
                self.showroom_daily(b)
        targets = {}
        for b in self.businesses:
            if b.kind == "shop":
                targets[b] = self.shop_restock(b)
        order = list(self.citizens)
        r.shuffle(order)
        for c in order:
            if not getattr(c, "dead", False):
                self.citizen_daily(c)
        self.gig_market()
        self.crime_daily()
        capture_experiment_market(self)
        self.adjust_prices(targets)
        if d % 7 == 6:
            self.payroll()
        if d % 7 == 3:
            for b in list(self.businesses):
                self.weekly_business(b)
        self.housing_market()
        for c in list(self.citizens):
            if c.id % 7 == d % 7 and is_adult(c):
                self.finance(c)
                self.maybe_start_business(c)
                self.maybe_build_house(c)
                self.maybe_buy_land(c)
                self.maybe_buy_house(c)
                self.maybe_buy_car(c)
                self.agent_decision_cycle(c)
        if d % 7 == 0:
            consider_births(self)
        self.migration_daily()
        self.random_event()
        self.government_cycle()
        if d % DPM == DPM - 1:
            self.monthly()
        if d % DPY == DPY - 1:
            self.yearly()
        self.sales_hist.append(self.sales_today)
        self.sales_today = 0.0
        if d % 5 == 0:
            self.record()
        finish_experiment_day(self)

    # ---- statistik
    def record(self):
        cs = self.citizens
        if not cs:
            return
        nws = sorted(c.networth for c in cs)
        n = len(nws)
        gini = 0.0
        shifted = [x - min(0.0, nws[0]) for x in nws]
        shifted_total = sum(shifted)
        if shifted_total > 0:
            gini = sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(shifted)) / (n * shifted_total)
        px = self.avg_price()
        if px > 0 and self.cpi_base is None:
            self.cpi_base = px
        S = self.series
        S["uang"].append(sum(c.cash + c.savings for c in cs) / n)
        S["kekayaan"].append(nws[n // 2])
        S["nganggur"].append(self.unemployment() * 100)
        S["gini"].append(gini)
        S["ihk"].append(px / self.cpi_base * 100 if (px > 0 and self.cpi_base) else 100.0)
        S["pdb"].append(sum(self.sales_hist))
        S["kas_kota"].append(self.treasury)
        S["penduduk"].append(n)
        S["emosi"].append(sum(c.happy for c in cs) / n)
        S["kriminal"].append(self.crime_rate * 100)

    def gini_now(self):
        return self.series["gini"][-1] if self.series["gini"] else 0.0

    def agent_observation(self, citizen):
        """Return a read-only snapshot for observing one agent's cognitive state."""
        if citizen not in self.citizens:
            return None
        state = getattr(citizen, "bdi", None)
        learning = getattr(citizen, "adaptive_learning", None)
        memory = getattr(citizen, "memory", None)
        knowledge = getattr(citizen, "knowledge", None)
        experiments = getattr(citizen, "experiments", None)

        desires = [
            {
                "id": goal.id,
                "priority": round(goal.priority, 3),
                "motivation": goal.motivation,
                "horizon": goal.horizon,
            }
            for goal in getattr(state, "desires", [])[:4]
        ] if state is not None else []
        intention = getattr(state, "intention", None)
        beliefs = [
            {
                "key": belief.key,
                "confidence": round(belief.confidence, 3),
                "source": belief.source,
            }
            for belief in list(getattr(state, "beliefs", {}).values())[:8]
        ] if state is not None else []
        motivations = dict(sorted(
            getattr(state, "motivations", {}).items(),
            key=lambda item: (-item[1], item[0]),
        )) if state is not None else {}
        memories = memory.retrieve(
            current_day=self.day, limit=4
        ) if memory is not None else []
        claims = knowledge.query(
            status="validated", current_day=self.day, limit=8
        ) if knowledge is not None else []
        learned_contexts = len(getattr(learning, "contexts", {})) if learning else 0
        learned_arms = sum(
            len(arms) for arms in getattr(learning, "contexts", {}).values()
        ) if learning else 0
        active_experiment = getattr(experiments, "active", None) if experiments else None

        active_relations = []
        social = getattr(self, "social_state", {})
        for edge in social.get("relationships", {}).values():
            if (edge["source_id"] == citizen.id
                    and edge["status"] == "active"):
                active_relations.append({
                    "target_id": edge["target_id"],
                    "trust": round(edge["trust"], 3),
                })
        organizations = []
        for organization in social.get("organizations", {}).values():
            if (organization["status"] == "active"
                    and str(citizen.id) in organization["members"]):
                organizations.append({
                    "id": organization["id"],
                    "name": organization["name"],
                    "kind": organization["kind"],
                    "fund": round(organization["fund"], 2),
                })
        family_partner = self.family_partner(citizen)
        return {
            "citizen_id": citizen.id,
            "day": self.day,
            "desires": desires,
            "motivations": {
                key: round(value, 3) for key, value in motivations.items()
            },
            "beliefs": beliefs,
            "intention": (
                {
                    "goal_id": intention.goal_id,
                    "status": intention.status,
                    "step": intention.next_step,
                    "actions": list(intention.action_ids),
                }
                if intention is not None else None
            ),
            "memories": [
                {
                    "domain": item.domain,
                    "action": item.action,
                    "last_day": item.last_day,
                    "importance": round(item.importance, 3),
                }
                for item in memories
            ],
            "validated_claims": [
                {
                    "a": claim.concept_a,
                    "relation": claim.relation,
                    "b": claim.concept_b,
                    "confidence": round(claim.confidence, 3),
                }
                for claim in claims
            ],
            "learning": {
                "contexts": learned_contexts,
                "arms": learned_arms,
                "pending": getattr(learning, "pending", None) is not None,
            },
            "experiment": (
                {
                    "id": active_experiment.id,
                    "product": active_experiment.product,
                    "phase": active_experiment.phase,
                    "hypothesis": active_experiment.hypothesis,
                }
                if active_experiment is not None else None
            ),
            "social": {
                "relations": active_relations[:8],
                "organizations": organizations,
                "partner_id": family_partner.id if family_partner is not None else None,
            },
        }

    def civilization_observation(self):
        """Return aggregate observations with explicit, deterministic definitions."""
        citizens = self.citizens
        adults = [citizen for citizen in citizens if is_adult(citizen)]
        children = [citizen for citizen in citizens if not is_adult(citizen)]
        organizations = [
            item for item in getattr(self, "social_state", {}).get(
                "organizations", {}
            ).values()
            if item["status"] == "active"
        ]
        active_relations = [
            edge for edge in getattr(self, "social_state", {}).get(
                "relationships", {}
            ).values()
            if edge["status"] == "active"
        ]
        observations = sum(
            len(getattr(citizen, "knowledge", KnowledgeGraph()).observations)
            for citizen in citizens
        )
        validated_claims = sum(
            1 for citizen in citizens
            for claim in getattr(
                citizen, "knowledge", KnowledgeGraph()
            ).claims
            if claim.status == "validated"
        )
        active_experiments = sum(
            getattr(citizen, "experiments", None).active is not None
            for citizen in citizens
            if getattr(citizen, "experiments", None) is not None
        )
        wealth = sorted(citizen.networth for citizen in citizens)
        median = wealth[len(wealth) // 2] if wealth else 0.0
        productivity = (
            sum(
                max(0.0, getattr(business, "last_profit", 0.0))
                for business in self.businesses
            ) / max(1, len(self.businesses))
        )
        return {
            "day": self.day,
            "population": len(citizens),
            "adults": len(adults),
            "children": len(children),
            "unemployment": round(self.unemployment(), 6),
            "gini": round(self.gini_now(), 6),
            "median_networth": round(median, 2),
            "average_business_profit": round(productivity, 2),
            "active_organizations": len(organizations),
            "active_social_relations": len(active_relations),
            "knowledge_observations": observations,
            "validated_claims": validated_claims,
            "active_experiments": active_experiments,
        }

    # ---- fitur pemain (edit)
    @ledgered_transaction("player_cash_adjustment", "counterpart:player_intervention")
    def edit_cash(self, c, delta):
        c.cash = max(0.0, c.cash + delta)

    @ledgered_transaction("player_cash_adjustment", "counterpart:player_intervention")
    def set_cash(self, c, val):
        c.cash = max(0.0, val)

    def set_price(self, sym, val):
        a = self.market.assets[sym]
        a.price = max(1.0, val)
        a.hist.append(a.price)

    def shock(self, sym, factor):
        self.set_price(sym, self.market.assets[sym].price * factor)
        self.log("bad" if factor < 1 else "good", f"{sym} {'ANJLOK' if factor < 1 else 'MELONJAK'}",
                 f"{(factor - 1) * 100:+.0f}% oleh pemain")

    @ledgered_transaction("government_funding", "counterpart:government_funding")
    def print_money(self, amt):
        try:
            amt = float(amt)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Jumlah suntikan kas harus berupa angka terbatas.") from None
        next_treasury = self.treasury + amt
        if not math.isfinite(amt) or amt < 0 or not math.isfinite(next_treasury):
            raise ValueError("Jumlah suntikan kas harus nonnegatif dan terbatas.")
        self.treasury = next_treasury
        self.log("info", "KAS KOTA DISUNTIK", rp(amt))

    @ledgered_transaction("player_treasury_adjustment", "counterpart:player_intervention")
    def adjust_treasury(self, delta):
        try:
            delta = float(delta)
            current_treasury = float(self.treasury)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Perubahan kas kota harus berupa angka terbatas.") from None
        next_treasury = current_treasury + delta
        if (not math.isfinite(delta) or not math.isfinite(current_treasury)
                or not math.isfinite(next_treasury)):
            raise ValueError("Perubahan kas kota harus berupa angka terbatas.")
        self.treasury = max(0.0, next_treasury)
        return self.treasury

    @ledgered_transaction("player_treasury_adjustment", "counterpart:player_intervention")
    def set_treasury(self, amount):
        try:
            amount = float(amount)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Kas kota harus berupa angka terbatas.") from None
        if not math.isfinite(amount):
            raise ValueError("Kas kota harus berupa angka terbatas.")
        self.treasury = max(0.0, amount)
        return self.treasury

    # ---- kontrol pasar (pemain)
    def toggle_halt(self, sym):
        a = self.market.assets[sym]
        a.halted = not a.halted
        self.log("bad" if a.halted else "good", f"{sym} {'DIHENTIKAN' if a.halted else 'DIBUKA LAGI'}",
                 "Perdagangan dibekukan pemain" if a.halted else "Perdagangan normal kembali")

    def set_vol_mult(self, sym, m):
        self.market.assets[sym].vol_mult = round(max(0.1, min(4.0, m)), 2)

    def set_bias(self, sym, b):
        self.market.assets[sym].bias = round(max(-1.0, min(1.0, b)), 2)

    def set_sentiment(self, v):
        self.market.sent = max(-0.12, min(0.12, v))

    def push_price(self, sym, amount):
        """Dukung (+) atau tekan (-) harga lewat arus beli/jual senilai amount rupiah (berlaku besok)."""
        self.market.assets[sym].flow += amount

    def reset_market_controls(self):
        for a in self.market.assets.values():
            a.halted, a.vol_mult, a.bias = False, 1.0, 0.0
        self.market.sent = 0.0

    # ---- kontrol properti & usaha (pemain)
    def set_house_index(self, v):
        self.house_index = max(0.3, min(5.0, v))

    def set_rent_yield(self, v):
        self.rent_yield = max(0.01, min(0.3, v))

    @ledgered_transaction("player_business_adjustment", "counterpart:player_intervention")
    def edit_business_cash(self, b, delta):
        b.cash = max(0.0, b.cash + delta)
