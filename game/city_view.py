"""
city_view.py -- semua yang tampil di PETA: jalan auto-tile, lot & bangunan, props, mobil, warga,
emote bubble, teks melayang, siklus siang/malam. Murni tampilan; logika ekonomi ada di systems/ekonomi_core.py.
"""
import math
import random

import pygame

from systems.ekonomi_core import MAP_W, MAP_H, ROAD_W, rp

WALK = 62.0                  # piksel per detik
LANE = 18                    # warga berjalan di sisi luar jalan yang diperlebar
CAR_LANE = 12
CAR_COLORS = ("red", "blue", "yellow", "purple")

# kata kunci pikiran warga -> emote (urut dari yang paling spesifik)
EMOTE_RULES = (
    ("bangkrut", "crash"), ("takut rugi", "cry"), ("Di-PHK", "cry"), ("Dirumahkan", "cry"), ("Lapar", "cry"),
    ("Diusir", "angry"), ("macet", "angry"), ("ambil untung", "money"), ("Buka ", "love"), ("Beli rumah", "love"),
    ("Diterima kerja", "love"), ("tempat tinggal", "love"), ("Jual", "money"), ("nabung", "money"), ("Beli", "money"),
    ("Pensiun", "sleep"), ("nggak menarik", "confused"), ("jelek", "confused"),
)
TONE = {"cry": "negative", "angry": "negative", "crash": "negative", "money": "positive", "love": "positive",
        "sleep": "neutral", "confused": "neutral"}


def darkness(hour):
    """0 = siang terang, 1 = malam penuh."""
    if 7 <= hour < 17:
        return 0.0
    if 17 <= hour < 20.5:
        return (hour - 17) / 3.5
    if hour >= 20.5 or hour < 4.5:
        return 1.0
    return 1.0 - (hour - 4.5) / 2.5


class View:
    """Status visual satu warga (posisi, jalur jalan, animasi)."""

    def __init__(self, c, rng, assets):
        self.c = c
        self.idle, self.walk = rng.choice(assets.char[c.female])
        self.x, self.y = c.home.lot.door if c.home else (MAP_W / 2, MAP_H / 2)
        self.path = []
        self.place = None
        self.inside = True
        self.phase = rng.uniform(0, 6)
        self.lane = rng.choice((-LANE, LANE)) + rng.uniform(-1.5, 1.5)
        self.wait = 0.0
        self.moving = False
        self.emote = None            # [nama, umur, durasi]
        self.last_thought = c.thoughts[0] if c.thoughts else None
        self.prev_net = c.cash + c.savings


class Car:
    def __init__(self, rng, world):
        self.horizontal = rng.random() < 0.55
        self.dir = rng.choice((-1, 1))
        self.idx = rng.randrange(len(world.hroads if self.horizontal else world.vroads))
        self.pos = rng.uniform(0, MAP_W if self.horizontal else MAP_H)
        self.speed = rng.uniform(46, 78)
        self.color = rng.choice(CAR_COLORS)

    @property
    def heading(self):
        if self.horizontal:
            return "E" if self.dir > 0 else "W"
        return "S" if self.dir > 0 else "N"


class Floater:
    def __init__(self, surf, x, y, life=1.8, rise=26):
        self.surf, self.x, self.y, self.t, self.life, self.rise = surf, x, y, 0.0, life, rise


class CityView:
    def __init__(self, assets, world, settings):
        self.a = assets
        self.world = world
        self.opt = settings
        self.rng = random.Random(world.seed)
        self.vrng = random.Random()
        self.views = {}
        self.cars = []
        self.floaters = []
        self.seen_ev = 0
        self.prev_biz = {id(b): b for b in world.businesses}
        self.layer = 0
        self.t = 0.0
        self.props = []
        self.lamps = []
        self.mask = self._light_mask(54)
        self.dark = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        self.surf = pygame.Surface((MAP_W, MAP_H))
        self.static = self.build_static()
        self.props.sort(key=lambda p: p[0])

    # ================================================================== statis
    def build_static(self):
        w, a = self.world, self.a
        P = a.pal
        s = pygame.Surface((MAP_W, MAP_H))
        s.fill(P["E"])
        rng = random.Random(w.seed + 1)
        for _ in range(420):
            s.fill(P["e"], (rng.randrange(MAP_W), rng.randrange(MAP_H), 2, 1))
        self.draw_roads(s, rng)
        for lot in w.lots:
            self.draw_lot(s, lot, rng)
        return s

    def draw_roads(self, s, rng):
        w, a = self.world, self.a
        T = {k: a.scaled(v, 3) for k, v in a.roads.items()}
        nh, nv = len(w.hroads), len(w.vroads)
        h = ROAD_W // 2
        for j, hy in enumerate(w.hroads):
            for i, vx in enumerate(w.vroads):
                c = {d for d, ok in (("N", j > 0), ("S", j < nh - 1), ("E", i < nv - 1), ("W", i > 0)) if ok}
                if len(c) == 4:
                    name = "cross_zebra" if rng.random() < 0.45 else "cross_4way"
                elif len(c) == 3:
                    name = {"S": "tjunc_n", "N": "tjunc_s", "W": "tjunc_e", "E": "tjunc_w"}[next(iter({"N", "S", "E", "W"} - c))]
                else:
                    name = "corner_" + ("n" if "N" in c else "s") + ("e" if "E" in c else "w")
                s.blit(T[name], (vx - h, hy - h))
        # ruas horizontal (5 tile) & vertikal (3,75 tile -> tile terakhir menimpa)
        for j, hy in enumerate(w.hroads):
            for i in range(nv - 1):
                x0 = int(w.vroads[i] + h)
                x1 = int(w.vroads[i + 1] - h)
                for x in range(x0, x1, ROAD_W):
                    s.blit(T["straight_h"], (x, hy - h))
                if rng.random() < 0.6:
                    s.blit(T["zebra_h"], (x0, hy - h))
                if rng.random() < 0.6:
                    s.blit(T["zebra_h"], (x1 - ROAD_W, hy - h))
        for i, vx in enumerate(w.vroads):
            for j in range(nh - 1):
                y0 = int(w.hroads[j] + h)
                y1 = int(w.hroads[j + 1] - h)
                ys = list(range(y0, y1 - ROAD_W + 1, ROAD_W))
                if ys[-1] + ROAD_W < y1:
                    ys.append(y1 - ROAD_W)
                for y in ys:
                    s.blit(T["straight_v"], (vx - h, y))
                if rng.random() < 0.6:
                    s.blit(T["zebra_v"], (vx - h, y0))
                if rng.random() < 0.6:
                    s.blit(T["zebra_v"], (vx - h, y1 - ROAD_W))

    def draw_lot(self, s, lot, rng):
        a, P = self.a, self.a.pal
        x, y, lw, lh = (int(v) for v in lot.rect)
        top = lot.door[1] < y + lh / 2 + 0.5 and lot.door[1] <= y + 2
        ground = pygame.Rect(x + 2, y + 2, lw - 4, lh - 4)
        if lot.kind == "park":
            pygame.draw.rect(s, P["e"], ground, border_radius=4)
            pygame.draw.rect(s, P["g"], ground, 1, border_radius=4)
            for _ in range(3):
                tx = rng.randint(ground.x + 14, ground.right - 14)
                ty = rng.randint(ground.y + 24, ground.bottom - 2)
                self.props.append((ty, a.scaled(a.props["park_tree"], 2), (tx - 16, ty - 32)))
            bx = ground.centerx + rng.choice((-16, 16))
            by = ground.centery + rng.randint(4, 14)
            self.props.append((by + 16, a.scaled(a.props["park_bench"], 2), (bx - 16, by - 16)))
            return
        pygame.draw.rect(s, P["C"] if lot.kind in ("hall", "exchange") else P["c"], ground, border_radius=3)
        pygame.draw.rect(s, P["K"], ground, 1, border_radius=3)
        # jalan setapak + keset pintu menuju jalan
        cx = int(lot.door[0])
        walk_y = y if top else y + lh - 9
        pygame.draw.rect(s, P["y"], (cx - 4, walk_y, 8, 9))
        pygame.draw.rect(s, P["D"], (cx - 3, y + 1 if top else y + lh - 4, 6, 3))
        bx, by = x + (lw - 64) // 2, y + (lh - 52) // 2
        if lot.kind == "house":
            pygame.draw.rect(s, (190, 184, 166), (bx + 3, by + 4, 64, 52))
            s.blit(a.building(f"house_{lot.building.color_i}", flip=(lot.building.color_i + int(x)) % 2 == 0), (bx, by))
            self.label(s, "APARTEMEN", (bx + 32, by + 24), 1)
        elif lot.kind in ("hall", "exchange"):
            pygame.draw.rect(s, (190, 184, 166), (bx + 3, by + 4, 64, 52))
            s.blit(a.building(lot.kind), (bx, by))
            self.label(s, "BALAI" if lot.kind == "hall" else "BURSA", (bx + 32, by + 24), 1)

    def label(self, surf, txt, center, scale=1):
        t = self.a.font.render(txt, scale)
        bg = pygame.Rect(0, 0, t.get_width() + 8, t.get_height() + 4)
        bg.center = center
        pygame.draw.rect(surf, (30, 27, 46), bg, border_radius=3)
        surf.blit(t, (bg.x + 4, bg.y + 2))

    def _lamp_positions(self):
        """Lampu jalan & halte di tepi atas tiap blok, hidran di sudut."""
        w, a = self.world, self.a
        out = []
        nb = 0
        for i in range(len(w.vroads) - 1):
            for j in range(len(w.hroads) - 1):
                x0 = w.vroads[i] + ROAD_W // 2
                y0 = w.hroads[j] + ROAD_W // 2
                bw = w.vroads[i + 1] - w.vroads[i] - ROAD_W
                bh = w.hroads[j + 1] - w.hroads[j] - ROAD_W
                kind = "bus" if (i + j) % 4 == 1 else "lamp"
                out.append((kind, x0 + bw / 2, y0 + 3))
                if (i * 3 + j) % 3 == 0:
                    out.append(("lamp", x0 + bw / 2, y0 + bh + 2))
                if (i + 2 * j) % 3 == 0:
                    out.append(("hydrant", x0 + 4, y0 + 4))
        return out

    # ================================================================== warga
    def route(self, p, q, lane):
        w = self.world
        ya = min(w.hroads, key=lambda y: abs(y - p[1])) + lane
        yb = min(w.hroads, key=lambda y: abs(y - q[1])) + lane
        pts = [(p[0], ya)]
        if abs(ya - yb) > 1:
            xv = min(w.vroads, key=lambda x: abs(x - (p[0] + q[0]) / 2)) + lane
            pts += [(xv, ya), (xv, yb)]
        pts += [(q[0], yb), q]
        return pts

    def desired_place(self, c):
        h = self.world.hour
        works = c.job is not None or c.business is not None
        if c.home is None:
            return "wander"
        if 6.5 <= h < 8.0:
            return "work" if works else "wander"
        if 8.0 <= h < 16.5:
            return "work" if works else ("wander" if c.id % 3 == 0 else "home")
        if 16.5 <= h < 17.5:
            return "shop"
        if 17.5 <= h < 21.0:
            return "wander" if c.id % 2 == 0 else "home"
        return "home"

    def nearest_shop(self, c):
        shops = [b for b in self.world.businesses if b.kind == "shop"]
        if not shops:
            return None
        hx, hy = c.home.lot.door if c.home else (MAP_W / 2, MAP_H / 2)
        return min(shops, key=lambda b: (b.lot.door[0] - hx) ** 2 + (b.lot.door[1] - hy) ** 2)

    def target_point(self, c, v, place):
        w = self.world
        if place == "home" and c.home:
            return c.home.lot.door
        if place == "work":
            wp = c.job or c.business
            if wp:
                return wp.lot.door
        if place == "shop":
            s = self.nearest_shop(c)
            if s:
                return s.lot.door
        y = self.vrng.choice(w.hroads) + v.lane
        return (self.vrng.uniform(30, MAP_W - 30), y)

    def update(self, dt, speed):
        w = self.world
        self.t += dt
        alive = {c.id for c in w.citizens}
        for cid in list(self.views):
            if cid not in alive:
                del self.views[cid]
        for c in w.citizens:
            v = self.views.get(c.id)
            if v is None:
                v = self.views[c.id] = View(c, self.vrng, self.a)
            if speed:
                self.move(v, c, dt, speed)
                self.mood(v, c, dt, speed)
        self.update_cars(dt, speed)
        self.watch_world(speed)
        for f in self.floaters:
            f.t += dt
        self.floaters = [f for f in self.floaters if f.t < f.life]

    def move(self, v, c, dt, speed):
        place = self.desired_place(c)
        if place == "shop" and self.nearest_shop(c) is None:
            place = "wander"
        if place != v.place:
            v.place = place
            v.inside = False
            tgt = self.target_point(c, v, place)
            v.path = self.route((v.x, v.y), tgt, v.lane)
            v.wait = 0
        if speed >= 30 and v.path:
            v.x, v.y = v.path[-1]
            v.path = []
        if v.path:
            step = WALK * dt * min(max(speed, 1.0), 6.0)
            while step > 0 and v.path:
                tx, ty = v.path[0]
                dx, dy = tx - v.x, ty - v.y
                d = math.hypot(dx, dy)
                if d <= step:
                    v.x, v.y = tx, ty
                    step -= d
                    v.path.pop(0)
                else:
                    v.x += dx / d * step
                    v.y += dy / d * step
                    step = 0
            v.moving = True
            v.phase += dt * 11
        else:
            v.moving = False
            if place in ("home", "work", "shop"):
                v.inside = True
            else:
                v.inside = False
                v.wait -= dt
                if v.wait <= 0:
                    tgt = self.target_point(c, v, "wander")
                    v.path = self.route((v.x, v.y), tgt, v.lane)
                    v.wait = self.vrng.uniform(1, 4)

    def mood(self, v, c, dt, speed):
        """Emote dari pikiran terbaru + teks melayang dari perubahan uang."""
        th = c.thoughts[0] if c.thoughts else None
        if th is not v.last_thought:
            v.last_thought = th
            if th and self.opt.emotes and speed <= 3:
                for key, name in EMOTE_RULES:
                    if key in th[1]:
                        v.emote = [name, 0.0, 3.6]
                        break
        if v.emote and not v.inside:
            v.emote[1] += dt
            if v.emote[1] > v.emote[2]:
                v.emote = None
        net = c.cash + c.savings
        delta = net - v.prev_net
        v.prev_net = net
        if self.opt.floaters and speed <= 3 and not v.inside and abs(delta) >= 1_000_000 and len(self.floaters) < 14:
            txt = ("+" if delta > 0 else "-") + rp(abs(delta)).replace("Rp", "")
            self.pop_text(txt, v.x, v.y - 34, (110, 214, 150) if delta > 0 else (246, 120, 120), life=1.5)

    def update_cars(self, dt, speed):
        if not self.opt.cars or speed == 0:
            return
        k = min(max(speed, 1.0), 3.0)
        for car in self.cars:
            length = MAP_W if car.horizontal else MAP_H
            ahead = min((((o.pos - car.pos) * car.dir) % length for o in self.cars
                         if o is not car and o.horizontal == car.horizontal and o.idx == car.idx and o.dir == car.dir),
                        default=999)
            sp = car.speed * (0.25 if ahead < 40 else 1.0)
            car.pos += car.dir * sp * dt * k
            if car.pos > length + 40:
                car.pos = -40
            elif car.pos < -40:
                car.pos = length + 40

    # ================================================================== efek
    def pop_text(self, txt, x, y, tint, life=1.6):
        surf = self.a.font.render(txt, 1, tint).copy()
        self.floaters.append(Floater(surf, x, y, life))

    def pop_label(self, name, x, y, life=2.2):
        if self.opt.floaters:
            surf = pygame.transform.scale(self.a.labels[name], (self.a.labels[name].get_width() * 2, self.a.labels[name].get_height() * 2))
            self.floaters.append(Floater(surf, x, y, life, 34))

    def watch_world(self, speed):
        """Pantau event dunia -> label melayang di lokasi yang pas."""
        w = self.world
        cur = {id(b): b for b in w.businesses}
        for k, b in cur.items():
            if k not in self.prev_biz and speed <= 10:
                self.pop_label("level_up", *b.lot.door)
        for k, b in self.prev_biz.items():
            if k not in cur and speed <= 10:
                self.pop_label("crash_alert", *b.lot.door)
        self.prev_biz = cur
        hx, hy = w.hall.lot.door
        ex, ey = w.exchange_lot.door
        for e in [e for e in w.events if e[0] > self.seen_ev]:
            self.seen_ev = e[0]
            title = e[2]
            if "MELONJAK" in title or "DIBUKA LAGI" in title:
                self.pop_label("boom_alert", ex, ey - 6)
            elif "ANJLOK" in title:
                self.pop_label("crash_alert", ex, ey - 6)
            elif "DIHENTIKAN" in title:
                self.pop_text("HALT!", ex, ey - 12, (246, 120, 120), 2.4)
            elif title.startswith("TAHUN"):
                self.pop_label("tax_alert", hx, hy - 6)
            elif "DISUNTIK" in title:
                self.pop_text("+" + e[3].replace("Rp", ""), hx, hy - 12, (110, 214, 150), 2.4)

    # ================================================================== gambar
    def pick_citizen(self, pos):
        best, bd = None, 16
        for v in self.views.values():
            if v.inside:
                continue
            d = math.hypot(pos[0] - v.x, pos[1] - (v.y - 12))
            if d < bd:
                best, bd = v.c, d
        return best

    def lot_at(self, pos):
        for lot in self.world.lots:
            x, y, lw, lh = lot.rect
            if x <= pos[0] < x + lw and y <= pos[1] < y + lh:
                return lot
        return None

    @staticmethod
    def sprite_pos(lot):
        x, y, lw, lh = lot.rect
        return int(x + (lw - 64) // 2), int(y + (lh - 52) // 2)

    def draw_business(self, s, b):
        a = self.a
        bx, by = self.sprite_pos(b.lot)
        pygame.draw.rect(s, (190, 184, 166), (bx + 3, by + 4, 64, 52))
        sprite = a.building("shop" if b.kind in ("shop", "showroom") else "factory")
        if b.kind == "farm":
            sprite = sprite.copy()
            sprite.fill((145, 210, 135, 255), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(sprite, (bx, by))
        labels = {"shop": "TOKO", "factory": "PABRIK", "farm": "KEBUN",
                  "showroom": "MOBIL", "car_factory": "PABRIK MOBIL",
                  "builder": "BANGUNAN", "repair": "SERVIS",
                  "delivery": "ANTAR", "cleaning": "KEBERSIHAN"}
        self.label(s, labels[b.kind], (bx + 32, by + 26))
        f = (min(1.0, b.car_stock / 3) if b.kind in ("showroom", "car_factory")
             else (min(1.0, b.stock / 30) if b.kind == "shop" else min(1.0, b.stock / max(b.prod * 6, 1))))
        top = b.lot.door[1] < b.lot.rect[1] + 3
        bar = pygame.Rect(bx, by + 53 if top else by - 5, 64, 3)
        pygame.draw.rect(s, (30, 27, 46), bar.inflate(2, 2))
        pygame.draw.rect(s, a.pal["G"] if f > 0.15 else a.pal["R"], (bar.x, bar.y, int(bar.w * f), 3))

    def draw_layer(self, s):
        w = self.world
        if self.layer == 1:
            nws = []
            for h in w.houses:
                nws.append(sum(o.networth for o in h.occupants) / len(h.occupants) if h.occupants else None)
            vals = sorted(v for v in nws if v is not None)
            for h, v in zip(w.houses, nws):
                col = (120, 120, 140, 110)
                if v is not None and len(vals) > 1:
                    t = vals.index(v) / (len(vals) - 1)
                    col = (int(240 - 190 * t), int(80 + 140 * t), 90, 150)
                self.tint_lot(s, h.lot, col)
        elif self.layer == 2:
            for h in w.houses:
                self.tint_lot(s, h.lot, (40, 40, 70, 90))
            for b in w.businesses:
                self.tint_lot(s, b.lot, (70, 200, 110, 160) if b.last_profit > 0 else (230, 80, 80, 160) if b.last_profit < 0 else (200, 200, 120, 140))

    def tint_lot(self, s, lot, rgba):
        x, y, lw, lh = (int(v) for v in lot.rect)
        t = pygame.Surface((lw - 4, lh - 4), pygame.SRCALPHA)
        t.fill(rgba)
        s.blit(t, (x + 2, y + 2))

    def draw(self, sel=None, hover=None, focus_lot=None):
        s = self.surf
        a = self.a
        w = self.world
        s.blit(self.static, (0, 0))
        self.draw_layer(s)
        for b in w.businesses:
            self.draw_business(s, b)
        night = darkness(w.hour) if self.opt.day_night else 0.0
        ents = [(p[0], 0, p) for p in self.props]
        for ln, lx, ly in self._lamp_cache():
            if ln == "hydrant":
                ss = a.scaled(a.props["fire_hydrant"], 1)
            elif ln == "bus":
                ss = a.scaled(a.props["bus_stop"], 2)
            else:
                ss = a.scaled(a.props["streetlight_night" if night > 0.35 else "streetlight_day"], 2)
            ents.append((ly + 4, 0, (0, ss, (lx - ss.get_width() // 2, ly + 4 - ss.get_height()))))
        if self.opt.cars:
            for citizen in w.citizens:
                color = getattr(citizen, "vehicle_color", None)
                v = self.views.get(citizen.id)
                if color and v and not v.inside:
                    spr = a.car(color, "E")
                    ents.append((v.y + 2, 1, (spr, v.x - spr.get_width() / 2, v.y - spr.get_height() / 2)))
        for v in self.views.values():
            if not v.inside:
                ents.append((v.y, 2, v))
        ents.sort(key=lambda e: e[0])
        for _, kind, d in ents:
            if kind == 0:
                s.blit(d[1], d[2])
            elif kind == 1:
                s.blit(d[0], (d[1], d[2]))
            else:
                self.draw_person(s, d, sel)
        if focus_lot is not None:
            self.pulse(s, focus_lot, (255, 214, 90))
        if sel is not None:
            self.mark_selection(s, sel)
        if night > 0:
            self.draw_night(s, night)
        for v in self.views.values():
            if not v.inside and v.emote and self.opt.emotes:
                self.draw_emote(s, v)
        for f in self.floaters:
            p = f.t / f.life
            img = f.surf
            img.set_alpha(255 if p < 0.65 else int(255 * (1 - p) / 0.35))
            ease = 1 - (1 - min(1.0, p * 1.4)) ** 2
            s.blit(img, (int(f.x - img.get_width() / 2), int(f.y - f.rise * ease)))
        for v in self.views.values():
            if not v.inside and (v.c is sel or v.c is hover or self.opt.names):
                self.draw_tag(s, v, v.c is sel or v.c is hover)
        return s

    def _lamp_cache(self):
        if not hasattr(self, "_lamps"):
            self._lamps = self._lamp_positions()
        return self._lamps

    def draw_person(self, s, v, sel):
        bob = -abs(math.sin(v.phase)) * 3 if v.moving else 0
        sprite = v.walk[int(v.phase) % 3] if v.moving else v.idle
        sh = pygame.Surface((18, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (30, 27, 46, 70), (0, 0, 18, 6))
        s.blit(sh, (v.x - 9, v.y - 3))
        s.blit(sprite, (int(v.x - sprite.get_width() / 2), int(v.y - sprite.get_height() + bob)))
        if v.c is sel:
            pygame.draw.ellipse(s, (255, 214, 90), (v.x - 12, v.y - 6, 24, 11), 2)

    def draw_emote(self, s, v):
        name, age, dur = v.emote
        em = self.a.emotes[name]
        tone = self.a.bubbles[TONE[name]]
        if age < 0.30:
            frame = tone[min(2, int(age / 0.10))]
        else:
            frame = em["composed"][int((age - 0.30) * 5) % 4]
        fade = 1.0 if age < dur - 0.4 else max(0.0, (dur - age) / 0.4)
        frame = frame.copy() if fade < 1 else frame
        if fade < 1:
            frame.set_alpha(int(255 * fade))
        s.blit(frame, (int(v.x - frame.get_width() / 2), int(v.y - 28 - frame.get_height() - (2 if age < 0.3 else 0))))

    def draw_tag(self, s, v, full):
        c = v.c
        ui_font = self.a.font
        name = ui_font.render(c.first, 1)
        if full:
            money = ui_font.render(rp(c.cash + c.savings).replace("Rp", ""), 1, (150, 240, 180))
            w = name.get_width() + money.get_width() + 18
        else:
            money = None
            w = name.get_width() + 10
        r = pygame.Rect(0, 0, w, 15)
        r.midbottom = (int(v.x), int(v.y - 30 - (20 if v.emote and not v.inside else 0)))
        r.clamp_ip(pygame.Rect(0, 0, MAP_W, MAP_H))
        pygame.draw.rect(s, (30, 27, 46), r, border_radius=3)
        s.blit(name, (r.x + 5, r.y + 3))
        if money:
            s.blit(money, (r.x + 11 + name.get_width(), r.y + 3))

    def pulse(self, s, lot, color):
        x, y, lw, lh = (int(v) for v in lot.rect)
        g = 2 + int(2 * (0.5 + 0.5 * math.sin(self.t * 7)))
        pygame.draw.rect(s, color, (x - g + 2, y - g + 2, lw + 2 * g - 4, lh + 2 * g - 4), 2, border_radius=5)

    def mark_selection(self, s, c):
        pairs = []
        if c.home:
            pairs.append((c.home.lot, "RUMAH", (110, 190, 255)))
        wp = c.job or c.business
        if wp:
            pairs.append((wp.lot, "KERJA", (255, 176, 80)))
        for lot, text, col in pairs:
            self.pulse(s, lot, col)
            x, y, lw, lh = lot.rect
            self.label(s, text, (int(x + lw / 2), int(y + 6)))

    # ---- malam
    def _light_mask(self, r):
        m = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(r, 0, -2):
            pygame.draw.circle(m, (0, 0, 0, int(210 * (1 - i / r) ** 1.4)), (r, r), i)
        return m

    def draw_night(self, s, night):
        d = self.dark
        d.fill((16, 18, 58, int(140 * night)))
        if night > 0.35:
            for ln, lx, ly in self._lamp_cache():
                if ln == "lamp":
                    d.blit(self.mask, (int(lx) - 54, int(ly) - 30), special_flags=pygame.BLEND_RGBA_SUB)
        s.blit(d, (0, 0))
