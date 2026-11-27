"""
scene_game.py -- layar utama permainan: peta + HUD atas + panel kanan + dock bawah + jendela (pasar, makro, ...).
"""
import pygame

from systems.ekonomi_core import DPY, MAX_POP, rp, MAP_W, MAP_H
from game.city_view import CityView
from game import windows
from game.ui import (INK, CREAM, CREAM2, MUTED, GREEN, RED, BLUE, GOLD, WHITE, SOFT_G, SOFT_R, SOFT_B, SOFT_Y,
                     parse_money)

W, H = 1280, 720
TOP, BOT = 36, 44
MAP_VIEW_W, MAP_VIEW_H = 992, H - TOP - BOT
MAPR = pygame.Rect(0, TOP, MAP_VIEW_W, MAP_VIEW_H)
SIDE = pygame.Rect(MAP_VIEW_W, TOP, W - MAP_VIEW_W, MAP_VIEW_H)
WIN = pygame.Rect(16, 44, 960, 624)
SPEEDS = [0, 1, 2, 5, 10, 100]
SPEED_LABELS = ["PAU", "1x", "2x", "5x", "10x", "100x"]
SIM_HOURS_PER_SECOND = 1 / 6
TABS = ["KOTA", "WARGA", "BERITA"]
LAYERS = ["NORMAL", "KEKAYAAN", "USAHA"]
CITY_NAME = "RUPIAHVILLE"
WINDOWS = {
    "market": ("BURSA EFEK", "market", windows.market_window),
    "macro": ("DASBOR MAKRO", "macro", windows.macro_window),
    "policy": ("KEBIJAKAN KOTA", "policy", windows.policy_window),
    "biz": ("DAFTAR USAHA", "business", windows.biz_window),
    "house": ("PASAR PROPERTI", "house", windows.house_window),
}


class GameScene:
    def __init__(self, app, world):
        self.app = app
        self.ui = app.ui
        self.a = app.assets
        self.opt = app.settings
        self.world = world
        self.cv = CityView(self.a, world, self.opt)
        map_w = max(world.vroads) + 24 if world.vroads else MAP_W
        map_h = max(world.hroads) + 24 if world.hroads else MAP_H
        self.map_w, self.map_h = max(MAPR.w, map_w), max(MAPR.h, map_h)
        self.camera_x = max(0, (self.map_w - MAPR.w) // 2)
        self.camera_y = max(0, (self.map_h - MAPR.h) // 2)
        self.pan_anchor = None
        self.speed_i = 1
        self.tab = 0
        self.sel = None
        self.people_query = ""
        self.people_search_focus = False
        self.people_search_rect = None
        self.window = None
        self.ws = {}
        self.sel_biz = None
        self.sel_house = None
        self.focus_lot = None
        self.focus_until = 0.0
        self.metric_i = 0
        self.prompt = None
        self.menu_open = False
        self.menu_page = "main"
        self.toast = None
        self.toast_t = 0.0
        self.seen_ev = world.events[-1][0] if world.events else 0
        self.hover = None
        self.hover_lot = None
        self.note = None            # pesan singkat (mis. "TERSIMPAN")
        self.note_t = 0.0

    # ================================================================== aksi
    def select_citizen(self, c):
        self.sel = c
        self.tab = 1

    def open_window(self, name):
        self.window = None if self.window == name else name

    def close_window(self):
        self.window = None

    def open_prompt(self, title, cb):
        self.prompt = {"title": title, "text": "", "cb": cb}

    def say(self, text):
        self.note, self.note_t = text, 2.5

    def set_speed(self, i):
        self.speed_i = i

    def cycle_layer(self):
        self.cv.layer = (self.cv.layer + 1) % len(LAYERS)

    def pan_to(self, x, y):
        self.camera_x = max(0, min(self.map_w - MAPR.w, x))
        self.camera_y = max(0, min(self.map_h - MAPR.h, y))

    def pan_by(self, dx, dy):
        self.pan_to(self.camera_x + dx, self.camera_y + dy)

    # ================================================================== update
    def update(self, dt):
        speed = SPEEDS[self.speed_i]
        paused = bool(self.prompt) or self.menu_open
        if speed and not paused:
            self.world.advance(dt * SIM_HOURS_PER_SECOND * speed)
        self.cv.update(dt, 0 if paused else speed)
        self.update_toast(dt)
        if self.note:
            self.note_t -= dt
            if self.note_t <= 0:
                self.note = None
        if self.focus_lot is not None and self.cv.t > self.focus_until:
            self.focus_lot = None
        self.hover = self.hover_lot = None
        mp = pygame.mouse.get_pos()
        if MAPR.collidepoint(mp) and not self.menu_open and not (self.window and WIN.collidepoint(mp)):
            lp = (mp[0] - MAPR.x + self.camera_x, mp[1] - MAPR.y + self.camera_y)
            self.hover = self.cv.pick_citizen(lp)
            self.hover_lot = self.cv.lot_at(lp)
        if self.focus_lot is not None and self.cv.t <= self.focus_until:
            x, y, lw, lh = self.focus_lot.rect
            self.camera_x = max(0, min(self.map_w - MAPR.w, int(x + lw / 2 - MAPR.w / 2)))
            self.camera_y = max(0, min(self.map_h - MAPR.h, int(y + lh / 2 - MAPR.h / 2)))

    def update_toast(self, dt):
        fresh = [e for e in self.world.events if e[0] > self.seen_ev]
        if fresh:
            self.seen_ev = fresh[-1][0]
            pri = [e for e in fresh if e[1] != "info"] or fresh
            e = pri[-1]
            if self.toast is None or self.toast_t > 1.0 or e[1] != "info":
                self.toast = (e[1], e[2], e[3])
                self.toast_t = 0.0
        if self.toast:
            self.toast_t += dt
            if self.toast_t > 5:
                self.toast = None

    # ================================================================== gambar
    def draw(self, screen):
        ui = self.ui
        ui.begin(screen)
        screen.fill((30, 27, 46))
        focus = None
        if self.window == "biz" and self.sel_biz:
            focus = self.sel_biz.lot
        elif self.window == "house" and self.sel_house:
            focus = self.sel_house.lot
        elif self.focus_lot is not None:
            focus = self.focus_lot
        surf = self.cv.draw(self.sel, self.hover, focus)
        screen.blit(surf, MAPR.topleft, pygame.Rect(self.camera_x, self.camera_y, MAPR.w, MAPR.h))
        if self.cv.t < 14 and not self.window:
            hint = pygame.Rect(MAPR.x + 10, MAPR.bottom - 30, 256, 22)
            ui.panel(hint, "dark", 1)
            ui.text("SERET PETA · PANAH · SHIFT+RODA", (hint.x + 6, hint.y + 5), WHITE, "xs")
        if self.cv.layer:
            self.draw_layer_legend()
        self.draw_side()
        self.draw_top()
        self.draw_bottom()
        if self.window:
            self.draw_window()
        self.draw_toast()
        if self.hover_lot is not None and not self.window and not self.menu_open and not ui.tip:
            tip = self.lot_tip(self.hover_lot)
            if tip:
                ui.tip = tip
        if self.menu_open:
            self.app.draw_pause(self)
        if self.prompt:
            self.draw_prompt()
        ui.end()

    # ---- HUD atas
    def draw_top(self):
        ui, a, w = self.ui, self.a, self.world
        ui.panel((0, 0, W, TOP), "dark", 1)
        ui.bmp(CITY_NAME, (12, 10), 2, CREAM)
        x = 206
        sun = 6 <= w.hour < 18
        ui.sprite(a.menu["hud_day_sun" if sun else "hud_night_moon"], (x, 6), 2)
        hh, mm = int(w.hour), int((w.hour % 1) * 60)
        ui.bmp(f"TAHUN {w.year} HARI {w.day % DPY + 1}", (x + 32, 7), 1, WHITE)
        ui.bmp(f"{hh:02d}:{mm:02d}", (x + 32, 20), 1, SOFT_Y)
        ihk = w.series["ihk"][-1] if w.series["ihk"] else 100
        ih = list(w.series["ihk"])
        ihk_ch = (ih[-1] / ih[-min(len(ih), 7)] - 1) if len(ih) > 1 else 0
        items = [
            (372, "hud_cash", "KAS KOTA", rp(w.treasury), SOFT_G, None),
            (532, "hud_pop", "WARGA", str(len(w.citizens)), WHITE, None),
            (632, "hud_inflation", "IHK", f"{ihk:.0f}", WHITE, ihk_ch),
            (742, None, "NGANGGUR", f"{w.unemployment() * 100:.0f}%", SOFT_R if w.unemployment() > 0.25 else WHITE, None),
        ]
        for x, icon, label, val, col, tr in items:
            tx = x
            if icon:
                ui.sprite(a.menu[icon], (x, 6), 2)
                tx = x + 30
            ui.bmp(label, (tx, 7), 1, (170, 172, 196))
            n = ui.bmp(val, (tx, 20), 1, col)
            if tr is not None:
                windows.trend_icon(self, tr, (tx + n + 6, 18), 1, 0.001)
        x0 = W - len(SPEEDS) * 44 - 8
        for i, label in enumerate(SPEED_LABELS):
            active = self.speed_i == i
            ui.button((x0 + i * 44, 2, 42, 32), label, lambda i=i: self.set_speed(i),
                      "new_city" if active else "load_seed", 1,
                      tip="Jeda (SPASI)" if i == 0 else f"{SPEEDS[i]}x (tombol {i})")

    # ---- dock bawah
    def draw_bottom(self):
        ui, a = self.ui, self.a
        ui.panel((0, H - BOT, W, BOT), "dark", 1)
        items = [
            ("inspect", "Warga (W)", lambda: setattr(self, "tab", 1), self.tab == 1 and not self.window),
            ("business", "Usaha (B)", lambda: self.open_window("biz"), self.window == "biz"),
            ("house", "Properti (R)", lambda: self.open_window("house"), self.window == "house"),
            ("road", f"Layer peta: {LAYERS[self.cv.layer]} (L)", self.cycle_layer, self.cv.layer > 0),
            ("bulldoze", "Berita (N)", lambda: setattr(self, "tab", 2), self.tab == 2 and not self.window),
            ("market", "Bursa Efek / Pasar saham (P)", lambda: self.open_window("market"), self.window == "market"),
            ("macro", "Dasbor ekonomi makro (E)", lambda: self.open_window("macro"), self.window == "macro"),
            ("policy", "Kebijakan & pajak (K)", lambda: self.open_window("policy"), self.window == "policy"),
            ("menu", "Menu (ESC)", lambda: setattr(self, "menu_open", True), False),
        ]
        x = 12
        for key, tip, cb, active in items:
            ui.dock_button((x, H - BOT + 1), a.dock[key], cb, tip, active, 3)
            x += 50
            if key in ("bulldoze",):
                pygame.draw.line(ui.screen, (110, 106, 150), (x - 2, H - BOT + 8), (x - 2, H - 8), 2)
                x += 6
        # ticker berita
        w = self.world
        if w.events:
            _, kind, title, sub = w.events[-1]
            icon = {"good": "trend_up", "bad": "alert_icon", "info": "trend_flat"}[kind]
            tx = x + 16
            ui.sprite(a.chart[icon], (tx, H - BOT + 14), 2)
            ui.bmp(title[:44], (tx + 26, H - BOT + 10), 1, WHITE)
            ui.text(sub[:70], (tx + 26, H - BOT + 24), (170, 172, 196), "xs")
        ui.bmp(f"SEED {w.seed}", (W - 12, H - BOT + 8), 1, (170, 172, 196), "r")
        if self.note:
            ui.bmp(self.note, (W - 12, H - BOT + 24), 1, SOFT_Y, "r")
        else:
            ui.bmp(f"LAYER {LAYERS[self.cv.layer]}", (W - 12, H - BOT + 24), 1, (120, 122, 150), "r")

    def draw_layer_legend(self):
        ui = self.ui
        r = pygame.Rect(MAPR.x + 10, MAPR.bottom - 30, 250, 22)
        ui.panel(r, "dark", 1)
        txt = {1: "LAYER KEKAYAAN: MERAH MISKIN - HIJAU KAYA", 2: "LAYER USAHA: HIJAU UNTUNG - MERAH RUGI"}[self.cv.layer]
        ui.bmp(txt[:30], (r.x + 8, r.y + 6), 1, WHITE)

    def draw_toast(self):
        if not self.toast or self.window:
            return
        ui = self.ui
        kind, title, sub = self.toast
        col = {"good": GOLD, "bad": RED, "info": BLUE}[kind]
        tw = max(ui.a.font.width(title), ui.f["s"].size(sub)[0]) + 90
        x = (MAPR.w - tw) // 2
        r = pygame.Rect(x, TOP + 8, tw, 54)
        ui.shadow_panel(r, "cream")
        pygame.draw.rect(ui.screen, col, (r.x + 8, r.y + 8, 38, 38), border_radius=4)
        ui.bmp({"good": "+", "bad": "!", "info": "?"}[kind], (r.x + 27, r.y + 16), 2, None, "c")
        ui.bmp(title, (r.x + 58, r.y + 10), 1, INK)
        ui.text(sub, (r.x + 58, r.y + 28), MUTED, "s")

    # ---- jendela
    def draw_window(self):
        ui, a = self.ui, self.a
        title, icon, fn = WINDOWS[self.window]
        r = WIN
        start = len(ui.hits)
        ui.shadow_panel(r, "cream")
        ui.panel((r.x + 8, r.y + 8, r.w - 16, 34), "dark", 1)
        ui.sprite(a.dock[icon], (r.x + 14, r.y + 11), 2)
        ui.bmp(title, (r.x + 52, r.y + 17), 2, CREAM)
        ui.button((r.right - 54, r.y + 11, 38, 28), "X", self.close_window, "exit", 1, tip="Tutup (ESC)")
        C = pygame.Rect(r.x + 14, r.y + 52, r.w - 28, r.h - 64)
        fn(self, C)
        ui.hits.insert(start, (r, lambda p: None))   # klik di jendela tidak tembus ke peta

    # ---- panel kanan
    def draw_side(self):
        ui = self.ui
        ui.panel(SIDE, "cream")
        tw = (SIDE.w - 24) // 3
        for i, name in enumerate(TABS):
            ui.button((SIDE.x + 10 + i * (tw + 2), SIDE.y + 8, tw, 28), name, lambda i=i: setattr(self, "tab", i),
                      "new_city" if self.tab == i else "load_seed", 1)
        [self.tab_city, self.tab_people, self.tab_news][self.tab](pygame.Rect(SIDE.x + 14, SIDE.y + 46, SIDE.w - 28, SIDE.h - 58))

    def tab_city(self, A):
        ui, w = self.ui, self.world
        cs = w.citizens
        avg = sum(c.cash + c.savings for c in cs) / max(1, len(cs))
        fac = sum(1 for b in w.businesses if b.kind in ("factory", "car_factory", "builder"))
        farm = sum(1 for b in w.businesses if b.kind == "farm")
        sh = sum(1 for b in w.businesses if b.kind == "shop")
        dealers = sum(1 for b in w.businesses if b.kind == "showroom")
        services = sum(1 for b in w.businesses
                       if b.kind in ("repair", "delivery", "cleaning"))
        occ = sum(len(h.occupants) for h in w.houses) / max(1, sum(h.cap for h in w.houses))
        unemployment = w.unemployment()
        ui.bmp("STATUS KOTA", (A.x, A.y), 1, INK)
        ui.text(f"HARI {w.day % DPY + 1} · TAHUN {w.year}", (A.right, A.y), MUTED, "xs", "r")
        y = A.y + 20
        gap, card_h = 6, 39
        card_w = (A.w - gap) // 2
        cards = [
            ("WARGA", f"{len(cs)} / {MAX_POP}", BLUE),
            ("PENGANGGURAN", f"{unemployment:.0%}", RED if unemployment > 0.25 else GREEN),
            ("UANG RATA-RATA", rp(avg), BLUE),
            ("GINI", f"{w.gini_now():.2f}", GOLD),
        ]
        for i, (label, value, color) in enumerate(cards):
            col, row = i % 2, i // 2
            card = pygame.Rect(A.x + col * (card_w + gap), y + row * (card_h + 4), card_w, card_h)
            pygame.draw.rect(ui.screen, CREAM2, card, border_radius=4)
            pygame.draw.rect(ui.screen, MUTED, card, 1, border_radius=4)
            ui.text(label, (card.x + 6, card.y + 4), MUTED, "xs")
            ui.text(value, (card.x + 6, card.y + 18), color, "m")

        y += 2 * card_h + 12
        finance = pygame.Rect(A.x, y, A.w, 78)
        ui.panel(finance, "dark", 1)
        ui.bmp("KEUANGAN KOTA", (finance.x + 8, finance.y + 6), 1, SOFT_Y)
        finance_rows = (
            ("Kas pemerintah", rp(w.treasury), WHITE),
            ("Modal bank", rp(w.bank.equity), SOFT_R if w.bank.equity < 0 else SOFT_G),
            ("Simpanan warga", rp(w.bank.deposits), WHITE),
            ("Pinjaman bank", rp(w.bank.loan_book), WHITE),
        )
        for i, (label, value, color) in enumerate(finance_rows):
            col, row = i % 2, i // 2
            cx, cy = finance.x + 8 + col * (finance.w // 2), finance.y + 23 + row * 25
            ui.text(label, (cx, cy), (190, 192, 214), "xs")
            ui.text(value, (cx, cy + 10), color, "xs")

        y = finance.bottom + 8
        economy = pygame.Rect(A.x, y, A.w, 46)
        pygame.draw.rect(ui.screen, CREAM2, economy, border_radius=4)
        pygame.draw.rect(ui.screen, MUTED, economy, 1, border_radius=4)
        ui.text("USAHA BERJALAN", (economy.x + 6, economy.y + 4), MUTED, "xs")
        ui.text(f"Kebun {farm} · Toko {sh} · Pabrik/bangun {fac}",
                (economy.x + 6, economy.y + 16), INK, "xs")
        ui.text(f"Dealer {dealers} · Jasa {services} · Hunian {occ:.0%}",
                (economy.x + 6, economy.y + 30), MUTED, "xs")
        y = economy.bottom + 8
        metrics = [("uang", "Rata2 uang", BLUE), ("kekayaan", "Kekayaan median", (110, 214, 150)),
                   ("nganggur", "Pengangguran %", (246, 120, 120)), ("gini", "Gini", (255, 190, 90)),
                   ("ihk", "IHK", (200, 150, 240)), ("pdb", "PDB 30 hari", (110, 214, 214)),
                   ("kas_kota", "Kas Kota", (255, 214, 90)), ("penduduk", "Penduduk", (240, 240, 240)),
                   ("emosi", "Kepuasan warga", (250, 170, 110)),
                   ("kriminal", "Kejadian kriminal %", (220, 100, 110))]
        key, label, col = metrics[self.metric_i % len(metrics)]
        ui.button((A.x, y, 28, 24), ui.f["m"].render("<", True, WHITE), lambda: setattr(self, "metric_i", self.metric_i - 1), "load_seed", 1)
        ui.button((A.right - 28, y, 28, 24), ui.f["m"].render(">", True, WHITE), lambda: setattr(self, "metric_i", self.metric_i + 1), "load_seed", 1)
        ui.text(label, (A.centerx, y + 5), INK, "s", "c")
        y += 28
        fmt = None if key in ("gini", "nganggur", "ihk", "penduduk", "emosi", "kriminal") else (lambda v: rp(v))
        chart = pygame.Rect(A.x, y, A.w, 148)
        values = list(w.series[key])
        ui.line_chart(chart, [values], [col], fmt, fill=True)
        if len(values) < 2:
            ui.text("DATA GRAFIK BELUM TERSEDIA",
                    (chart.centerx, chart.centery - 8), (190, 192, 214), "xs", "c")
            ui.text("SIMULASI BARU DIMULAI",
                    (chart.centerx, chart.centery + 8), (150, 152, 180), "xs", "c")
        y = chart.bottom + 8
        button_w = (A.w - 6) // 2
        ui.button((A.x, y, button_w, 26), "BERITA KOTA", lambda: setattr(self, "tab", 2), "load_seed", 1)
        ui.button((A.x + button_w + 6, y, button_w, 26), "KEBIJAKAN", lambda: self.open_window("policy"), "options", 1)
        y += 31
        ui.button((A.x, y, A.w, 26), "BUKA DASBOR MAKRO", lambda: self.open_window("macro"), "options", 1)

    def citizen_directory(self):
        citizens = sorted(self.world.citizens, key=lambda citizen: citizen.networth, reverse=True)
        query = self.people_query.strip().casefold()
        if query:
            citizens = [citizen for citizen in citizens if query in citizen.name.casefold()]
        return citizens

    def tab_people(self, A):
        ui, w = self.ui, self.world
        c = self.sel
        if c is not None and c not in w.citizens:
            c = self.sel = None
        x, y = A.x, A.y
        if c is None:
            search = pygame.Rect(x, y, A.w, 26)
            pygame.draw.rect(ui.screen, WHITE if self.people_search_focus else CREAM2, search, border_radius=4)
            pygame.draw.rect(ui.screen, BLUE if self.people_search_focus else MUTED, search, 2, border_radius=4)
            prompt = self.people_query or "Cari nama warga..."
            ui.text(prompt, (search.x + 8, search.y + 6), INK if self.people_query else MUTED, "xs")
            ui.hits.append((search, lambda p: setattr(self, "people_search_focus", True)))
            self.people_search_rect = search
            y += 32
            citizens = self.citizen_directory()
            ui.text("HASIL PENCARIAN" if self.people_query else "5 WARGA TERKAYA", (x, y), INK, "s")
            y += 22
            richest = citizens[:5]
            for rank, q in enumerate(richest, 1):
                row = pygame.Rect(x - 4, y, A.w + 8, 20)
                hot = ui.hot(row)
                pygame.draw.rect(ui.screen, WHITE if hot else CREAM, row, border_radius=3)
                ui.text(f"{rank}. {q.name[:15]}", (row.x + 5, row.y + 3), INK, "xs")
                ui.text(rp(q.networth), (row.right - 4, row.y + 3), GREEN, "xs", "r")
                ui.hits.append((row, lambda p, q=q: setattr(self, "sel", q)))
                y += 21
            ui.text(f"WARGA {len(citizens)} · URUT KEKAYAAN",
                    (x, y + 3), INK, "xs")
            y += 23
            area = pygame.Rect(x, y, A.w, A.bottom - y)
            if not citizens:
                ui.text("Warga tidak ditemukan.", (area.x + 4, area.y + 8), MUTED, "xs")
            row_h = 24
            off = ui.scroll_area("people", area, len(citizens) * row_h)
            for i, q in enumerate(citizens):
                row_y = area.y + i * row_h - off
                if row_y < area.y or row_y + row_h > area.bottom:
                    continue
                row = pygame.Rect(area.x, row_y, area.w - 8, row_h - 2)
                hot = ui.hot(row)
                pygame.draw.rect(ui.screen, WHITE if hot else CREAM, row, border_radius=3)
                ui.text(f"{i + 1:>3}. {q.name[:14]}", (row.x + 4, row.y + 4), INK, "xs")
                ui.text(rp(q.networth), (row.right - 4, row.y + 4), GREEN, "xs", "r")
                ui.hits.append((row, lambda p, q=q: setattr(self, "sel", q)))
            ui.scrollbar("people", area, len(citizens) * row_h)
            return
        v = self.cv.views.get(c.id)
        if v:
            ui.panel((x, y, 64, 76), "dark", 1)
            ui.screen.blit(pygame.transform.scale(v.idle, (40, 56)), (x + 12, y + 10))
            if v.emote:
                em = self.a.emotes[v.emote[0]]["composed"]
                ui.screen.blit(self.a.scaled(em[int(self.cv.t * 5) % 4], 2), (x + 64, y + 4))
        ui.text(c.name.upper()[:20], (x + 74, y + 40), INK, "m")
        ui.text(f"{c.label} · {'P' if c.female else 'L'} · {int(c.age)} th", (x + 74, y + 58), MUTED, "xs")
        ui.button((A.right - 26, y, 26, 24), "X", lambda: setattr(self, "sel", None), "exit", 1, tip="Lepas pilihan")
        y += 86
        job = c.job.name if c.job else ("Pemilik " + c.business.name if c.business else "Menganggur")
        rows = [("Kerja", job), ("Tunai", rp(c.cash)), ("Tabungan", rp(c.savings)),
                ("Total aset", rp(c.assets)), ("Utang", rp(c.debt)), ("Kekayaan bersih", rp(c.networth)),
                ("Plafon utang tanpa agunan", rp(w.unsecured_limit(c))),
                ("Kendaraan", rp(c.vehicle_value) if c.vehicle_value else "Tidak punya"),
                ("Rumah", ("milik sendiri" if c.home and c.home.owner is c else ("sewa" if c.home else "tunawisma"))
                 + (f" (+{len(c.houses)} sewa)" if c.houses else "")),
                ("AI / literasi uang", f"{c.learning * 100:.0f}% / {c.financial_literacy * 100:.0f}%"),
                ("Emosi", f"{c.emotion} · stres {c.stress * 100:.0f}% · takut {c.fear * 100:.0f}%"),
                ("Sedih / depresi", f"{c.sadness * 100:.0f}% / {c.depression * 100:.0f}%"),
                ("Gig terakhir", f"{c.last_gig or 'belum'} · total {c.gigs_done}"),
                ("Catatan kriminal", str(c.crimes)),
                ("Sehat/Senang", f"{c.health:.0f} / {c.happy:.0f}")]
        for k, val in rows:
            ui.text(k, (x, y), MUTED)
            ui.text(val[:24], (A.right, y), INK, "s", "r")
            y += 17
        hold = ", ".join(f"{s} {h[0]:.1f}" for s, h in list(c.hold.items())[:3])
        if hold:
            ui.text("Pegang: " + hold[:32], (x, y), MUTED)
            y += 17
        observation = w.agent_observation(c)
        if observation is not None:
            top_goal = observation["desires"][0]["id"] if observation["desires"] else "tidak ada"
            intention = observation["intention"]
            intention_text = (
                intention["goal_id"] if intention is not None else "tidak ada"
            )
            ui.text("OBSERVASI AGEN", (x, y), INK, "xs")
            y += 15
            ui.text("Tujuan", (x, y), MUTED, "xs")
            ui.text(top_goal[:24], (A.right, y), INK, "xs", "r")
            y += 14
            ui.text("Niat", (x, y), MUTED, "xs")
            ui.text(intention_text[:24], (A.right, y), INK, "xs", "r")
            y += 14
            ui.text("Strategi", (x, y), MUTED, "xs")
            ui.text(
                f"{observation['learning']['contexts']} konteks · "
                f"{observation['learning']['arms']} aksi",
                (A.right, y), INK, "xs", "r",
            )
            y += 14
            ui.text("Pengetahuan / sosial", (x, y), MUTED, "xs")
            ui.text(
                f"{len(observation['validated_claims'])} klaim · "
                f"{len(observation['social']['relations'])} relasi",
                (A.right, y), INK, "xs", "r",
            )
            y += 16
        y += 4
        traits = [("Risiko", c.risk), ("Serakah", c.greed), ("Hemat", c.frugal), ("Ikut tren", c.herd),
                  ("Optimis", c.optimism), ("Sabar", c.patience), ("Skill", c.skill), ("Jiwa usaha", c.entre),
                  ("Bicara", c.persuasion), ("Bangunan", c.construction_skill), ("Servis", c.repair_skill)]
        for i, (k, val) in enumerate(traits):
            cx, cy = x + (i % 2) * 134, y + (i // 2) * 16
            ui.text(k, (cx, cy), MUTED, "xs")
            ui.bar((cx + 58, cy + 2, 64, 9), val, BLUE)
        y += 86
        hw = (A.w - 12) // 4
        for i, (lab, d) in enumerate((("+1JT", 1e6), ("+10JT", 1e7), ("+100JT", 1e8), ("-1JT", -1e6))):
            ui.button((x + i * (hw + 4), y, hw, 24), lab, lambda d=d: w.edit_cash(c, d), "new_city" if d > 0 else "exit", 1)
        y += 28
        ui.button((x, y, A.w, 24), "SET UANG TUNAI - M", lambda: self.open_prompt(f"Uang tunai {c.first}", lambda val: w.set_cash(c, val)), "options", 1)
        y += 32
        ui.text("PIKIRAN TERAKHIR", (x, y), INK, "s")
        y += 18
        for day, msg in list(c.thoughts)[:4]:
            for ln in ui.wrap(f"[{day}] {msg}", 36)[:2]:
                if y < A.bottom - 12:
                    ui.text(ln, (x, y), (70, 74, 86), "xs")
                y += 14

    def tab_news(self, A):
        ui, a, w = self.ui, self.a, self.world
        ev = list(reversed(w.events))
        rh = 46
        off = ui.scroll_area("news", A, len(ev) * rh)
        for i, (eid, kind, title, sub) in enumerate(ev):
            y = A.y + i * rh - off
            if y < A.y or y + rh > A.bottom:
                continue
            col = {"good": SOFT_G, "bad": SOFT_R, "info": SOFT_B}[kind]
            r = pygame.Rect(A.x, y, A.w - 8, rh - 4)
            pygame.draw.rect(ui.screen, col, r, border_radius=4)
            pygame.draw.rect(ui.screen, INK, r, 1, border_radius=4)
            icon = {"good": "trend_up", "bad": "alert_icon", "info": "trend_flat"}[kind]
            ui.sprite(a.chart[icon], (r.x + 6, r.y + 6), 2)
            ui.bmp(title[:22], (r.x + 30, r.y + 6), 1, INK)
            ui.text(sub[:30], (r.x + 30, r.y + 22), (60, 56, 80), "xs")
        ui.scrollbar("news", A, len(ev) * rh)

    # ---- tooltip bangunan
    def lot_tip(self, lot):
        b = lot.building
        if lot.kind == "park":
            return "Taman kota"
        if lot.kind == "exchange":
            return "BURSA EFEK\nKlik untuk membuka pasar saham & kripto"
        if lot.kind == "hall":
            return f"BALAI KOTA\nPegawai {len(b.workers)} · kas kota {rp(self.world.treasury)}\nKlik untuk kebijakan"
        if lot.kind == "house" and b:
            own = b.owner.first if b.owner else "Kota"
            return f"Rumah · penghuni {len(b.occupants)}/{b.cap}\nPemilik {own} · nilai {rp(b.value)}\nKlik untuk detail"
        if b is not None and hasattr(b, "workers"):
            return f"{b.name}\nKas {rp(b.cash)} · pekerja {len(b.workers)}/{b.max_workers}\nLaba bln lalu {rp(b.last_profit)}\nKlik untuk detail"
        return "Lahan kosong" if lot.kind == "biz" else None

    # ---- prompt angka
    def draw_prompt(self):
        ui, p = self.ui, self.prompt
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((10, 8, 24, 130))
        ui.screen.blit(shade, (0, 0))
        r = pygame.Rect(0, 0, 460, 124)
        r.center = (W // 2, H // 2)
        ui.shadow_panel(r, "cream")
        ui.bmp(p["title"], (r.x + 20, r.y + 18), 1, INK)
        ui.text("contoh: 5jt, 250rb, 1.5m (miliar)   Enter=OK  Esc=batal", (r.x + 20, r.y + 40), MUTED, "xs")
        box = pygame.Rect(r.x + 20, r.y + 64, r.w - 40, 34)
        pygame.draw.rect(ui.screen, INK, box, border_radius=4)
        pygame.draw.rect(ui.screen, WHITE, box.inflate(-4, -4), border_radius=3)
        cur = "_" if pygame.time.get_ticks() // 400 % 2 == 0 else ""
        ui.text(p["text"] + cur, (box.x + 10, box.y + 8), INK, "m")

    # ================================================================== input
    def event(self, e):
        if self.prompt:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.prompt = None
                elif e.key == pygame.K_RETURN:
                    val = parse_money(self.prompt["text"])
                    if val is not None:
                        self.prompt["cb"](val)
                    self.prompt = None
                elif e.key == pygame.K_BACKSPACE:
                    self.prompt["text"] = self.prompt["text"][:-1]
                elif e.unicode and e.unicode.isprintable() and len(self.prompt["text"]) < 16:
                    self.prompt["text"] += e.unicode
            return
        if self.people_search_focus and e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER):
                self.people_search_focus = False
            elif e.key == pygame.K_BACKSPACE:
                self.people_query = self.people_query[:-1]
            elif e.unicode and e.unicode.isprintable() and len(self.people_query) < 32:
                self.people_query += e.unicode
            return
        if (self.people_search_focus and e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self.people_search_rect and not self.people_search_rect.collidepoint(e.pos)):
            self.people_search_focus = False
        if self.menu_open:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                if self.menu_page != "main":
                    self.menu_page = "main"
                else:
                    self.menu_open = False
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.ui.click(e.pos)
            return
        if e.type == pygame.MOUSEWHEEL:
            if MAPR.collidepoint(pygame.mouse.get_pos()):
                if pygame.key.get_mods() & pygame.KMOD_SHIFT and e.y:
                    self.pan_by(-e.y * 48, 0)
                else:
                    self.pan_by(-e.x * 48, -e.y * 48)
            else:
                self.ui.wheel(e.y)
        elif e.type == pygame.KEYDOWN:
            self.key(e.key)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (2, 3) and MAPR.collidepoint(e.pos):
            self.pan_anchor = {
                "pos": e.pos, "camera_x": self.camera_x, "camera_y": self.camera_y,
                "button": e.button, "moved": False,
            }
        elif e.type == pygame.MOUSEBUTTONUP and self.pan_anchor and e.button == self.pan_anchor["button"]:
            anchor = self.pan_anchor
            self.pan_anchor = None
            if anchor["button"] == 1 and not anchor["moved"] and MAPR.collidepoint(e.pos):
                self.click_map((e.pos[0] - MAPR.x + self.camera_x, e.pos[1] - MAPR.y + self.camera_y))
        elif e.type == pygame.MOUSEMOTION and self.pan_anchor:
            dx = e.pos[0] - self.pan_anchor["pos"][0]
            dy = e.pos[1] - self.pan_anchor["pos"][1]
            if abs(dx) >= 4 or abs(dy) >= 4:
                self.pan_anchor["moved"] = True
            self.pan_to(self.pan_anchor["camera_x"] - dx, self.pan_anchor["camera_y"] - dy)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.ui.click(e.pos):
                return
            if self.window and WIN.collidepoint(e.pos):
                return
            if MAPR.collidepoint(e.pos):
                self.pan_anchor = {
                    "pos": e.pos, "camera_x": self.camera_x, "camera_y": self.camera_y,
                    "button": e.button, "moved": False,
                }

    def click_map(self, pos):
        c = self.cv.pick_citizen(pos)
        if c:
            self.select_citizen(c)
            return
        lot = self.cv.lot_at(pos)
        b = lot.building if lot else None
        if lot is not None:
            if lot.kind == "exchange":
                self.window = "market"
                return
            if lot.kind == "hall":
                self.window = "policy"
                return
            if lot.kind == "house" and b:
                self.sel_house = b
                self.window = "house"
                return
            if b is not None and hasattr(b, "workers") and lot.kind == "biz":
                self.sel_biz = b
                self.window = "biz"
                return
        self.sel = None

    def key(self, k):
        if k == pygame.K_ESCAPE:
            if self.window:
                self.window = None
            else:
                self.menu_open = True
                self.menu_page = "main"
        elif k == pygame.K_SPACE:
            self.speed_i = 0 if self.speed_i else 1
        elif pygame.K_1 <= k <= pygame.K_5:
            self.speed_i = k - pygame.K_1 + 1
        elif k == pygame.K_TAB:
            self.tab = (self.tab + 1) % len(TABS)
        elif k == pygame.K_p:
            self.open_window("market")
        elif k == pygame.K_e:
            self.open_window("macro")
        elif k == pygame.K_k:
            self.open_window("policy")
        elif k == pygame.K_b:
            self.open_window("biz")
        elif k == pygame.K_r:
            self.open_window("house")
        elif k == pygame.K_l:
            self.cycle_layer()
        elif k == pygame.K_w:
            self.tab = 1
        elif k == pygame.K_n:
            self.tab = 2
        elif k == pygame.K_F5:
            self.app.save_world(self.world)
        elif k == pygame.K_m and self.sel:
            c = self.sel
            self.open_prompt(f"Uang tunai {c.first}", lambda v: self.world.set_cash(c, v))
        elif k in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            dx = -72 if k == pygame.K_LEFT else (72 if k == pygame.K_RIGHT else 0)
            dy = -72 if k == pygame.K_UP else (72 if k == pygame.K_DOWN else 0)
            self.pan_by(dx, dy)
