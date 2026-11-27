"""
ui.py -- toolkit UI immediate-mode yang memakai sprite dari pack (panel 9-slice, tombol, toggle, slider, ikon).

Pola: setiap frame `ui.begin(screen)` -> panggil ui.button()/slider()/... (menggambar + mendaftar area klik)
-> `ui.end()` menggambar tooltip. Klik diproses `ui.click(pos)` memakai daftar area dari frame terakhir
(yang digambar paling akhir = paling atas, dicek paling dulu).
"""
import pygame

INK = (30, 27, 46)
CREAM = (244, 241, 222)
CREAM2 = (224, 218, 195)
MUTED = (104, 100, 130)
DARK = (58, 52, 86)
GREEN = (44, 156, 100)
RED = (212, 76, 76)
BLUE = (64, 126, 210)
GOLD = (236, 160, 36)
WHITE = (248, 249, 250)
SOFT_G = (183, 228, 199)
SOFT_R = (242, 132, 130)
SOFT_B = (162, 210, 255)
SOFT_Y = (255, 209, 102)


def fmt_px(v):
    """Harga ala Indonesia: 4.200 / 500.000 / 12,50"""
    if v >= 100:
        return f"{v:,.0f}".replace(",", ".")
    if v >= 10:
        return f"{v:.1f}".replace(".", ",")
    return f"{v:.2f}".replace(".", ",")


class UI:
    def __init__(self, assets):
        self.a = assets
        mono = "couriernew,consolas,dejavusansmono,menlo,monospace"
        self.f = {
            "xs": pygame.font.SysFont(mono, 12, bold=True),
            "s": pygame.font.SysFont(mono, 14, bold=True),
            "m": pygame.font.SysFont(mono, 16, bold=True),
            "l": pygame.font.SysFont(mono, 23, bold=True),
        }
        self.screen = None
        self.hits = []
        self.tip = None
        self.drag = None
        self.scroll = {}
        self.wheel_regions = []
        self.mouse = (0, 0)
        self.down = False

    # ------------------------------------------------------------------ siklus frame
    def begin(self, screen):
        self.screen = screen
        self.hits = []
        self.tip = None
        self.wheel_regions = []
        self.mouse = pygame.mouse.get_pos()
        self.down = pygame.mouse.get_pressed()[0]
        if self.drag and not self.down:
            self.drag = None
        if self.drag:
            self.drag(self.mouse)

    def end(self):
        if self.tip:
            lines = self.tip.split("\n")
            w = max(self.f["s"].size(t)[0] for t in lines) + 16
            h = len(lines) * 18 + 12
            x = min(self.mouse[0] + 14, self.screen.get_width() - w - 4)
            y = min(self.mouse[1] + 16, self.screen.get_height() - h - 4)
            self.panel((x, y, w, h), "dark", 1)
            for i, t in enumerate(lines):
                self.text(t, (x + 8, y + 6 + i * 18), WHITE)

    def click(self, pos):
        for rect, fn in reversed(self.hits):
            if rect.collidepoint(pos):
                fn(pos)
                return True
        return False

    def wheel(self, dy):
        for key, rect, content_h in reversed(self.wheel_regions):
            if rect.collidepoint(self.mouse):
                mx = max(0, content_h - rect.h)
                self.scroll[key] = max(0, min(mx, self.scroll.get(key, 0) - dy * 36))
                return True
        return False

    def blocked(self, pos, rects):
        return any(r.collidepoint(pos) for r in rects)

    # ------------------------------------------------------------------ teks
    def text(self, s, pos, color=INK, font="s", align="l"):
        t = self.f[font].render(str(s), True, color)
        x, y = pos
        if align == "r":
            x -= t.get_width()
        elif align == "c":
            x -= t.get_width() // 2
        self.screen.blit(t, (x, y))
        return t.get_width()

    def bmp(self, s, pos, scale=1, tint=None, align="l"):
        t = self.a.font.render(s, scale, tint)
        x, y = pos
        if align == "r":
            x -= t.get_width()
        elif align == "c":
            x -= t.get_width() // 2
        self.screen.blit(t, (x, y))
        return t.get_width()

    def wrap(self, s, n):
        out, line = [], ""
        for word in s.split():
            if len(line) + len(word) + 1 > n:
                out.append(line)
                line = word
            else:
                line = (line + " " + word).strip()
        if line:
            out.append(line)
        return out

    # ------------------------------------------------------------------ bentuk dasar
    def panel(self, rect, kind="cream", scale=2):
        rect = pygame.Rect(rect)
        self.screen.blit(self.a.panel(kind, rect.size, scale), rect.topleft)
        return rect

    def shadow_panel(self, rect, kind="cream"):
        rect = pygame.Rect(rect)
        sh = pygame.Surface(rect.size, pygame.SRCALPHA)
        sh.fill((20, 18, 36, 90))
        self.screen.blit(sh, (rect.x + 5, rect.y + 5))
        return self.panel(rect, kind)

    def bar(self, rect, frac, color=GREEN, back=CREAM2):
        rect = pygame.Rect(rect)
        frac = max(0.0, min(1.0, frac))
        pygame.draw.rect(self.screen, INK, rect)
        pygame.draw.rect(self.screen, back, rect.inflate(-2, -2))
        w = int((rect.w - 2) * frac)
        if w > 0:
            pygame.draw.rect(self.screen, color, (rect.x + 1, rect.y + 1, w, rect.h - 2))

    def sprite(self, surf, pos, k=1, align="l"):
        s = self.a.scaled(surf, k)
        x, y = pos
        if align == "c":
            x -= s.get_width() // 2
        self.screen.blit(s, (x, y))
        return s

    # ------------------------------------------------------------------ widget
    def hot(self, rect):
        return rect.collidepoint(self.mouse)

    def button(self, rect, label, cb, color="load_seed", fs=1, enabled=True, tip=None, tint=None):
        """color: new_city (hijau) | load_seed (biru) | options (kuning) | exit (merah muda)."""
        rect = pygame.Rect(rect)
        hot = enabled and self.hot(rect)
        state = "disabled" if not enabled else ("pressed" if hot and self.down else ("hover" if hot else "normal"))
        self.screen.blit(self.a.button(color, rect.size, state), rect.topleft)
        if isinstance(label, pygame.Surface):
            self.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.y + 6 + (rect.h - 14 - label.get_height()) // 2))
        elif label:
            t = self.a.font.render(label, fs, tint)
            self.screen.blit(t, (rect.centerx - t.get_width() // 2, rect.y + 6 + (rect.h - 14 - t.get_height()) // 2 + (1 if state == "pressed" else 0)))
        if hot and tip:
            self.tip = tip
        if enabled:
            self.hits.append((rect, lambda pos, cb=cb: cb()))
        return rect

    def dock_button(self, pos, icon, cb, tip, active=False, k=3):
        s = self.a.scaled(icon, k)
        rect = pygame.Rect(pos[0], pos[1], s.get_width(), s.get_height())
        hot = self.hot(rect)
        if active:
            pygame.draw.rect(self.screen, GOLD, rect.inflate(6, 6), border_radius=3)
        self.screen.blit(s, (rect.x, rect.y - (2 if hot else 0)))
        if hot:
            self.tip = tip
        self.hits.append((rect, lambda p, cb=cb: cb()))
        return rect

    def toggle(self, pos, value, cb, label="", color=INK, font="s"):
        spr = self.a.menu["toggle_on" if value else "toggle_off"]
        s = self.a.scaled(spr, 2)
        rect = pygame.Rect(pos[0], pos[1], s.get_width(), s.get_height())
        self.screen.blit(s, rect.topleft)
        if label:
            self.text(label, (rect.right + 10, rect.y + 2), color, font)
        hit = rect.inflate(8 + (self.f[font].size(label)[0] + 10 if label else 0), 4)
        self.hits.append((hit, lambda p: cb(not value)))
        return rect

    def slider(self, rect, value, lo, hi, cb, step=None, key=None):
        """Slider memakai knob dari pack. Bisa di-drag; cb(nilai_baru)."""
        rect = pygame.Rect(rect)
        t = 0.0 if hi == lo else max(0.0, min(1.0, (value - lo) / (hi - lo)))
        pad = 10
        track = pygame.Rect(rect.x, rect.centery - 5, rect.w, 10)
        pygame.draw.rect(self.screen, INK, track, border_radius=4)
        inner = track.inflate(-4, -4)
        pygame.draw.rect(self.screen, self.a.pal["S"], inner, border_radius=3)
        kx = rect.x + pad + int((rect.w - 2 * pad) * t)
        fill = pygame.Rect(inner.x, inner.y, max(0, kx - inner.x), inner.h)
        if fill.w > 0:
            pygame.draw.rect(self.screen, self.a.pal["G"], fill, border_radius=3)
        knob = self.a.scaled(self.a.menu["slider_knob"], 2)
        self.screen.blit(knob, (kx - knob.get_width() // 2, rect.centery - knob.get_height() // 2))

        def apply(pos):
            tt = max(0.0, min(1.0, (pos[0] - rect.x - pad) / max(1, rect.w - 2 * pad)))
            v = lo + (hi - lo) * tt
            if step:
                v = round(v / step) * step
            cb(round(v, 6))

        def down(pos):
            self.drag = apply
            apply(pos)
        self.hits.append((rect.inflate(0, 8), down))
        return rect

    # ------------------------------------------------------------------ scroll
    def scroll_area(self, key, rect, content_h):
        rect = pygame.Rect(rect)
        self.wheel_regions.append((key, rect, content_h))
        mx = max(0, content_h - rect.h)
        off = max(0, min(mx, self.scroll.get(key, 0)))
        self.scroll[key] = off
        return off

    def scrollbar(self, key, rect, content_h):
        rect = pygame.Rect(rect)
        if content_h <= rect.h:
            return
        off = self.scroll.get(key, 0)
        pygame.draw.rect(self.screen, CREAM2, (rect.right - 5, rect.y, 4, rect.h))
        th = max(24, int(rect.h * rect.h / content_h))
        ty = rect.y + int((rect.h - th) * off / max(1, content_h - rect.h))
        pygame.draw.rect(self.screen, INK, (rect.right - 5, ty, 4, th))

    # ------------------------------------------------------------------ chart garis
    def line_chart(self, rect, series, colors, fmt=None, title=None, grid=4, fill=False):
        """series: list of list angka. Latar panel gelap dari pack, garis 2px, label min/max."""
        rect = pygame.Rect(rect)
        self.panel(rect, "dark", 1 if rect.h < 70 else 2)
        data = [s for s in series if len(s) >= 2]
        if title:
            self.text(title, (rect.x + 8, rect.y + 5), (190, 192, 214), "xs")
        if not data:
            return
        lo = min(min(s) for s in data)
        hi = max(max(s) for s in data)
        if hi - lo < 1e-9:
            hi = lo + 1
        pad = (hi - lo) * 0.08
        lo, hi = lo - pad, hi + pad
        top = rect.y + (22 if title else 12)
        pl, pr, pb = rect.x + 8, rect.right - 8, rect.bottom - 10
        ph = pb - top
        for g in range(grid + 1):
            y = top + ph * g / grid
            pygame.draw.line(self.screen, (78, 74, 108), (pl, y), (pr, y))
        f = fmt or (lambda v: f"{v:.2f}" if abs(v) < 100 else f"{v:,.0f}".replace(",", "."))
        for s, col in zip(data, colors):
            pts = [(pl + (pr - pl) * i / (len(s) - 1), pb - ph * (v - lo) / (hi - lo)) for i, v in enumerate(s)]
            if fill:
                poly = pts + [(pts[-1][0], pb), (pts[0][0], pb)]
                sh = pygame.Surface((pr - pl + 2, rect.h), pygame.SRCALPHA)
                pygame.draw.polygon(sh, tuple(col) + (50,), [(x - pl, y - rect.y) for x, y in poly])
                self.screen.blit(sh, (pl, rect.y))
            pygame.draw.lines(self.screen, col, False, pts, 2)
            pygame.draw.circle(self.screen, WHITE, (int(pts[-1][0]), int(pts[-1][1])), 3)
        self.text(f(hi - pad), (rect.right - 10, top - 1), (200, 202, 224), "xs", "r")
        self.text(f(lo + pad), (rect.right - 10, pb - 13), (200, 202, 224), "xs", "r")


def parse_money(s):
    """'5jt' '250rb' '1.5m'(miliar) '2t'(triliun) -> angka rupiah, atau None kalau tidak valid."""
    s = s.strip().lower().replace(",", ".").replace(" ", "").replace("rp", "")
    mult = 1
    for suf, m in (("miliar", 1e9), ("juta", 1e6), ("ribu", 1e3), ("jt", 1e6), ("rb", 1e3), ("k", 1e3),
                   ("m", 1e9), ("t", 1e12)):
        if s.endswith(suf):
            mult, s = m, s[:-len(suf)]
            break
    try:
        return float(s) * mult
    except ValueError:
        return None
