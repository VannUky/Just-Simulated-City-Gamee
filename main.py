r"""
main.py -- Simulasi Ekonomi Kota (pixel art)

Siapkan:    .venv\Scripts\python.exe -m pip install -r requirements.txt
Jalankan:   .venv\Scripts\python.exe main.py

Kontrol:
  SPASI jeda · 1-5 kecepatan (1x/2x/5x/10x/100x)
  P pasar saham · E dasbor makro · K kebijakan · B usaha · R properti · L layer peta · W warga · N berita
  Seret peta / tombol panah geser kota · Shift+roda geser horizontal · klik warga/gedung · M set uang · F5 simpan · F11 layar penuh · ESC menu
"""
import os
import pickle
import random
import sys
from collections import deque
from pathlib import Path

try:
    import pygame
except ImportError as error:
    raise SystemExit("Pygame belum tersedia. Aktifkan .venv dan install requirements.txt terlebih dahulu.") from error

from systems.accounting import AccountingLedger, JournalEntry, LedgerAccount, Posting
from systems.ekonomi_core import (
    Asset, Bank, Business, Citizen, Hall, House, Loan, Lot, Market, Policy,
    World,
)
from game.assets import Assets
from game.settings import Settings
from game.ui import UI
from game.menus import StartMenu, draw_pause
from game.scene_game import GameScene, W, H

ROOT = Path(__file__).resolve().parent
ASSET_DIR = ROOT / "assets"
SAVE_PATH = ROOT / "saves" / "slot1.sav"
SAVE_FORMAT = "rupiahville-save"
SAVE_SCHEMA_VERSION = 3


class RestrictedSaveUnpickler(pickle.Unpickler):
    ALLOWED_GLOBALS = {
        ("collections", "deque"): deque,
        ("random", "Random"): random.Random,
        ("systems.accounting", "AccountingLedger"): AccountingLedger,
        ("systems.accounting", "JournalEntry"): JournalEntry,
        ("systems.accounting", "LedgerAccount"): LedgerAccount,
        ("systems.accounting", "Posting"): Posting,
        ("systems.ekonomi_core", "Asset"): Asset,
        ("systems.ekonomi_core", "Bank"): Bank,
        ("systems.ekonomi_core", "Business"): Business,
        ("systems.ekonomi_core", "Citizen"): Citizen,
        ("systems.ekonomi_core", "Hall"): Hall,
        ("systems.ekonomi_core", "House"): House,
        ("systems.ekonomi_core", "Loan"): Loan,
        ("systems.ekonomi_core", "Lot"): Lot,
        ("systems.ekonomi_core", "Market"): Market,
        ("systems.ekonomi_core", "Policy"): Policy,
        ("systems.ekonomi_core", "World"): World,
    }

    def find_class(self, module, name):
        try:
            return self.ALLOWED_GLOBALS[(module, name)]
        except KeyError:
            raise pickle.UnpicklingError(
                f"Global save tidak diizinkan: {module}.{name}"
            ) from None


def _migrate_save_v1_to_v2(payload):
    migrated = dict(payload)
    world = migrated.get("world")
    if not isinstance(world, World):
        raise ValueError("Data dunia tidak ditemukan pada save.")
    ledger = getattr(world, "ledger", None)
    migrated["ledger_schema_version"] = getattr(
        ledger, "schema_version", AccountingLedger.SCHEMA_VERSION
    )
    migrated["schema_version"] = 2
    return migrated


def _migrate_save_v2_to_v3(payload):
    migrated = dict(payload)
    if not isinstance(migrated.get("world"), World):
        raise ValueError("Data dunia tidak ditemukan pada save.")
    migrated["ledger_schema_version"] = AccountingLedger.SCHEMA_VERSION
    migrated["schema_version"] = 3
    return migrated


SAVE_MIGRATIONS = {
    1: _migrate_save_v1_to_v2,
    2: _migrate_save_v2_to_v3,
}


def _decode_save_payload(payload):
    if isinstance(payload, World):
        return payload, None
    if not isinstance(payload, dict) or payload.get("format") != SAVE_FORMAT:
        raise ValueError("Format save tidak dikenal.")
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise ValueError(f"Versi skema save tidak didukung: {schema_version!r}")
    if schema_version > SAVE_SCHEMA_VERSION:
        raise ValueError(f"Versi skema save tidak didukung: {schema_version!r}")
    while schema_version < SAVE_SCHEMA_VERSION:
        migration = SAVE_MIGRATIONS.get(schema_version)
        if migration is None:
            raise ValueError(f"Versi skema save tidak didukung: {schema_version!r}")
        migrated_payload = migration(payload)
        if not isinstance(migrated_payload, dict):
            raise ValueError("Migrasi skema save menghasilkan data tidak valid.")
        migrated_version = migrated_payload.get("schema_version")
        if (isinstance(migrated_version, bool)
                or not isinstance(migrated_version, int)
                or migrated_version <= schema_version
                or migrated_version > SAVE_SCHEMA_VERSION):
            raise ValueError("Migrasi skema save tidak menaikkan versi dengan benar.")
        payload = migrated_payload
        schema_version = migrated_version
    world = payload.get("world")
    if not isinstance(world, World):
        raise ValueError("Data dunia tidak ditemukan pada save.")
    ledger_schema_version = payload.get("ledger_schema_version")
    if (isinstance(ledger_schema_version, bool)
            or not isinstance(ledger_schema_version, int)):
        raise ValueError("Versi ledger pada save tidak valid.")
    return world, ledger_schema_version


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Rupiahville - Simulasi Ekonomi Kota")
        self.settings = Settings()
        try:
            flags = pygame.SCALED | pygame.RESIZABLE
            self.screen = pygame.display.set_mode((W, H), flags)
        except pygame.error:
            self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.assets = Assets(ASSET_DIR)
        self.ui = UI(self.assets)
        self.running = True
        self.scene = StartMenu(self)
        if self.settings.fullscreen:
            self.apply_fullscreen()

    # ---- alur layar
    def new_game(self, seed=None):
        world = World(seed=seed, n_pop=int(self.settings.population))
        self.scene = GameScene(self, world)

    def go_menu(self):
        self.scene = StartMenu(self)

    def quit(self):
        self.running = False

    def draw_pause(self, sc):
        draw_pause(self, sc)

    def apply_fullscreen(self):
        want = bool(self.settings.fullscreen)
        cur = bool(pygame.display.get_surface().get_flags() & pygame.FULLSCREEN)
        if want != cur:
            pygame.display.toggle_fullscreen()

    # ---- simpan / muat
    def has_save(self):
        return SAVE_PATH.is_file()

    def notify(self, message):
        show_message = getattr(self.scene, "say", None)
        if show_message is None:
            print(message)
            return
        show_message(message)

    def save_world(self, world):
        temp_path = SAVE_PATH.with_name(SAVE_PATH.name + ".tmp")
        previous_limit = sys.getrecursionlimit()
        try:
            SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
            if previous_limit < 20000:
                sys.setrecursionlimit(20000)
            with temp_path.open("wb") as f:
                payload = {
                    "format": SAVE_FORMAT,
                    "schema_version": SAVE_SCHEMA_VERSION,
                    "ledger_schema_version": world.ledger.schema_version,
                    "world": world,
                }
                pickle.dump(payload, f, protocol=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, SAVE_PATH)
        except (OSError, pickle.PickleError, AttributeError, TypeError,
                ValueError, RecursionError, OverflowError) as err:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as cleanup_error:
                self.notify(f"GAGAL MENYIMPAN: {err}; file sementara gagal dihapus: {cleanup_error}")
                return False
            self.notify(f"GAGAL MENYIMPAN: {err}")
            return False
        finally:
            if sys.getrecursionlimit() != previous_limit:
                sys.setrecursionlimit(previous_limit)
        self.notify("GAME TERSIMPAN")
        return True

    def load_game(self):
        try:
            previous_limit = sys.getrecursionlimit()
            if previous_limit < 20000:
                sys.setrecursionlimit(20000)
            with open(SAVE_PATH, "rb") as f:
                payload = RestrictedSaveUnpickler(f).load()
            world, ledger_schema_version = _decode_save_payload(payload)
        except (OSError, EOFError, pickle.UnpicklingError, AttributeError,
                ImportError, IndexError, KeyError, TypeError, ValueError,
                RecursionError, OverflowError) as err:
            self.notify(f"GAGAL MEMUAT SAVE: {err}")
            return False
        finally:
            if "previous_limit" in locals() and sys.getrecursionlimit() != previous_limit:
                sys.setrecursionlimit(previous_limit)
        if not isinstance(world, World):
            self.notify("SAVE TIDAK VALID: data kota tidak ditemukan")
            return False
        try:
            world.migrate_save()
        except (AttributeError, TypeError, ValueError) as err:
            self.notify(f"SAVE TIDAK KOMPATIBEL: {err}")
            return False
        if (ledger_schema_version is not None
                and world.ledger.schema_version != ledger_schema_version):
            self.notify("SAVE TIDAK KOMPATIBEL: versi ledger tidak cocok")
            return False
        self.scene = GameScene(self, world)
        self.notify("SAVE BERHASIL DIMUAT")
        return True

    # ---- loop
    def run(self):
        while self.running:
            dt = min(self.clock.tick(60) / 1000.0, 0.1)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    self.settings.set("fullscreen", not self.settings.fullscreen)
                    self.apply_fullscreen()
                else:
                    self.scene.event(e)
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()
        pygame.quit()


if __name__ == "__main__":
    App().run()
