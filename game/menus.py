"""
menus.py -- Start Menu (tombol, seed box, dadu dari pack), panel Opsi, dan Menu Jeda.
Latar start menu = kota hidup (demo) yang bergerak pelan dengan siklus siang/malam.
"""
import math
import random

import pygame

from systems.ekonomi_core import World, MAP_W, MAP_H
from game.city_view import CityView
from game.ui import INK, CREAM, MUTED, WHITE, SOFT_Y, SOFT_G, SOFT_R, GREEN

W, H = 1280, 720


def new_seed():
    return random.randrange(100_000, 1_000_000)


class _DemoSettings:
    """Pengaturan tetap untuk kota latar belakang."""
    day_night, cars, emotes, floaters, names = True, True, True, False, False


# ======================================================================= opsi
def draw_options(ui, app, r):
    """Panel opsi (dipakai di start menu & menu jeda). r = Rect panel."""
    st = app.settings
    ui.shadow_panel(r, "cream")
    ui.bmp("OPSI", (r.centerx, r.y + 18), 2, INK, "c")
    y = r.y + 62
    rows = [("day_night", "Siklus siang / malam"), ("cars", "Tampilkan mobil milik warga"), ("emotes", "Emote bubble warga"),
            ("floaters", "Teks melayang (+Rp, BOOM!)"), ("names", "Selalu tampilkan nama warga"),
            ("fullscreen", "Layar penuh (F11)")]
    for key, label in rows:
        def cb(v, key=key):
            st.set(key, v)
            if key == "fullscreen":
                app.apply_fullscreen()
        ui.toggle((r.x + 30, y), st.data[key], cb, label, INK, "m")
        y += 38
    y += 6
    ui.text("Penduduk awal (kota baru)", (r.x + 30, y), INK, "m")
    ui.text(str(st.population), (r.right - 30, y), INK, "m", "r")
    ui.slider((r.x + 30, y + 22, r.w - 60, 26), st.population, 20, 140, lambda v: st.set("population", int(v)), 10)
    ui.text("Berlaku untuk kota yang dibuat setelah ini.", (r.x + 30, y + 54), MUTED, "xs")


# ======================================================================= start menu
class StartMenu:
    def __init__(self, app):
        self.app = app
        self.ui, self.a, self.opt = app.ui, app.assets, app.settings
        seed = new_seed()
        self.world = World(seed=seed, n_pop=30)
        for _ in range(25):
            self.world.advance(24)
        self.world.hour = 15.5
        self.cv = CityView(self.a, self.world, _DemoSettings())
        self.t = 0.0
        self.seed_text = str(new_seed())
        self.page = "main"
        self.msg = None
        self.msg_t = 0.0
        self.box = self._make_seed_box()

    def _make_seed_box(self):
        b = self.a.menu["seed_input_box"].copy()
        fill = b.get_at((40, 8))
        pygame.draw.rect(b, fill, (3, 3, b.get_width() - 6, b.get_height() - 7))
        return b

    # ---- update / draw
    def update(self, dt):
        self.t += dt
        self.world.advance(dt * 0.9)
        self.cv.update(dt, 1)
        if self.msg:
            self.msg_t -= dt
            if self.msg_t <= 0:
                self.msg = None

    def say(self, text):
        self.msg, self.msg_t = text, 2.5

    def draw(self, screen):
        ui, a = self.ui, self.a
        ui.begin(screen)
        surf = self.cv.draw()
        # kamera pelan menyusuri kota: potong 640x360 lalu perbesar 2x (tajam)
        ox = int((MAP_W - 640) * (0.5 + 0.5 * math.sin(self.t * 0.07)))
        oy = int((MAP_H - 360) * (0.5 + 0.5 * math.sin(self.t * 0.05 + 1)))
        view = surf.subsurface(pygame.Rect(ox, oy, 640, 360))
        screen.blit(pygame.transform.scale(view, (W, H)), (0, 0))
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((20, 18, 44, 120))
        screen.blit(shade, (0, 0))
        cx = W // 2
        # judul
        title = "RUPIAHVILLE"
        bounce = int(3 * math.sin(self.t * 2.2))
        ui.bmp(title, (cx + 4, 56 + bounce + 4), 6, (20, 18, 44), "c")
        ui.bmp(title, (cx, 56 + bounce), 6, SOFT_Y, "c")
        ui.bmp("SIMULASI EKONOMI PIKSEL", (cx, 126), 2, WHITE, "c")
        ui.bmp("SEMUA WARGA MULAI DARI RP0", (cx, 152), 1, (200, 204, 230), "c")
        if self.page == "options":
            r = pygame.Rect(0, 0, 480, 470)
            r.center = (cx, 400)
            draw_options(ui, self.app, r)
            ui.button((r.centerx - 90, r.bottom - 52, 180, 38), "KEMBALI", lambda: setattr(self, "page", "main"), "exit", 2)
        else:
            self.draw_main(screen, cx)
        ui.bmp("V2 · ESC KELUAR", (12, H - 20), 1, (170, 172, 196))
        if self.msg:
            ui.bmp(self.msg, (cx, H - 30), 2, SOFT_R, "c")
        ui.end()

    def sprite_button(self, rect, key, cb):
        hot = rect.collidepoint(self.ui.mouse)
        spr = self.a.menu[f"btn_{key}_{'pressed' if hot else 'normal'}"]
        self.ui.screen.blit(self.a.scaled(spr, 3), rect.topleft)
        self.ui.hits.append((rect, lambda p, cb=cb: cb()))

    def draw_main(self, screen, cx):
        ui, a = self.ui, self.a
        # seed box + dadu
        box = self.a.scaled(self.box, 3)
        bx = cx - (box.get_width() + 8 + 48) // 2
        by = 196
        base = self.box.copy()
        t = a.font.render("SEED:" + self.seed_text, 1, (74, 78, 105))
        base.blit(t, (6, 4))
        screen.blit(pygame.transform.scale(base, (base.get_width() * 3, base.get_height() * 3)), (bx, by))
        dice = pygame.Rect(bx + box.get_width() + 8, by, 48, 48)
        screen.blit(a.scaled(a.menu["btn_random_dice"], 3), dice.topleft)
        ui.hits.append((dice, lambda p: setattr(self, "seed_text", str(new_seed()))))
        if dice.collidepoint(ui.mouse):
            ui.tip = "Acak seed"
        ui.bmp("KLIK DADU UNTUK SEED ACAK", (cx, by + 54), 1, (200, 204, 230), "c")
        bw, bh = 192, 54
        y = 292
        rects = []
        has_save = self.app.has_save()
        items = [("new_city", self.new_city), ("options", lambda: setattr(self, "page", "options")),
                 ("exit", self.app.quit)]
        for key, cb in items:
            self.sprite_button(pygame.Rect(cx - bw // 2, y, bw, bh), key, cb)
            y += bh + 10
        if has_save:
            ui.button((cx - bw // 2, y, bw, 40), "LANJUTKAN SAVE", self.app.load_game, "new_city", 1, tip="Muat simpanan terakhir (F5 saat bermain)")

    def new_city(self):
        self.app.new_game(int(self.seed_text))

    def load_seed(self):
        self.new_city()

    def event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                if self.page == "options":
                    self.page = "main"
                else:
                    self.app.quit()
            elif self.page == "main":
                if e.key == pygame.K_RETURN:
                    self.new_city()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.ui.click(e.pos)


# ======================================================================= menu jeda
def draw_pause(app, sc):
    ui = app.ui
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    shade.fill((10, 8, 24, 150))
    ui.screen.blit(shade, (0, 0))
    cx = W // 2
    if sc.menu_page == "options":
        r = pygame.Rect(0, 0, 480, 470)
        r.center = (cx, H // 2)
        draw_options(ui, app, r)
        ui.button((r.centerx - 90, r.bottom - 52, 180, 38), "KEMBALI", lambda: setattr(sc, "menu_page", "main"), "exit", 2)
        return
    r = pygame.Rect(0, 0, 360, 380)
    r.center = (cx, H // 2)
    ui.shadow_panel(r, "cream")
    ui.bmp("MENU JEDA", (cx, r.y + 20), 2, INK, "c")
    ui.bmp(f"SEED {sc.world.seed}", (cx, r.y + 48), 1, MUTED, "c")
    y = r.y + 76

    def save_and_resume():
        if app.save_world(sc.world):
            sc.menu_open = False

    for label, color, cb in (
            ("LANJUTKAN", "new_city", lambda: setattr(sc, "menu_open", False)),
            ("SIMPAN GAME", "load_seed", save_and_resume),
            ("OPSI", "options", lambda: setattr(sc, "menu_page", "options")),
            ("MENU UTAMA", "exit", app.go_menu),
            ("KELUAR GAME", "exit", app.quit)):
        ui.button((cx - 130, y, 260, 46), label, cb, color, 2)
        y += 56
    if sc.note:
        ui.bmp(sc.note, (cx, r.bottom - 20), 1, SOFT_R, "c")
