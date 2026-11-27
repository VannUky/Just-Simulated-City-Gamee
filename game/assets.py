"""
assets.py -- memuat SEMUA aset pack dan memotongnya lewat atlas_metadata.json.

Yang dipakai dari pack:
  karakter (idle + sheet jalan) · bangunan · kendaraan · jalan auto-tile + props
  emote & bubble · bitmap font + floating text · panel 9-slice, candlestick, sparkline, gauge, ikon tren
  tombol start menu, seed box, toggle, slider, ikon HUD, dock, tombol kecepatan
"""
import json
from pathlib import Path

import pygame

ALIAS = {"·": ".", "_": "-", "=": "-", "'": ",", "(": " ", ")": " ", "&": "+", "*": "+", ">": "-", "<": "-", "#": " "}


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def R(d):
    return pygame.Rect(d["x"], d["y"], d["w"], d["h"])


def nine(src, size, m, scale=1, tile=False):
    """9-slice: sudut diperbesar `scale` kali (tetap tajam), sisi & tengah direntangkan."""
    l, t, r, b = m
    sw, sh = src.get_size()
    w, h = int(size[0]), int(size[1])
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    L, T, Rr, B = l * scale, t * scale, r * scale, b * scale
    xs = [(0, l, 0, L), (l, sw - r, L, w - Rr), (sw - r, sw, w - Rr, w)]
    ys = [(0, t, 0, T), (t, sh - b, T, h - B), (sh - b, sh, h - B, h)]
    for sy0, sy1, dy0, dy1 in ys:
        for sx0, sx1, dx0, dx1 in xs:
            dw, dh = dx1 - dx0, dy1 - dy0
            if dw <= 0 or dh <= 0 or sx1 <= sx0 or sy1 <= sy0:
                continue
            part = src.subsurface(pygame.Rect(sx0, sy0, sx1 - sx0, sy1 - sy0))
            if tile and (sx0, sy0) == (l, t):          # pusat panel: diulang (tile), bukan direntang -> pola titik tetap kecil
                tw, th = (sx1 - sx0) * scale, (sy1 - sy0) * scale
                cell = pygame.transform.scale(part, (tw, th))
                for ty in range(dy0, dy1, th):
                    for tx in range(dx0, dx1, tw):
                        out.blit(cell, (tx, ty), pygame.Rect(0, 0, min(tw, dx1 - tx), min(th, dy1 - ty)))
                continue
            out.blit(pygame.transform.scale(part, (dw, dh)), (dx0, dy0))
    return out


class BitmapFont:
    """Font piksel dari pack (A-Z, 0-9, $ % + - . , : ! ? /). Huruf kecil otomatis jadi kapital."""

    def __init__(self, sheet, glyphs):
        self.g = {ch: sheet.subsurface(R(d)).copy() for ch, d in glyphs.items()}
        self.cache = {}
        self.scaled = {}

    def _glyph(self, ch, scale):
        k = (ch, scale)
        s = self.scaled.get(k)
        if s is None:
            g = self.g[ch]
            s = g if scale == 1 else pygame.transform.scale(g, (g.get_width() * scale, g.get_height() * scale))
            self.scaled[k] = s
        return s

    def width(self, text, scale=1):
        return max(0, len(text) * 8 * scale - scale)

    def render(self, text, scale=1, tint=None):
        text = str(text).upper()
        key = (text, scale, tint)
        surf = self.cache.get(key)
        if surf is not None:
            return surf
        if len(self.cache) > 2500:
            self.cache.clear()
        surf = pygame.Surface((max(1, self.width(text, scale)), 9 * scale), pygame.SRCALPHA)
        for i, ch in enumerate(text):
            ch = ALIAS.get(ch, ch)
            if ch in self.g:
                surf.blit(self._glyph(ch, scale), (i * 8 * scale, 0))
        if tint:
            surf.fill(tuple(tint) + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        self.cache[key] = surf
        return surf


class Assets:
    def __init__(self, root):
        self.root = Path(root)
        metadata_path = self.root / "atlas_metadata.json"
        meta = json.loads(metadata_path.read_text(encoding="utf-8"))
        required_sheets = {
            "01_emotes_and_bubbles.png", "02_speed_controls.png",
            "03_roads_and_props.png", "04_charts_and_economy.png",
            "05_bitmap_font_and_floating_text.png", "06_start_menu_and_hud.png",
        }
        sheets = meta.get("sheets")
        if not isinstance(sheets, dict) or not required_sheets.issubset(sheets):
            legacy_path = self.root / "atlas_metadata_legacy.json"
            if not legacy_path.is_file():
                found = sorted(sheets) if isinstance(sheets, dict) else []
                missing = sorted(required_sheets - set(found))
                raise ValueError(
                    f"{metadata_path} does not describe the runtime atlas sheets; "
                    f"missing {', '.join(missing)}. "
                    f"Provide a compatible atlas manifest at {legacy_path}."
                )
            meta = json.loads(legacy_path.read_text(encoding="utf-8"))
            sheets = meta.get("sheets")
            if not isinstance(sheets, dict) or not required_sheets.issubset(sheets):
                raise ValueError(f"{legacy_path} does not describe the runtime atlas sheets.")

        self.meta = sheets
        meta_info = meta.get("meta")
        palette = (
            meta_info.get("palette_hex", meta_info.get("palette"))
            if isinstance(meta_info, dict) else None
        )
        if not isinstance(palette, dict):
            raise ValueError(f"{metadata_path} does not contain a valid palette.")
        self.pal = {k: hexrgb(v) for k, v in palette.items()}
        self._cache = {}
        load = lambda p: pygame.image.load(str(self.root / p)).convert_alpha()
        self.sh_emote = load("emotes/01_emotes_and_bubbles.png")
        self.sh_speed = load("menu/speed_controls.png")
        self.sh_road = load("roads/roads_and_props.png")
        self.sh_chart = load("chart/04_charts_and_economy.png")
        self.sh_font = load("font/bitmap_font_and_floating_text.png")
        self.sh_menu = load("menu/start_menu_and_hud.png")

        m = self.meta
        self.font = BitmapFont(self.sh_font, m["05_bitmap_font_and_floating_text.png"]["glyphs"])
        self.labels = {k: self.sh_font.subsurface(R(d)).copy()
                       for k, d in m["05_bitmap_font_and_floating_text.png"]["floating_labels"].items()}
        self.roads = {k: self.sh_road.subsurface(R(d)).copy() for k, d in m["03_roads_and_props.png"]["roads"].items()}
        self.props = {k: self.sh_road.subsurface(R(d)).copy() for k, d in m["03_roads_and_props.png"]["props"].items()}
        self.chart = {}
        for k, d in m["04_charts_and_economy.png"]["widgets"].items():
            self.chart[k] = self.sh_chart.subsurface(R(d)).copy()
        self.chart_meta = m["04_charts_and_economy.png"]["widgets"]
        self.menu = {k: self.sh_menu.subsurface(R(d)).copy() for k, d in m["06_start_menu_and_hud.png"]["elements"].items()}
        self.speed = {}
        for name, states in m["02_speed_controls.png"]["buttons"].items():
            self.speed[name] = {st: self.sh_speed.subsurface(R(r)).copy() for st, r in states.items()}
        em = m["01_emotes_and_bubbles.png"]
        self.bubbles = {tone: [self.sh_emote.subsurface(R(r)).copy() for r in fr] for tone, fr in em["bubbles"].items()}
        self.emotes = {}
        for name, d in em["emotes"].items():
            self.emotes[name] = {
                "composed": [self.sh_emote.subsurface(R(r)).copy() for r in d["composed_frames"]],
                "standalone": [self.sh_emote.subsurface(R(r)).copy() for r in d["standalone_frames"]],
            }
        self.char = self._load_characters()
        self.building_src = self._load_buildings()
        self.car_src = self._load_cars()
        self.blank_btn = self._make_blank_buttons()
        self.blank_dock = self._make_blank_dock()
        self.dock = dict((k[5:], v) for k, v in self.menu.items() if k.startswith("dock_"))
        for name, fn in (("market", self._icon_market), ("macro", self._icon_macro),
                         ("policy", self._icon_policy), ("menu", self._icon_menu)):
            self.dock[name] = fn()

    # ------------------------------------------------------------------ util
    def scaled(self, surf, k, flip=(False, False)):
        key = (id(surf), k, flip)
        out = self._cache.get(key)
        if out is None:
            w, h = surf.get_size()
            out = surf if k == 1 else pygame.transform.scale(surf, (max(1, int(w * k)), max(1, int(h * k))))
            if flip[0] or flip[1]:
                out = pygame.transform.flip(out, flip[0], flip[1])
            self._cache[key] = out
        return out

    # ------------------------------------------------------------------ karakter, bangunan, kendaraan
    def _load_characters(self):
        out = {True: [], False: []}
        idle_dir = self.root / "characters" / "idle"
        sheet_dir = self.root / "characters" / "sheets"
        for prefix, female in (("cewe", True), ("cowo", False)):
            for idle_path in sorted(idle_dir.glob(f"{prefix}_*_idle.png")):
                sheet_path = sheet_dir / idle_path.name.replace("_idle.png", "_sheet.png")
                if not sheet_path.is_file():
                    raise FileNotFoundError(f"Sprite berjalan tidak ditemukan: {sheet_path}")
                idle = pygame.transform.scale(pygame.image.load(str(idle_path)).convert_alpha(), (20, 28))
                sheet = pygame.image.load(str(sheet_path)).convert_alpha()
                if sheet.get_width() % 3:
                    raise ValueError(f"Spritesheet harus 3 frame: {sheet_path}")
                fw = sheet.get_width() // 3
                frames = [pygame.transform.scale(sheet.subsurface(pygame.Rect(i * fw, 0, fw, sheet.get_height())).copy(), (20, 28))
                          for i in range(3)]
                out[female].append((idle, frames))
        if not out[True] or not out[False]:
            raise FileNotFoundError(f"Aset karakter cewe/cowo tidak lengkap: {idle_dir}")
        return out

    def _load_buildings(self):
        d = {}
        for p in (self.root / "buildings").glob("*.png"):
            d[p.stem] = pygame.image.load(str(p)).convert_alpha()
        need = ("house_blue", "house_red", "house_purple", "house_green", "house_orange", "shop_mart", "office_corp", "bank_exchange")
        for n in need:
            if n not in d:
                raise FileNotFoundError(f"Aset bangunan tidak ditemukan: buildings/{n}.png")
        return d

    def building(self, key, flip=False):
        """Sprite bangunan 64x52 (skala 0.5 dari 128x104)."""
        names = {"house_0": "house_blue", "house_1": "house_red", "house_2": "house_purple", "house_3": "house_green",
                 "house_4": "house_orange", "house_5": "house_blue", "shop": "shop_mart", "factory": "office_corp",
                 "exchange": "bank_exchange", "hall": "office_corp"}
        ck = ("bld", key, flip)
        s = self._cache.get(ck)
        if s is None:
            s = pygame.transform.scale(self.building_src[names[key]], (64, 52))
            if key == "hall":                                   # Balai Kota: office_corp diberi rona lavender
                s = s.copy()
                s.fill((214, 196, 246, 255), special_flags=pygame.BLEND_RGBA_MULT)
            if key == "house_5":
                flip = True
            if flip:
                s = pygame.transform.flip(s, True, False)
            self._cache[ck] = s
        return s

    def _load_cars(self):
        d = {}
        for p in (self.root / "vehicles").glob("car_*_*.png"):
            _, color, o = p.stem.split("_")
            img = pygame.image.load(str(p)).convert_alpha()
            d[(color, o)] = pygame.transform.scale(img, (img.get_width() // 2, img.get_height() // 2))
        if not d:
            raise FileNotFoundError("Aset kendaraan tidak ditemukan")
        return d

    def car(self, color, heading):
        """heading: 'E','W','N','S' (aset h menghadap timur, v menghadap utara)."""
        o = "h" if heading in "EW" else "v"
        s = self.car_src[(color, o)]
        flip = (heading == "W", heading == "S")
        return self.scaled(s, 1, flip) if any(flip) else s

    # ------------------------------------------------------------------ tombol & panel dari sprite
    def _make_blank_buttons(self):
        """Hapus tulisan bawaan tombol (ambil profil warna kolom x=1, tepat di dalam outline) supaya label bisa diganti sendiri."""
        out = {}
        for color in ("new_city", "load_seed", "options", "exit"):
            for st in ("normal", "pressed"):
                src = self.menu[f"btn_{color}_{st}"].copy()
                w, h = src.get_size()
                for y in range(h):
                    c = src.get_at((1, y))
                    if c[3] == 0:
                        continue
                    pygame.draw.line(src, c, (1, y), (w - 2, y))
                out[(color, st)] = src
        return out

    def button(self, color, size, state="normal", scale=2):
        key = ("btn", color, size, state, scale)
        s = self._cache.get(key)
        if s is None:
            src = self.blank_btn[(color, "pressed" if state == "pressed" else "normal")]
            s = nine(src, size, (4, 3, 4, 4), scale)
            if state == "hover":
                s.fill((22, 22, 22, 0), special_flags=pygame.BLEND_RGB_ADD)
            elif state == "disabled":
                s.fill((170, 170, 170, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self._cache[key] = s
        return s

    def panel(self, kind, size, scale=2):
        key = ("panel", kind, size, scale)
        s = self._cache.get(key)
        if s is None:
            s = nine(self.chart[f"panel_{kind}_9slice"], size, (4, 4, 4, 4), scale, tile=True)
            self._cache[key] = s
        return s

    # ------------------------------------------------------------------ ikon dock buatan sendiri
    def _make_blank_dock(self):
        O, B, D = self.pal["O"], self.pal["C"], self.pal["c"]
        s = pygame.Surface((14, 14), pygame.SRCALPHA)
        s.fill(O)
        pygame.draw.rect(s, B, (1, 1, 12, 10))
        pygame.draw.rect(s, D, (1, 11, 12, 2))
        return s

    def _icon(self, painter):
        s = self.blank_dock.copy()
        painter(s, self.pal)
        return s

    def _icon_market(self):
        def p(s, P):
            O = P["O"]
            for x, top, bot, body, col in ((3, 3, 8, (4, 7), P["g"]), (6, 2, 7, (3, 5), P["R"]), (9, 2, 8, (4, 7), P["g"])):
                pygame.draw.line(s, O, (x, top), (x, bot))
                pygame.draw.rect(s, O, (x - 1, body[0], 3, body[1] - body[0] + 1))
                s.set_at((x, body[0] + 1), col)
                s.set_at((x, body[1] - 1), col)
        return self._icon(p)

    def _icon_macro(self):
        def p(s, P):
            for x, h, col in ((2, 3, P["B"]), (5, 5, P["G"]), (8, 7, P["Y"])):
                pygame.draw.rect(s, P["O"], (x, 9 - h, 4, h + 1))
                pygame.draw.rect(s, col, (x + 1, 10 - h, 2, h - 1))
        return self._icon(p)

    def _icon_policy(self):
        def p(s, P):
            for y, kx in ((3, 4), (6, 8), (9, 5)):
                pygame.draw.line(s, P["O"], (2, y), (11, y))
                pygame.draw.rect(s, P["Y"], (kx, y - 1, 3, 3))
                pygame.draw.rect(s, P["O"], (kx, y - 1, 3, 3), 1)
        return self._icon(p)

    def _icon_menu(self):
        def p(s, P):
            for y in (3, 6, 9):
                pygame.draw.line(s, P["O"], (3, y), (10, y))
        return self._icon(p)
