"""
windows.py -- jendela besar yang dibuka dari dock:
  PASAR (chart candlestick + panel kontrol pasar) · MAKRO (gauge) · KEBIJAKAN · USAHA · PROPERTI
Setiap fungsi menerima `sc` (GameScene) dan `C` (Rect area isi jendela).
"""
import pygame

from systems.ekonomi_core import POLICY_FIELDS, PRODUCTION_RECIPES, Policy, rp
from game.ui import (INK, CREAM, CREAM2, MUTED, GREEN, RED, BLUE, GOLD, WHITE,
                     SOFT_G, SOFT_R, SOFT_B, SOFT_Y, fmt_px)

TFS = (("1D", 1), ("1W", 7), ("1M", 30))


def pct(v, d=1):
    return f"{v * 100:+.{d}f}%"


def trend_icon(sc, change, pos, k=2, eps=0.002):
    name = "trend_up" if change > eps else ("trend_down" if change < -eps else "trend_flat")
    sc.ui.sprite(sc.a.chart[name], pos, k)


def hit(sc, rect, fn):
    sc.ui.hits.append((pygame.Rect(rect), lambda p, fn=fn: fn()))


def fmt_policy(kind, v):
    if kind == "rp":
        return rp(v)
    if kind == "pct":
        return f"{v * 100:.0f}%"
    if kind == "pct1":
        return f"{v * 100:.1f}%"
    return f"{v * 100:.2f}%"


# ======================================================================= PASAR
def candle_sprite(a, candle):
    o, h, l, c, _ = candle
    ch = c / o - 1
    if abs(ch) < 0.002:
        return a.chart["candle_doji"]
    if ch > 0:
        return a.chart["candle_bull_strong" if ch > 0.02 else "candle_bull_small"]
    return a.chart["candle_bear_strong" if ch < -0.02 else "candle_bear_small"]


def market_window(sc, C):
    ui, a, w = sc.ui, sc.a, sc.world
    m = w.market
    st = sc.ws.setdefault("market", {"sym": "KOTA", "tf": 0, "mode": "candle", "ma": True, "vol": True})
    asset = m.assets[st["sym"]]
    scr = ui.screen

    # ---- strip indeks
    x = C.x
    for name, kind in (("IHSK SAHAM", "stock"), ("IKRP KRIPTO", "crypto")):
        s = m.index(kind)
        ch = s[-1] / s[-min(len(s), 15)] - 1
        r = pygame.Rect(x, C.y, 214, 36)
        ui.panel(r, "dark", 1)
        ui.bmp(name, (r.x + 10, r.y + 6), 1, (190, 192, 214))
        ui.bmp(f"{s[-1]:.1f}".replace(".", ","), (r.x + 10, r.y + 20), 1, WHITE)
        trend_icon(sc, ch, (r.right - 30, r.y + 10))
        ui.bmp(pct(ch).replace(" ", ""), (r.right - 36, r.y + 14), 1, SOFT_G if ch >= 0 else SOFT_R, "r")
        x += 222
    fg = m.fear_greed()
    mood = "TAKUT" if fg < 0.33 else ("SERAKAH" if fg > 0.67 else "NETRAL")
    r = pygame.Rect(x, C.y, 180, 36)
    ui.panel(r, "dark", 1)
    ui.bmp("SENTIMEN", (r.x + 10, r.y + 6), 1, (190, 192, 214))
    ui.bmp(mood, (r.x + 10, r.y + 20), 1, SOFT_Y)
    port = sum(c.holdings_value for c in w.citizens)
    r = pygame.Rect(x + 188, C.y, C.right - x - 188, 36)
    ui.panel(r, "dark", 1)
    ui.bmp("PORTOFOLIO WARGA", (r.x + 10, r.y + 6), 1, (190, 192, 214))
    ui.bmp(rp(port), (r.x + 10, r.y + 20), 1, WHITE)

    top = C.y + 44
    # ---- kolom kiri: daftar aset
    L = pygame.Rect(C.x, top, 250, C.h - 44)
    y = L.y
    for group, kind in (("SAHAM", "stock"), ("KRIPTO", "crypto")):
        ui.text(group, (L.x + 2, y), MUTED, "xs")
        y += 16
        for sym, s in m.assets.items():
            if s.kind != kind:
                continue
            row = pygame.Rect(L.x, y, L.w, 38)
            sel = sym == st["sym"]
            hot = ui.hot(row)
            pygame.draw.rect(scr, SOFT_Y if sel else (CREAM if not hot else WHITE), row, border_radius=4)
            pygame.draw.rect(scr, INK, row, 2 if sel else 1, border_radius=4)
            cs = m.candles(sym, 1, 1)[0]
            ui.sprite(candle_sprite(a, cs), (row.x + 6, row.y + 3), 2)
            ui.text(sym, (row.x + 26, row.y + 3), INK, "m")
            ui.text(s.name[:11], (row.x + 26, row.y + 21), MUTED, "xs")
            ch = s.change(30)
            spark = "spark_up" if ch > 0.015 else ("spark_down" if ch < -0.015 else "spark_flat")
            ui.sprite(a.chart[spark], (row.x + 112, row.y + 9), 1)
            if s.halted:
                ui.sprite(a.chart["alert_icon"], (row.x + 138, row.y + 10), 2)
            ui.text(fmt_px(s.price), (row.right - 6, row.y + 3), INK, "s", "r")
            ui.text(pct(ch), (row.right - 6, row.y + 20), GREEN if ch >= 0 else RED, "xs", "r")
            hit(sc, row, lambda sym=sym: st.update(sym=sym))
            y += 42
        y += 4
    # gauge fear & greed + slider sentimen
    gy = y + 2
    ui.text("SENTIMEN PASAR", (L.x + 2, gy), MUTED, "xs")
    g = "gauge_low" if fg < 0.33 else ("gauge_high" if fg > 0.67 else "gauge_mid")
    ui.sprite(a.chart[g], (L.x + 4, gy + 14), 4)
    ui.text("TAKUT", (L.x + 140, gy + 38), GREEN, "xs")
    ui.text(f"{fg * 100:.0f}/100", (L.x + 140, gy + 54), INK, "s")
    ui.text("Geser = paksa mood pasar", (L.x + 2, gy + 84), MUTED, "xs")
    ui.slider((L.x, gy + 98, L.w, 24), m.sent, -0.12, 0.12, w.set_sentiment, 0.005)

    # ---- kolom tengah: chart
    M = pygame.Rect(C.x + 258, top, 438, C.h - 44)
    ch30 = asset.change(30)
    ui.text(f"{asset.name}", (M.x, M.y), INK, "l")
    ui.text(f"{asset.sym} · {'SAHAM' if asset.kind == 'stock' else 'KRIPTO'}", (M.x, M.y + 26), MUTED, "xs")
    ui.bmp(fmt_px(asset.price), (M.right - 4, M.y + 2), 2, None, "r")
    trend_icon(sc, ch30, (M.right - 30, M.y + 24))
    ui.bmp(pct(ch30), (M.right - 36, M.y + 28), 1, SOFT_G if ch30 >= 0 else SOFT_R, "r")
    if asset.halted:
        ui.button((M.x + 190, M.y + 6, 120, 26), "TRADING HALT", lambda: None, "exit", 1)
    # kontrol chart
    by = M.y + 52
    bx = M.x
    for i, (name, _) in enumerate(TFS):
        ui.button((bx, by, 44, 26), name, lambda i=i: st.update(tf=i), "new_city" if st["tf"] == i else "load_seed", 1)
        bx += 48
    ui.button((bx + 6, by, 70, 26), "GARIS" if st["mode"] == "candle" else "CANDLE",
              lambda: st.update(mode="line" if st["mode"] == "candle" else "candle"), "options", 1, tip="Ganti tampilan chart")
    ui.button((bx + 82, by, 44, 26), "MA", lambda: st.update(ma=not st["ma"]), "new_city" if st["ma"] else "load_seed", 1,
              tip="Moving average 7 candle")
    ui.button((bx + 130, by, 52, 26), "VOL", lambda: st.update(vol=not st["vol"]), "new_city" if st["vol"] else "load_seed", 1,
              tip="Volume transaksi")
    tf = TFS[st["tf"]][1]
    candles = m.candles(asset.sym, tf, 60)
    chart_r = pygame.Rect(M.x, by + 34, M.w, 232 if st["vol"] else 292)
    price_chart(sc, chart_r, candles, st, tf)
    cy = chart_r.bottom + 4
    if st["vol"]:
        vol_r = pygame.Rect(M.x, cy, M.w, 52)
        volume_chart(sc, vol_r, candles)
        cy = vol_r.bottom + 8
    else:
        cy += 4
    # statistik
    last = candles[-1]
    holders = [c for c in w.citizens if asset.sym in c.hold]
    units = sum(c.hold[asset.sym][0] for c in holders)
    avg_cost = sum(c.hold[asset.sym][0] * c.hold[asset.sym][1] for c in holders) / units if units else 0
    h30 = max(list(asset.hist)[-30:])
    l30 = min(list(asset.hist)[-30:])
    stats = [("Open", fmt_px(last[0])), ("High", fmt_px(last[1])), ("Low", fmt_px(last[2])), ("Close", fmt_px(last[3])),
             ("Tertinggi 30H", fmt_px(h30)), ("Terendah 30H", fmt_px(l30)), ("Rata2 beli warga", fmt_px(avg_cost) if units else "-"),
             ("Volume", rp(last[4]))]
    for i, (k, v) in enumerate(stats):
        px, py = M.x + (i % 2) * 222, cy + (i // 2) * 17
        ui.text(k, (px, py), MUTED, "xs")
        ui.text(v, (px + 212, py), INK, "xs", "r")

    # ---- kolom kanan: kontrol pasar
    Rt = pygame.Rect(C.x + 704, top, C.w - 704, C.h - 44)
    ui.panel(Rt, "dark", 1)
    x0, wv = Rt.x + 10, Rt.w - 20
    y = Rt.y + 8
    ui.bmp("KONTROL PASAR", (x0, y), 1, SOFT_Y)
    ui.text(asset.sym, (Rt.right - 10, y - 3), WHITE, "m", "r")
    y += 20
    if asset.halted:
        ui.button((x0, y, wv, 30), "BUKA PERDAGANGAN", lambda: w.toggle_halt(asset.sym), "new_city", 1)
    else:
        ui.button((x0, y, wv, 30), "HENTIKAN TRADING", lambda: w.toggle_halt(asset.sym), "exit", 1,
                  tip="Warga tidak bisa beli/jual, harga membeku")
    y += 36
    ui.text("Volatilitas", (x0, y), (200, 202, 224), "xs")
    ui.text(f"{asset.vol_mult:.1f}x", (x0 + wv, y), WHITE, "xs", "r")
    ui.slider((x0, y + 12, wv, 22), asset.vol_mult, 0.1, 3.0, lambda v: w.set_vol_mult(asset.sym, v), 0.1)
    y += 40
    ui.text("Tren (bias per tahun)", (x0, y), (200, 202, 224), "xs")
    ui.text(f"{asset.bias * 100:+.0f}%", (x0 + wv, y), SOFT_G if asset.bias >= 0 else SOFT_R, "xs", "r")
    ui.slider((x0, y + 12, wv, 22), asset.bias, -1.0, 1.0, lambda v: w.set_bias(asset.sym, v), 0.05)
    y += 42
    hw = (wv - 6) // 2
    ui.button((x0, y, hw, 28), "CRASH -30%", lambda: w.shock(asset.sym, 0.7), "exit", 1)
    ui.button((x0 + hw + 6, y, hw, 28), "BOOM +30%", lambda: w.shock(asset.sym, 1.3), "new_city", 1)
    y += 32
    tw = (wv - 12) // 3
    ui.button((x0, y, tw, 26), "-10%", lambda: w.shock(asset.sym, 0.9), "exit", 1)
    ui.button((x0 + tw + 6, y, tw, 26), "+10%", lambda: w.shock(asset.sym, 1.1), "new_city", 1)
    ui.button((x0 + 2 * (tw + 6), y, tw, 26), "SET", lambda: sc.open_prompt(f"Harga baru {asset.sym}", lambda v: w.set_price(asset.sym, v)),
              "options", 1, tip="Ketik harga baru, contoh 5000 atau 2.5rb")
    y += 32
    ui.button((x0, y, hw, 26), "DUKUNG +100JT", lambda: w.push_price(asset.sym, 1e8), "new_city", 1,
              tip="Suntik arus beli, harga naik besok")
    ui.button((x0 + hw + 6, y, hw, 26), "TEKAN -100JT", lambda: w.push_price(asset.sym, -1e8), "exit", 1,
              tip="Arus jual besar, harga turun besok")
    y += 36
    ui.bmp("GLOBAL", (x0, y), 1, SOFT_Y)
    y += 14
    ui.button((x0, y, hw, 26), "BULL RUN", lambda: w.set_sentiment(0.08), "new_city", 1)
    ui.button((x0 + hw + 6, y, hw, 26), "BEAR MARKET", lambda: w.set_sentiment(-0.08), "exit", 1)
    y += 30
    ui.button((x0, y, wv, 24), "RESET SEMUA KONTROL", w.reset_market_controls, "options", 1)
    y += 30
    p = w.policy
    for label, key in (("Pajak jual saham", "tax_stock"), ("Pajak jual kripto", "tax_crypto")):
        ui.text(label, (x0, y), (200, 202, 224), "xs")
        ui.text(f"{getattr(p, key) * 100:.2f}%", (x0 + wv, y), WHITE, "xs", "r")
        ui.slider((x0, y + 10, wv, 22), getattr(p, key), 0, 0.05, lambda v, key=key: setattr(p, key, v), 0.0005)
        y += 36
    ui.text(f"Pemegang {asset.sym}: {len(holders)} warga", (x0, y), (200, 202, 224), "xs")
    ui.text(rp(units * asset.price), (x0 + wv, y), WHITE, "xs", "r")


def price_chart(sc, r, candles, st, tf):
    ui, a, w = sc.ui, sc.a, sc.world
    scr = ui.screen
    P = a.pal
    ui.panel(r, "dark", 1)
    n = len(candles)
    if n < 2:
        return
    inner = pygame.Rect(r.x + 8, r.y + 10, r.w - 74, r.h - 28)
    ma = []
    if st["ma"] and n >= 7:
        cl = [c[3] for c in candles]
        ma = [sum(cl[max(0, i - 6):i + 1]) / len(cl[max(0, i - 6):i + 1]) for i in range(n)]
    lo = min(c[2] for c in candles)
    hi = max(c[1] for c in candles)
    pad = (hi - lo) * 0.06 or hi * 0.01
    lo, hi = lo - pad, hi + pad
    yv = lambda v: inner.bottom - inner.h * (v - lo) / (hi - lo)
    for g in range(5):
        gy = inner.y + inner.h * g / 4
        pygame.draw.line(scr, (80, 76, 112), (inner.x, gy), (inner.right, gy))
        ui.text(fmt_px(hi - (hi - lo) * g / 4), (r.right - 6, gy - 7), (190, 192, 214), "xs", "r")
    step = inner.w / n
    for i in range(0, n, max(1, n // 6)):
        day = w.day - (n - 1 - i) * tf
        ui.text(f"H{day}", (inner.x + step * (i + 0.5), r.bottom - 15), (150, 152, 180), "xs", "c")
    if st["mode"] == "line":
        pts = [(inner.x + step * (i + 0.5), yv(c[3])) for i, c in enumerate(candles)]
        up = candles[-1][3] >= candles[0][3]
        col = P["G"] if up else P["R"]
        sh = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.polygon(sh, tuple(col) + (60,), [(x - r.x, y - r.y) for x, y in pts + [(pts[-1][0], inner.bottom), (pts[0][0], inner.bottom)]])
        scr.blit(sh, r.topleft)
        pygame.draw.lines(scr, col, False, pts, 2)
    else:
        cw = max(3, int(step * 0.72)) | 1
        for i, (o, h, l, c, v) in enumerate(candles):
            cx = int(inner.x + step * (i + 0.5))
            up = c >= o
            pygame.draw.line(scr, (196, 198, 220), (cx, int(yv(h))), (cx, int(yv(l))))
            top_y, bot_y = int(yv(max(o, c))), int(yv(min(o, c)))
            body = pygame.Rect(cx - cw // 2, top_y, cw, max(3, bot_y - top_y))
            pygame.draw.rect(scr, INK, body)
            pygame.draw.rect(scr, P["G"] if up else P["R"], body.inflate(-2, -2))
    if ma:
        pts = [(inner.x + step * (i + 0.5), yv(v)) for i, v in enumerate(ma)]
        pygame.draw.lines(scr, SOFT_Y, False, pts, 2)
    # garis harga terakhir
    lc = candles[-1][3]
    ly = int(yv(lc))
    for x in range(inner.x, inner.right, 8):
        pygame.draw.line(scr, (255, 255, 255), (x, ly), (x + 3, ly))
    tag = pygame.Rect(inner.right + 2, ly - 8, 62, 16)
    pygame.draw.rect(scr, P["G"] if candles[-1][3] >= candles[-1][0] else P["R"], tag, border_radius=3)
    pygame.draw.rect(scr, INK, tag, 1, border_radius=3)
    ui.text(fmt_px(lc), (tag.centerx, tag.y + 1), INK, "xs", "c")
    # crosshair
    mx, my = ui.mouse
    if inner.collidepoint(mx, my):
        i = max(0, min(n - 1, int((mx - inner.x) / step)))
        cx = int(inner.x + step * (i + 0.5))
        pygame.draw.line(scr, (210, 212, 236), (cx, inner.y), (cx, inner.bottom))
        pygame.draw.line(scr, (210, 212, 236), (inner.x, my), (inner.right, my))
        o, h, l, c, v = candles[i]
        info = f"H{w.day - (n - 1 - i) * tf}  O {fmt_px(o)}  H {fmt_px(h)}  L {fmt_px(l)}  C {fmt_px(c)}  V {rp(v)}"
        tw = ui.f["xs"].size(info)[0] + 10
        ib = pygame.Rect(inner.x + 4, inner.y + 2, tw, 16)
        pygame.draw.rect(scr, INK, ib, border_radius=3)
        ui.text(info, (ib.x + 5, ib.y + 1), WHITE, "xs")
        pv = hi - (hi - lo) * (my - inner.y) / inner.h
        pl = pygame.Rect(inner.right + 2, my - 8, 62, 16)
        pygame.draw.rect(scr, WHITE, pl, border_radius=3)
        ui.text(fmt_px(pv), (pl.centerx, pl.y + 1), INK, "xs", "c")


def volume_chart(sc, r, candles):
    ui, a = sc.ui, sc.a
    ui.panel(r, "dark", 1)
    n = len(candles)
    if n < 2:
        return
    inner = pygame.Rect(r.x + 8, r.y + 6, r.w - 74, r.h - 12)
    mv = max(c[4] for c in candles) or 1
    step = inner.w / n
    bw = max(2, int(step * 0.72))
    for i, c in enumerate(candles):
        hh = max(1, int(inner.h * c[4] / mv))
        col = a.pal["g"] if c[3] >= c[0] else a.pal["r"]
        pygame.draw.rect(ui.screen, col, (int(inner.x + step * (i + 0.5) - bw / 2), inner.bottom - hh, bw, hh))
    ui.text("VOL", (r.right - 6, r.y + 4), (190, 192, 214), "xs", "r")
    ui.text(rp(mv), (r.right - 6, r.y + 18), (150, 152, 180), "xs", "r")


# ======================================================================= MAKRO
def gauge_level(v, lo, hi):
    return "gauge_low" if v < lo else ("gauge_mid" if v < hi else "gauge_high")


def macro_window(sc, C):
    ui, a, w = sc.ui, sc.a, sc.world
    S = w.series
    civilization = w.civilization_observation()
    ihk = list(S["ihk"])
    infl = (ihk[-1] / ihk[-7] - 1) * 100 if len(ihk) >= 7 else 0.0
    bank_liq = w.bank.cash / max(1.0, w.bank.deposits) if w.bank.deposits > 1 else 9.9
    unemp = w.unemployment() * 100
    cards = [
        ("PENGANGGURAN", gauge_level(unemp, 10, 22), f"{unemp:.1f}%", "Rendah = bagus", "nganggur", -1),
        ("INFLASI 30 HARI", gauge_level(abs(infl), 1.5, 4), f"{infl:+.1f}%", "Harga barang vs bulan lalu", "ihk", -1),
        ("KETIMPANGAN", gauge_level(w.gini_now(), 0.35, 0.5), f"GINI {w.gini_now():.2f}", "0 = merata, 1 = timpang", "gini", -1),
        ("KESEHATAN BANK", gauge_level(-min(bank_liq, 2.0), -0.5, -0.25), (f"{min(bank_liq, 9.99) * 100:.0f}% KAS" if w.bank.deposits > 1 else "BELUM ADA"),
         (f"Org {civilization['active_organizations']} · "
          f"klaim valid {civilization['validated_claims']}"), None, 0),
    ]
    cw = (C.w - 24) // 4
    for i, (title, g, val, sub, key, _) in enumerate(cards):
        r = pygame.Rect(C.x + i * (cw + 8), C.y, cw, 196)
        ui.panel(r, "cream")
        ui.bmp(title, (r.centerx, r.y + 12), 1, None, "c")
        ui.sprite(a.chart[g], (r.centerx - 64, r.y + 30), 4)
        ui.bmp(val, (r.centerx, r.y + 104), 2, None, "c")
        ui.text(sub, (r.centerx, r.y + 128), MUTED, "xs", "c")
        if key:
            s = list(S[key])
            ch = (s[-1] - s[-min(len(s), 8)]) if len(s) > 1 else 0
            trend_icon(sc, ch, (r.x + 14, r.y + 152), 2, 1e-6)
            ui.text("naik" if ch > 1e-6 else ("turun" if ch < -1e-6 else "stabil"), (r.x + 36, r.y + 154), INK, "xs")
        else:
            ui.text(f"Untung {rp(w.bank.profit)}", (r.x + 14, r.y + 148), GREEN, "xs")
            ui.text(f"Rugi {rp(w.bank.loss)}", (r.x + 14, r.y + 164), RED, "xs")
    metrics = [("uang", "Rata2 uang warga", BLUE), ("kekayaan", "Kekayaan median", (110, 214, 150)),
               ("nganggur", "Pengangguran %", (246, 120, 120)), ("gini", "Gini", (255, 190, 90)),
               ("ihk", "IHK (harga)", (200, 150, 240)), ("pdb", "PDB 30 hari", (110, 214, 214)),
               ("kas_kota", "Kas Kota", (255, 214, 90)), ("penduduk", "Penduduk", (240, 240, 240)),
               ("emosi", "Kepuasan warga", (250, 170, 110)), ("kriminal", "Kejadian kriminal %", (220, 100, 110))]
    ch_h = (C.h - 196 - 8 - 16) // 3
    for i, (key, label, col) in enumerate(metrics):
        r = pygame.Rect(C.x + (i % 4) * (cw + 8), C.y + 204 + (i // 4) * (ch_h + 8), cw, ch_h)
        fmt = None if key in ("gini", "nganggur", "ihk", "penduduk", "emosi", "kriminal") else (lambda v: rp(v))
        ui.line_chart(r, [list(S[key])], [col], fmt, title=label, fill=True)


# ======================================================================= KEBIJAKAN
PRESETS = {
    "STIMULUS": dict(welfare=2_000_000, tax_pph=0.03, tax_ppn=0.08, loan_rate=0.07, deposit_rate=0.04, min_wage=3_500_000),
    "AUSTERITY": dict(welfare=500_000, tax_pph=0.10, tax_ppn=0.14, loan_rate=0.14, deposit_rate=0.07, min_wage=2_750_000),
}


def policy_window(sc, C):
    ui, w = sc.ui, sc.world
    p = w.policy
    colw = 600
    ui.text("Geser slider atau klik +/- untuk mengubah pajak & kebijakan kota.", (C.x, C.y), MUTED, "s")
    mayor = next((c for c in w.citizens if c.id == w.mayor_id), None)
    mayor_name = mayor.first if mayor else "belum terpilih"
    ui.text(f"Wali kota: {mayor_name}", (C.right - 300, C.y + 2), INK, "xs")
    ui.button((C.right - 148, C.y - 2, 148, 24),
              "OTOMATIS: AKTIF" if w.auto_policy else "OTOMATIS: MATI",
              lambda: setattr(w, "auto_policy", not w.auto_policy),
              "new_city" if w.auto_policy else "exit", 1,
              tip="Wali kota menyesuaikan pajak dan bansos tiap kuartal")
    y = C.y + 26
    for key, label, step, lo, hi, kind in POLICY_FIELDS:
        v = getattr(p, key)
        ui.text(label, (C.x, y + 6), INK, "m")
        ui.slider((C.x + 190, y, 230, 28), v, lo, hi, lambda nv, key=key: setattr(p, key, round(nv, 6)), step)
        ui.text(fmt_policy(kind, v), (C.x + 520, y + 6), INK, "m", "r")

        def chg(d, key=key, step=step, lo=lo, hi=hi):
            setattr(p, key, round(min(hi, max(lo, getattr(p, key) + d * step)), 6))
        ui.button((C.x + 530, y, 28, 28), "-", lambda chg=chg: chg(-1), "exit", 1)
        ui.button((C.x + 562, y, 28, 28), "+", lambda chg=chg: chg(1), "new_city", 1)
        y += 40
    x = C.x + colw + 20
    wv = C.right - x
    ui.bmp("PRESET", (x, C.y + 4), 1, None)
    y = C.y + 24
    for name, vals in PRESETS.items():
        ui.button((x, y, wv, 30), name, lambda vals=vals: [setattr(p, k, v) for k, v in vals.items()],
                  "new_city" if name == "STIMULUS" else "exit", 1, tip="Ubah banyak kebijakan sekaligus")
        y += 36
    ui.button((x, y, wv, 30), "KEMBALI NORMAL", lambda: w.__setattr__("policy", Policy()), "options", 1)
    y += 48
    ui.bmp("KAS KOTA", (x, y), 1)
    ui.bmp(rp(w.treasury), (x, y + 16), 2, (60, 150, 100))
    ui.text(f"Pemasukan pekan ini {rp(w.rev_week)}", (x, y + 40), MUTED, "xs")
    y += 62
    hw = (wv - 6) // 2
    ui.button((x, y, hw, 28), "+500JT", lambda: w.print_money(500_000_000), "new_city", 1)
    ui.button((x + hw + 6, y, hw, 28), "-500JT", lambda: w.adjust_treasury(-500_000_000), "exit", 1)
    y += 34
    ui.button((x, y, hw, 28), "+5M", lambda: w.print_money(5_000_000_000), "new_city", 1)
    ui.button((x + hw + 6, y, hw, 28), "SET", lambda: sc.open_prompt("Kas kota baru", w.set_treasury), "options", 1)
    y += 48
    ui.bmp("CATATAN", (x, y), 1)
    for i, ln in enumerate(("Pajak naik = kas kota naik,", "daya beli warga turun.", "Bunga naik = kredit usaha", "lebih sulit & KPR mahal.", "Bansos naik = kas kota cepat", "habis tapi warga tetap makan.")):
        ui.text(ln, (x, y + 18 + i * 15), MUTED, "xs")


# ======================================================================= USAHA
def biz_window(sc, C):
    ui, a, w = sc.ui, sc.a, sc.world
    biz = sorted(w.businesses, key=lambda b: -b.last_profit)
    fac = sum(1 for b in biz if b.kind in ("factory", "car_factory", "builder"))
    farms = sum(1 for b in biz if b.kind == "farm")
    dealers = sum(1 for b in biz if b.kind == "showroom")
    services = sum(1 for b in biz if b.kind in ("repair", "delivery", "cleaning"))
    employment = w.employment_stats()
    shops = sum(1 for b in biz if b.kind == "shop")
    stats = [("PABRIK/BANGUN", str(fac)), ("KEBUN", str(farms)), ("TOKO/DEALER", str(shops + dealers)),
             ("JASA", str(services)),
             ("FT/PT/GIG", f"{employment['full_time']}/{employment['part_time']}/{employment['informal']}"),
             ("KAS BANK", rp(w.bank.cash))]
    sw = (C.w - 40) // 6
    for i, (k, v) in enumerate(stats):
        r = pygame.Rect(C.x + i * (sw + 8), C.y, sw, 38)
        ui.panel(r, "dark", 1)
        ui.bmp(k, (r.x + 8, r.y + 6), 1, (190, 192, 214))
        ui.bmp(v, (r.x + 8, r.y + 20), 1, WHITE)
    L = pygame.Rect(C.x, C.y + 48, 600, C.h - 48)
    ui.panel(L, "cream", 1)
    heads = (("USAHA", 10), ("KAS", 250), ("PEKERJA", 340), ("LABA/BLN", 440), ("UMUR", 560))
    for k, x in heads:
        ui.bmp(k, (L.x + x, L.y + 10), 1, MUTED)
    area = pygame.Rect(L.x + 6, L.y + 28, L.w - 12, L.h - 34)
    rh = 28
    off = ui.scroll_area("biz", area, len(biz) * rh)
    if sc.sel_biz not in biz:
        sc.sel_biz = biz[0] if biz else None
    for i, b in enumerate(biz):
        y = area.y + i * rh - off
        if y < area.y or y + rh > area.bottom:
            continue
        row = pygame.Rect(area.x, y, area.w - 8, rh - 2)
        sel = b is sc.sel_biz
        pygame.draw.rect(ui.screen, SOFT_Y if sel else (CREAM if i % 2 else CREAM2), row, border_radius=3)
        icon = a.building("shop" if b.kind in ("shop", "showroom") else "factory")
        ui.screen.blit(pygame.transform.scale(icon, (24, 20)), (row.x + 4, row.y + 3))
        ui.text(b.name[:20], (row.x + 34, row.y + 5), INK, "s")
        ui.text(rp(b.cash), (row.x + 240, row.y + 5), INK, "s")
        ui.text(f"{len(b.workers)}/{b.max_workers}", (row.x + 330, row.y + 5), INK, "s")
        ui.text(rp(b.last_profit), (row.x + 430, row.y + 5), GREEN if b.last_profit >= 0 else RED, "s")
        ui.text(f"{b.age_days}H", (row.x + 550, row.y + 5), MUTED, "s")
        if ui.hot(row):
            pygame.draw.rect(ui.screen, INK, row, 1, border_radius=3)
        hit(sc, row, lambda b=b: setattr(sc, "sel_biz", b))
    ui.scrollbar("biz", area, len(biz) * rh)
    # detail
    D = pygame.Rect(C.x + 608, C.y + 48, C.w - 608, C.h - 48)
    ui.panel(D, "cream", 1)
    b = sc.sel_biz
    if b is None:
        ui.text("Belum ada usaha di kota.", (D.x + 14, D.y + 14), MUTED, "s")
        return
    x = D.x + 14
    ui.screen.blit(a.scaled(a.building("shop" if b.kind in ("shop", "showroom") else "factory"), 1),
                   (D.centerx - 32, D.y + 10))
    ui.text(b.name, (D.centerx, D.y + 66), INK, "m", "c")
    kind_label = {"factory": "Pabrik", "farm": "Kebun", "shop": "Toko",
                  "showroom": "Showroom mobil", "car_factory": "Pabrik mobil",
                  "builder": "Industri bangunan", "repair": "Jasa servis",
                  "delivery": "Jasa antar", "cleaning": "Jasa kebersihan"}[b.kind]
    ui.text(f"{kind_label} · umur {b.age_days} hari", (D.centerx, D.y + 86), MUTED, "xs", "c")
    recipe = PRODUCTION_RECIPES.get(b.kind)
    product_labels = {
        "food": "pangan", "goods": "barang", "vehicles": "kendaraan",
        "construction": "konstruksi", "repair": "servis",
        "delivery": "antar", "cleaning": "kebersihan",
    }
    if recipe:
        failure = {
            "labor": "· tenaga kerja kurang",
            "inputs_or_cash": "· input/kas kurang",
        }.get(b.production_failed, "")
        production = (
            f"{b.prod:.2f} {product_labels[recipe['product']]}/hari {failure}"
        )
        inputs = " · ".join(
            f"{name} {quantity:.1f}"
            for name, quantity in sorted(b.input_inventory.items())
        ) or "habis"
    else:
        production, inputs = "ritel / stok ulang", "-"
    rows = [("Pemilik", b.owner.name[:18]), ("Kas usaha", rp(b.cash)),
            ("Nilai aset usaha", rp(b.asset_value)),
            ("Utang", rp(b.loan.balance) if b.loan else "-"),
            ("Ekuitas usaha", rp(b.asset_value - (b.loan.balance if b.loan else 0))),
            ("Gaji dasar", rp(b.wage)), ("Harga jual", rp(b.price)),
            ("Stok", f"{b.stock:.0f} unit / {b.car_stock:.1f} mobil"),
            ("Jam kerja", f"{b.work_hours:.0f} jam/minggu"),
            ("Produksi", production), ("Input", inputs),
            ("Laba bln lalu", rp(b.last_profit)), ("Bulan rugi", str(b.loss_months))]
    y = D.y + 108
    for k, v in rows:
        ui.text(k, (x, y), MUTED, "s")
        ui.text(v, (D.right - 14, y), INK, "s", "r")
        y += 20
    y += 6
    ui.text("Pekerja:", (x, y), INK, "s")
    for i, wk in enumerate(b.workers[:4]):
        ui.text(f"- {wk.name[:22]}", (x, y + 16 + i * 14), MUTED, "xs")
    y += 78
    hw = (D.w - 34) // 3
    ui.button((x, y, hw, 26), "+10JT", lambda: w.edit_business_cash(b, 1e7), "new_city", 1)
    ui.button((x + hw + 3, y, hw, 26), "+50JT", lambda: w.edit_business_cash(b, 5e7), "new_city", 1)
    ui.button((x + 2 * (hw + 3), y, hw, 26), "-10JT", lambda: w.edit_business_cash(b, -1e7), "exit", 1)
    y += 32
    ui.button((x, y, D.w - 28, 26), "LIHAT PEMILIK", lambda: sc.select_citizen(b.owner), "load_seed", 1)


# ======================================================================= PROPERTI
def house_window(sc, C):
    ui, a, w = sc.ui, sc.a, sc.world
    hs = w.houses
    occ = sum(len(h.occupants) for h in hs) / max(1, sum(h.cap for h in hs))
    homeless = sum(1 for c in w.citizens if c.home is None)
    avg = sum(h.value for h in hs) / max(1, len(hs))
    owned = sum(1 for h in hs if h.owner)
    stats = [("TERISI", f"{occ * 100:.0f}%"), ("TUNAWISMA", str(homeless)), ("RATA2 NILAI", rp(avg)),
             ("DIMILIKI WARGA", f"{owned}/{len(hs)}"), ("KPR AKTIF", str(sum(1 for l in w.loans if l.kind == "mortgage")))]
    sw = (C.w - 32) // 5
    for i, (k, v) in enumerate(stats):
        r = pygame.Rect(C.x + i * (sw + 8), C.y, sw, 38)
        ui.panel(r, "dark", 1)
        ui.bmp(k, (r.x + 8, r.y + 6), 1, (190, 192, 214))
        ui.bmp(v, (r.x + 8, r.y + 20), 1, WHITE)
    L = pygame.Rect(C.x, C.y + 48, 600, C.h - 48)
    ui.panel(L, "cream", 1)
    for k, x in (("RUMAH", 10), ("PENGHUNI", 100), ("PEMILIK", 200), ("NILAI", 380), ("SEWA/ORANG", 470)):
        ui.bmp(k, (L.x + x, L.y + 10), 1, MUTED)
    area = pygame.Rect(L.x + 6, L.y + 28, L.w - 12, L.h - 34)
    rh = 28
    off = ui.scroll_area("house", area, len(hs) * rh)
    if sc.sel_house not in hs:
        sc.sel_house = hs[0] if hs else None
    for i, h in enumerate(hs):
        y = area.y + i * rh - off
        if y < area.y or y + rh > area.bottom:
            continue
        row = pygame.Rect(area.x, y, area.w - 8, rh - 2)
        sel = h is sc.sel_house
        pygame.draw.rect(ui.screen, SOFT_Y if sel else (CREAM if i % 2 else CREAM2), row, border_radius=3)
        ui.screen.blit(pygame.transform.scale(a.building(f"house_{h.color_i}"), (24, 20)), (row.x + 4, row.y + 3))
        ui.text(f"#{i + 1}", (row.x + 34, row.y + 5), INK, "s")
        ui.text(f"{len(h.occupants)}/{h.cap}", (row.x + 96, row.y + 5), INK, "s")
        ui.text(h.owner.first[:14] if h.owner else "KOTA", (row.x + 194, row.y + 5), BLUE if h.owner else MUTED, "s")
        ui.text(rp(h.value), (row.x + 374, row.y + 5), INK, "s")
        ui.text(rp(h.rent_pp()), (row.x + 464, row.y + 5), INK, "s")
        if ui.hot(row):
            pygame.draw.rect(ui.screen, INK, row, 1, border_radius=3)
        hit(sc, row, lambda h=h: setattr(sc, "sel_house", h))
    ui.scrollbar("house", area, len(hs) * rh)
    D = pygame.Rect(C.x + 608, C.y + 48, C.w - 608, C.h - 48)
    ui.panel(D, "cream", 1)
    h = sc.sel_house
    x = D.x + 14
    wv = D.w - 28
    if h is not None:
        ui.screen.blit(a.building(f"house_{h.color_i}"), (D.centerx - 32, D.y + 10))
        ui.text(f"Rumah #{hs.index(h) + 1}", (D.centerx, D.y + 66), INK, "m", "c")
        ui.text(f"Pemilik: {h.owner.name if h.owner else 'Kota / pengembang'}"[:34], (D.centerx, D.y + 86), MUTED, "xs", "c")
        ui.text(f"Lahan {rp(h.land_value)} + bangunan {rp(h.structure_value)}",
                (D.centerx, D.y + 98), MUTED, "xs", "c")
        ui.text("Penghuni:", (x, D.y + 120), INK, "s")
        for i, o in enumerate(h.occupants[:4]):
            ui.text(f"- {o.name[:24]}", (x, D.y + 138 + i * 14), BLUE, "xs")
            hit(sc, (x, D.y + 138 + i * 14, 200, 14), lambda o=o: sc.select_citizen(o))
        ui.button((x, D.y + 198, wv, 24), "FOKUS DI PETA", lambda: setattr(sc, "focus_until", sc.cv.t + 3.0) or setattr(sc, "focus_lot", h.lot), "load_seed", 1)
        if h.owner is not sc.sel:
            buyer = sc.sel
            ui.button((x, D.y + 226, wv, 24),
                      f"BELI RUMAH · {rp(h.value)}" if buyer else "PILIH WARGA UNTUK MEMBELI",
                      lambda: sc.app.notify("Transaksi berhasil." if buyer and w.buy_house(buyer, h)
                                            else "Pembelian gagal: dana, plafon KPR, atau rumah tidak memenuhi syarat."),
                      "new_city" if buyer else "load_seed", 1)
    y = D.y + 256
    ui.bmp("PASAR PROPERTI", (x, y), 1)
    y += 18
    ui.text("Indeks harga rumah", (x, y), MUTED, "xs")
    ui.text(f"{w.house_index:.2f}x", (x + wv, y), INK, "xs", "r")
    ui.slider((x, y + 12, wv, 24), w.house_index, 0.3, 3.0, w.set_house_index, 0.05)
    y += 46
    ui.text("Imbal hasil sewa / tahun", (x, y), MUTED, "xs")
    ui.text(f"{w.rent_yield * 100:.1f}%", (x + wv, y), INK, "xs", "r")
    ui.slider((x, y + 12, wv, 24), w.rent_yield, 0.02, 0.15, w.set_rent_yield, 0.005)
    y += 46
    ui.text("PBB per tahun", (x, y), MUTED, "xs")
    ui.text(f"{w.policy.tax_pbb * 100:.1f}%", (x + wv, y), INK, "xs", "r")
    ui.slider((x, y + 12, wv, 24), w.policy.tax_pbb, 0, 0.05, lambda v: setattr(w.policy, "tax_pbb", round(v, 4)), 0.001)
    y += 46
    buyer = sc.sel
    vacant = sum(1 for lot in w.lots if lot.kind == "biz" and lot.building is None
                 and lot.land_owner is None)
    contractors = sum(1 for business in w.businesses if business.kind == "builder"
                     and business.cash >= 15_000_000 * 0.1)
    ui.text(f"Tanah kosong {vacant} · kontraktor siap {contractors}",
            (x, y), MUTED, "xs")
    y += 16
    ui.button((x, y, wv, 24),
              f"BELI LAHAN PEMERINTAH · {rp(w.lot_price)}" if buyer else "PILIH WARGA UNTUK BELI LAHAN",
              lambda: sc.app.notify("Lahan dibeli; biaya masuk ke kas kota."
                                    if buyer and w.buy_land(buyer)
                                    else "Pembelian lahan gagal atau tidak ada lahan kosong."),
              "new_city" if buyer else "load_seed", 1)
    y += 28
    owns_land = buyer and any(lot.land_owner is buyer and lot.building is None for lot in w.lots)
    ui.button((x, y, wv, 24),
              f"BANGUN RUMAH TERPISAH · {rp(15_000_000)}" if owns_land
              else "BELI LAHAN DULU UNTUK MEMBANGUN",
              lambda: sc.app.notify("Rumah selesai dibangun." if owns_land and w.build_house(buyer)
                                    else "Pembangunan gagal: perlu lahan sendiri dan kontraktor bermodal."),
              "new_city" if owns_land else "load_seed", 1)
